# -*- coding: utf-8 -*-
"""skmr 로그인 암호화 (하이브리드: RSA-OAEP-256 + A256GCM).

규격 출처: 프론트엔드 번들(index-*.js)의 로그인 암호화 함수 (2026-10-06 확인)
  challenge: {challengeId, nonce, keyId, publicKey(PEM), algorithm="RSA-OAEP-256+A256GCM", expiresIn}
  평문(JSON.stringify, 키 순서 그대로):
      {username, password, loginChannel:"WEB", challengeId, nonce, issuedAt:<Date.now() 밀리초>}
  암호화: AES-256-GCM(iv 12바이트, tagLength 128, AAD 없음)으로 평문 암호화
          -> 그 AES 키를 서버 공개키로 RSA-OAEP(SHA-256) 암호화
  login 요청: {challengeId, keyId, encryptedKey, iv, ciphertext}  (모두 표준 base64, btoa)
  (WebCrypto 의 AES-GCM 결과는 ciphertext||tag 이며 cryptography 의 AESGCM 도 동일)
"""
from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def build_plaintext(username: str, password: str, challenge: dict[str, Any]) -> bytes:
    """프론트엔드와 동일한 키 순서/값. issuedAt 은 밀리초."""
    return json.dumps(
        {
            "username": username,
            "password": password,
            "loginChannel": "WEB",
            "challengeId": challenge["challengeId"],
            "nonce": challenge["nonce"],
            "issuedAt": int(time.time() * 1000),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def build_aad(challenge: dict[str, Any]) -> bytes | None:
    """프론트엔드는 additionalData 를 쓰지 않는다 (AAD 없음)."""
    return None


def encrypt_login(username: str, password: str, challenge: dict[str, Any]) -> dict[str, str]:
    public_key = serialization.load_pem_public_key(challenge["publicKey"].encode("ascii"))
    aes_key = AESGCM.generate_key(bit_length=256)
    iv = os.urandom(12)
    ciphertext = AESGCM(aes_key).encrypt(iv, build_plaintext(username, password, challenge), build_aad(challenge))
    encrypted_key = public_key.encrypt(
        aes_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    return {
        "challengeId": challenge["challengeId"],
        "keyId": challenge["keyId"],
        "encryptedKey": b64(encrypted_key),
        "iv": b64(iv),
        "ciphertext": b64(ciphertext),
    }
