# -*- coding: utf-8 -*-
"""skmr API 모의 서버 (표준 라이브러리만 사용). 프레임워크 자체 검증/개발용이며 실제 서버 동작을 보증하지 않는다.

구현: 챌린지+하이브리드 암호화 로그인(crypto.py 와 같은 가정), 쿠키 세션 + 만료/갱신, API key 검사(선택),
      folders/documents, 청크 업로드 5개 API(소유자 검사 포함), 지연/오류 주입.

  python -m apitest.mock.skmr_mock --port 8099 [--api-key SECRET] [--token-ttl 240] [--latency-ms 0] [--fail-rate 0]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import random
import re
import secrets
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CHUNK_SIZE = 64 * 1024
PREFIX = "/api/v1"


class State:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.lock = threading.Lock()
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        self.public_pem = self.private_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        self.users = {f"new{i}": "1234" for i in range(1, 51)}
        self.challenges: dict[str, str] = {}      # challengeId -> nonce
        self.sessions: dict[str, tuple[str, float]] = {}  # sid -> (user, expires)
        self.refresh: dict[str, str] = {}         # rid -> user
        self.uploads: dict[str, dict] = {}
        self.documents: dict[str, list[dict]] = {"FLD_A": [], "FLD_B": []}
        self.requests = 0


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "skmr-mock"
    state: State

    def log_message(self, *a) -> None:  # 콘솔 소음 제거
        pass

    # ---- 공통
    def _send(self, status: int, body=None, cookies: list[str] | None = None) -> None:
        data = b"" if body is None else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json;charset=UTF-8")
        self.send_header("Content-Length", str(len(data)))
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        if data:
            self.wfile.write(data)

    def _cookie(self, name: str) -> str:
        for part in self.headers.get("Cookie", "").split(";"):
            key, _, value = part.strip().partition("=")
            if key == name:
                return value
        return ""

    def _body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def _user(self) -> str | None:
        sid = self._cookie("sid")
        with self.state.lock:
            session = self.state.sessions.get(sid)
        if session and session[1] > time.time():
            return session[0]
        return None

    def _issue_session(self, user: str) -> list[str]:
        sid, rid = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        with self.state.lock:
            self.state.sessions[sid] = (user, time.time() + self.state.args.token_ttl)
            self.state.refresh[rid] = user
        return [f"sid={sid}; Path=/; HttpOnly", f"rid={rid}; Path=/; HttpOnly"]

    def _dispatch(self, method: str) -> None:
        st = self.state
        with st.lock:
            st.requests += 1
        if st.args.latency_ms:
            time.sleep(st.args.latency_ms / 1000)
        if st.args.api_key and self.headers.get("X-API-Key") != st.args.api_key:
            body = self._body() if method in ("POST", "PUT") else b""
            return self._send(401, {"code": "UNAUTHORIZED", "message": "Invalid or missing API key"})

        parsed = urlsplit(self.path)
        path = parsed.path
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        if not path.startswith(PREFIX):
            self._body()
            return self._send(404, {"message": "not found"})
        route = path[len(PREFIX):]

        # ---- 인증 (세션 불필요)
        if method == "GET" and route == "/auth/login/challenge":
            cid, nonce = str(uuid.uuid4()), secrets.token_urlsafe(32)
            with st.lock:
                st.challenges[cid] = nonce
            return self._send(200, {"challengeId": cid, "nonce": nonce, "keyId": "mock-key", "publicKey": st.public_pem,
                                    "algorithm": "RSA-OAEP-256+A256GCM", "expiresIn": 120})
        if method == "POST" and route == "/auth/login":
            return self._login()
        if method == "POST" and route == "/auth/refresh":
            self._body()
            with st.lock:
                user = st.refresh.get(self._cookie("rid"))
            if not user:
                return self._send(401, {"message": "invalid refresh"})
            return self._send(200, {"message": "refreshed", "expiresIn": st.args.token_ttl}, self._issue_session(user))

        # ---- 이하 세션 필요
        body = self._body() if method in ("POST", "PUT", "DELETE") else b""
        user = self._user()
        if not user:
            return self._send(401, {"message": "unauthorized"})

        if method == "GET" and route == "/auth/me":
            return self._send(200, {"username": user, "loginChannel": "WEB", "userNm": user})
        if method == "GET" and route == "/folders/roots":
            return self._send(200, [{"id": "DOCBOXM_1", "name": "부서문서함", "parentFolderId": None, "gubun": "D"}])
        if method == "GET" and (m := re.fullmatch(r"/folders/([^/]+)/children", route)):
            return self._send(200, [{"id": "FLD_A", "name": "테스트폴더A"}, {"id": "FLD_B", "name": "테스트폴더B"}])
        if method == "GET" and route == "/documents":
            items = list(st.documents.get(query.get("boxId", ""), []))
            return self._send(200, {"items": items, "page": 1, "size": 100, "totalCount": len(items),
                                    "totalPages": 1, "hasNext": False})
        return self._upload_routes(method, route, body, user)

    # ---- 로그인
    def _login(self) -> None:
        st = self.state
        try:
            req = json.loads(self._body())
            with st.lock:
                nonce = st.challenges.pop(req["challengeId"], None)  # 1회용
            if nonce is None:
                return self._send(400, {"message": "invalid or used challenge"})
            aes_key = st.private_key.decrypt(
                base64.b64decode(req["encryptedKey"]),
                padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
            )
            plain = json.loads(AESGCM(aes_key).decrypt(base64.b64decode(req["iv"]), base64.b64decode(req["ciphertext"]), None))
        except Exception as exc:
            return self._send(400, {"message": f"decrypt failed: {type(exc).__name__}"})
        if plain.get("nonce") != nonce or plain.get("challengeId") != req["challengeId"] or plain.get("loginChannel") != "WEB":
            return self._send(401, {"message": "nonce/challenge mismatch"})
        if abs(time.time() * 1000 - int(plain.get("issuedAt", 0))) > 120_000:
            return self._send(401, {"message": "issuedAt out of range"})
        user = plain.get("username")
        if st.users.get(user) != plain.get("password"):
            return self._send(401, {"message": "invalid credentials"})
        self._send(200, {"message": "로그인에 성공했습니다.", "tokenType": "Bearer", "expiresIn": st.args.token_ttl,
                         "username": user, "loginChannel": "WEB"}, self._issue_session(user))

    # ---- 청크 업로드
    def _upload_routes(self, method: str, route: str, body: bytes, user: str) -> None:
        st = self.state
        if method == "POST" and route == "/document-uploads":
            req = json.loads(body or b"{}")
            if not all(k in req for k in ("operation", "folderId", "fileName", "fileSize", "expectedFileSha256")):
                return self._send(400, {"message": "operation/folderId/fileName/fileSize/expectedFileSha256 required"})
            if req["folderId"] not in st.documents:
                return self._send(404, {"message": "folder not found"})
            uid = str(uuid.uuid4())
            total = max(1, -(-int(req["fileSize"]) // CHUNK_SIZE))
            with st.lock:
                dup = any(d.get("sha256") == req["expectedFileSha256"] for d in st.documents[req["folderId"]])
                st.uploads[uid] = {"owner": user, "folder": req["folderId"], "name": req["fileName"],
                                   "size": int(req["fileSize"]), "total": total, "chunks": {},
                                   "sha256": req["expectedFileSha256"], "status": "COMPLETED" if dup else "UPLOADING"}
            if dup:  # 같은 내용이 이미 있으면 청크 전송 없이 완료 (프론트엔드의 COMPLETED 분기)
                return self._send(200, {"uploadId": uid, "status": "COMPLETED"})
            return self._send(200, {"uploadId": uid, "status": "UPLOADING", "chunkSize": CHUNK_SIZE,
                                    "totalChunks": total, "uploadedChunks": []})

        m = re.fullmatch(r"/document-uploads/([^/]+)(?:/(chunks/(\d+)|complete))?", route)
        if not m:
            return self._send(404, {"message": "not found"})
        uid, sub, index = m.group(1), m.group(2), m.group(3)
        with st.lock:
            up = st.uploads.get(uid)
        if up is None:
            return self._send(404, {"message": "upload not found"})
        if up["owner"] != user:  # 다른 계정의 업로드 접근 차단
            return self._send(403, {"message": "forbidden"})

        if method == "PUT" and index is not None:
            if st.args.fail_rate and random.random() < st.args.fail_rate:
                return self._send(500, {"message": "injected failure"})
            i = int(index)
            if i >= up["total"]:
                return self._send(400, {"message": "chunk index out of range"})
            if self.headers.get("X-Chunk-SHA256") != hashlib.sha256(body).hexdigest():
                return self._send(400, {"message": "chunk sha256 mismatch"})
            with st.lock:
                up["chunks"][i] = len(body)
            return self._send(200, {"index": i, "received": len(body)})
        if method == "GET" and sub is None:
            with st.lock:
                got = sorted(up["chunks"])
            return self._send(200, {"uploadId": uid, "status": up["status"], "uploadedChunks": got, "totalChunks": up["total"]})
        if method == "POST" and sub == "complete":
            with st.lock:
                if len(up["chunks"]) != up["total"] or sum(up["chunks"].values()) != up["size"]:
                    return self._send(409, {"message": "chunks incomplete"})
                doc = {"id": f"DOC_{uuid.uuid4().hex[:12]}", "name": up["name"], "owner": up["owner"],
                       "size": up["size"], "sha256": up["sha256"]}
                st.documents[up["folder"]].append(doc)
                up["status"] = "COMPLETED"
            return self._send(200, {"documentId": doc["id"], "status": "COMPLETED"})
        if method == "DELETE" and sub is None:
            with st.lock:
                st.uploads.pop(uid, None)
            return self._send(200, {"uploadId": uid, "status": "CANCELLED"})
        return self._send(405, {"message": "method not allowed"})

    def do_GET(self) -> None: self._dispatch("GET")
    def do_POST(self) -> None: self._dispatch("POST")
    def do_PUT(self) -> None: self._dispatch("PUT")
    def do_DELETE(self) -> None: self._dispatch("DELETE")


def make_server(args: argparse.Namespace) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"state": State(args)})
    server = ThreadingHTTPServer((args.host, args.port), handler)
    server.daemon_threads = True
    return server


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="skmr API 모의 서버")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--api-key", default="", help="지정하면 X-API-Key 헤더를 요구")
    parser.add_argument("--token-ttl", type=float, default=240, help="세션 만료(초). 작게 주면 401->갱신 경로 테스트")
    parser.add_argument("--latency-ms", type=int, default=0)
    parser.add_argument("--fail-rate", type=float, default=0.0, help="chunk PUT 에 주입할 500 오류 비율(0~1)")
    return parser.parse_args(argv)


if __name__ == "__main__":
    ns = parse_args()
    srv = make_server(ns)
    print(f"mock skmr listening on http://{ns.host}:{ns.port}  (api_key={'on' if ns.api_key else 'off'}, token_ttl={ns.token_ttl}s)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
