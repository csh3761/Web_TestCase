# -*- coding: utf-8 -*-
"""skmr-api-admin(EcmManager API) 인증 흐름 (순수 API).

skmr(일반사용자 DocSphere API)과 서버가 다르고 인증 방식도 다르다.
- 로그인: 챌린지/암호화 없이 POST /auth/login 에 {username, password, clientType?} 평문.
  clientType 은 화면(업무함관리자/시스템관리자)마다 다르다 (Account.client_type, 비어 있으면 아예 안 보냄).
  보낸 값이 틀리면 403 FORBIDDEN("지원하지 않는 로그인 클라이언트입니다"), 자격증명이 틀리면 401.
- 세션: 응답 body 의 accessToken 을 Authorization: Bearer 로 직접 실어야 한다 (쿠키 아님).
  Refresh Token 만 HttpOnly 쿠키로 내려온다 (httpx 쿠키 저장소가 자동 보관).
- 토큰 유효시간 900초 관측.
"""
from __future__ import annotations

from typing import Any

from ...core.client import ApiClient, Resp
from ...core.config import Account


class LoginError(RuntimeError):
    pass


def _login_body(account: Account) -> dict[str, Any]:
    body: dict[str, Any] = {"username": account.username, "password": account.password}
    if account.client_type:
        body["clientType"] = account.client_type
    return body


async def login(client: ApiClient, account: Account) -> Resp:
    response = await client.request("auth.login", "POST", "/auth/login", json=_login_body(account), retry_401=False)
    if not response.ok:
        raise LoginError(f"login 실패: status={response.status} body={str(response.body)[:200]}")
    _apply_token(client, response.body)
    return response


def _apply_token(client: ApiClient, body: Any) -> None:
    if isinstance(body, dict) and body.get("accessToken"):
        scheme = body.get("tokenType") or "Bearer"
        client.auth_headers["Authorization"] = f"{scheme} {body['accessToken']}"


def install_refresh_handler(client: ApiClient, account: Account) -> None:
    async def refresh() -> None:
        response = await client.request("auth.refresh", "POST", "/auth/refresh", retry_401=False)
        if response.ok:
            _apply_token(client, response.body)
            return
        client.recorder.count("auth.relogin")
        client.auth_headers.pop("Authorization", None)
        await login(client, account)

    client.on_unauthorized = refresh
