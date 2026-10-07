// skmr 로그인 Pre-request Script (Postman)
// 하는 일: 챌린지 조회 -> 로그인 정보를 AES-256-GCM 으로 암호화 -> AES 키를 서버 공개키로 RSA-OAEP(SHA-256) 암호화
//          -> 로그인 본문(JSON)을 변수 loginBody 에 저장. 요청 Body 는 {{loginBody}} 로 지정한다.
// 필요 변수: base_url, username, password
//
// 외부 패키지(pm.require, npm)나 Node crypto 없이, Postman 에 기본 내장된 crypto-js 만 사용한다.
// crypto-js 에는 AES-GCM / RSA 가 없어서 아래에 직접 구현했다 (AES 블록 암호와 SHA-256 만 crypto-js 사용).
// 참고: 스크립트가 오류로 중단돼도 Postman 은 요청을 그대로 보낸다 -> "본문 형식이 올바르지 않습니다"(VALIDATION_ERROR)가 나오면
//       View > Show Postman Console 에서 스크립트 오류를 확인한다.
const CryptoJS = require('crypto-js');

// ------------------------------------------------------------------ 바이트 유틸
function bytesToWA(u8) {
  const words = [];
  for (let i = 0; i < u8.length; i++) { words[i >>> 2] = (words[i >>> 2] || 0) | (u8[i] << (24 - (i % 4) * 8)); }
  return CryptoJS.lib.WordArray.create(words, u8.length);
}
function waToBytes(wa) {
  const out = new Uint8Array(wa.sigBytes);
  for (let i = 0; i < wa.sigBytes; i++) { out[i] = (wa.words[i >>> 2] >>> (24 - (i % 4) * 8)) & 0xff; }
  return out;
}
function concat(...parts) {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let off = 0;
  for (const p of parts) { out.set(p, off); off += p.length; }
  return out;
}
function xor(a, b) {
  const out = new Uint8Array(a.length);
  for (let i = 0; i < a.length; i++) { out[i] = a[i] ^ b[i]; }
  return out;
}
function toBig(u8) {
  let h = '';
  for (const b of u8) { h += b.toString(16).padStart(2, '0'); }
  return BigInt('0x' + (h || '0'));
}
function fromBig(n, len) {
  const h = n.toString(16).padStart(len * 2, '0');
  const out = new Uint8Array(len);
  for (let i = 0; i < len; i++) { out[i] = parseInt(h.substr(i * 2, 2), 16); }
  return out;
}
function randomBytes(n) {
  // Postman 샌드박스에는 globalThis 가 없을 수 있다. 전역 crypto 가 있을 때만 사용하고, 없으면 crypto-js 난수를 쓴다.
  // (typeof 는 선언되지 않은 식별자에 대해서만 안전하다 -> 속성 접근 전에 반드시 먼저 검사)
  if (typeof crypto !== 'undefined' && crypto && typeof crypto.getRandomValues === 'function') {
    return crypto.getRandomValues(new Uint8Array(n));
  }
  return waToBytes(CryptoJS.lib.WordArray.random(n));  // 테스트 도구 용도의 대체 난수
}
function sha256(u8) { return waToBytes(CryptoJS.SHA256(bytesToWA(u8))); }
function b64(u8) { return CryptoJS.enc.Base64.stringify(bytesToWA(u8)); }
function utf8(str) { return waToBytes(CryptoJS.enc.Utf8.parse(str)); }

// ------------------------------------------------------------------ AES-256-GCM (iv 12바이트, 태그 16바이트, AAD 없음)
function aesEcb(key, data) {  // data 길이는 16의 배수 (패딩 없음)
  const enc = CryptoJS.AES.encrypt(bytesToWA(data), bytesToWA(key), { mode: CryptoJS.mode.ECB, padding: CryptoJS.pad.NoPadding });
  return waToBytes(enc.ciphertext);
}
const GCM_R = 0xe1n << 120n;
function gmul(x, y) {  // GF(2^128) 곱셈
  let z = 0n;
  let v = y;
  for (let i = 127n; i >= 0n; i--) {
    if ((x >> i) & 1n) { z ^= v; }
    v = (v & 1n) ? ((v >> 1n) ^ GCM_R) : (v >> 1n);
  }
  return z;
}
function ghash(h, ct) {
  let y = 0n;
  for (let off = 0; off < ct.length; off += 16) {
    const block = new Uint8Array(16);
    block.set(ct.subarray(off, off + 16));
    y = gmul(y ^ toBig(block), h);
  }
  return gmul(y ^ BigInt(ct.length * 8), h);  // [len(A)=0 || len(C)]
}
function aesGcmEncrypt(key, iv, plaintext) {
  const h = toBig(aesEcb(key, new Uint8Array(16)));
  const blocks = Math.max(1, Math.ceil(plaintext.length / 16));
  const counters = new Uint8Array(blocks * 16);
  for (let i = 0; i < blocks; i++) {  // 첫 데이터 블록의 카운터는 2 (1 은 태그용 J0)
    counters.set(iv, i * 16);
    const c = i + 2;
    counters.set([(c >>> 24) & 255, (c >>> 16) & 255, (c >>> 8) & 255, c & 255], i * 16 + 12);
  }
  const keystream = aesEcb(key, counters);
  const ct = xor(plaintext, keystream.subarray(0, plaintext.length));
  const j0 = new Uint8Array(16);
  j0.set(iv);
  j0[15] = 1;
  const tag = fromBig(ghash(h, ct) ^ toBig(aesEcb(key, j0)), 16);
  return concat(ct, tag);  // WebCrypto 와 동일: 암호문 뒤에 태그
}

// ------------------------------------------------------------------ RSA-OAEP (SHA-256, MGF1 SHA-256, label 없음)
function derRead(buf, pos) {
  let len = buf[pos + 1];
  let p = pos + 2;
  if (len & 0x80) {
    const n = len & 0x7f;
    len = 0;
    for (let i = 0; i < n; i++) { len = (len * 256) + buf[p++]; }
  }
  return { start: p, end: p + len };
}
function stripZero(u8) {
  let i = 0;
  while (i < u8.length - 1 && u8[i] === 0) { i++; }
  return u8.subarray(i);
}
function parseSpkiPem(pem) {
  const der = waToBytes(CryptoJS.enc.Base64.parse(pem.replace(/-----[^-]+-----/g, '').replace(/\s+/g, '')));
  const outer = derRead(der, 0);
  const algorithm = derRead(der, outer.start);
  const bitString = derRead(der, algorithm.end);
  const rsaKey = derRead(der, bitString.start + 1);  // BIT STRING 첫 바이트는 unused-bits
  const nField = derRead(der, rsaKey.start);
  const eField = derRead(der, nField.end);
  const n = stripZero(der.subarray(nField.start, nField.end));
  return { n: toBig(n), e: toBig(der.subarray(eField.start, eField.end)), k: n.length };
}
function modPow(base, exp, mod) {
  let result = 1n;
  let b = base % mod;
  let e = exp;
  while (e > 0n) {
    if (e & 1n) { result = (result * b) % mod; }
    e >>= 1n;
    b = (b * b) % mod;
  }
  return result;
}
function mgf1(seed, length) {
  const parts = [];
  let total = 0;
  for (let counter = 0; total < length; counter++) {
    const c = new Uint8Array([(counter >>> 24) & 255, (counter >>> 16) & 255, (counter >>> 8) & 255, counter & 255]);
    const h = sha256(concat(seed, c));
    parts.push(h);
    total += h.length;
  }
  return concat(...parts).subarray(0, length);
}
function rsaOaepEncrypt(pub, message) {
  const hLen = 32;
  if (message.length > pub.k - 2 * hLen - 2) { throw new Error('RSA-OAEP: 메시지가 너무 깁니다.'); }
  const db = new Uint8Array(pub.k - hLen - 1);
  db.set(sha256(new Uint8Array(0)), 0);           // lHash (label 없음)
  db[db.length - message.length - 1] = 1;          // 0x01 구분자 (그 앞은 0 패딩)
  db.set(message, db.length - message.length);
  const seed = randomBytes(hLen);
  const maskedDb = xor(db, mgf1(seed, db.length));
  const maskedSeed = xor(seed, mgf1(maskedDb, hLen));
  const em = concat(new Uint8Array([0]), maskedSeed, maskedDb);
  return fromBig(modPow(toBig(em), pub.e, pub.n), pub.k);
}

// ------------------------------------------------------------------ 로그인 본문 생성
const baseUrl = pm.variables.get('base_url');
const username = pm.variables.get('username');
const password = pm.variables.get('password');

pm.sendRequest(
  {
    url: `${baseUrl}/api/v1/auth/login/challenge`,
    method: 'GET',
    header: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  },
  (err, res) => {
    if (err) { throw err; }
    const ch = res.json();

    // 평문: 프론트엔드와 같은 키 순서. issuedAt 은 밀리초.
    const plaintext = utf8(JSON.stringify({
      username,
      password,
      loginChannel: 'WEB',
      challengeId: ch.challengeId,
      nonce: ch.nonce,
      issuedAt: Date.now(),
    }));

    const aesKey = randomBytes(32);
    const iv = randomBytes(12);
    const ciphertext = aesGcmEncrypt(aesKey, iv, plaintext);
    const encryptedKey = rsaOaepEncrypt(parseSpkiPem(ch.publicKey), aesKey);

    pm.variables.set('loginBody', JSON.stringify({
      challengeId: ch.challengeId,
      keyId: ch.keyId,
      encryptedKey: b64(encryptedKey),
      iv: b64(iv),
      ciphertext: b64(ciphertext),
    }));
  }
);
