# -*- coding: utf-8 -*-
"""skmr 인증 흐름 (순수 API).

login : GET /auth/login/challenge -> 암호화 -> POST /auth/login
        세션은 응답의 Set-Cookie(httpx 쿠키 저장소가 자동 보관)를 기본으로 한다.
        응답 body 에 accessToken 이 있으면 Authorization 헤더도 함께 설정한다 (미확인 -> 양쪽 모두 지원).
refresh: POST /auth/refresh. 실패하면 전체 재로그인. 만료(expiresIn=240s 관측)로 인한 401 에서 자동 호출된다.
"""
from __future__ import annotations

from typing import Any

from ...core.client import ApiClient, Resp
from ...core.config import Account
from . import crypto


class LoginError(RuntimeError):
    pass


async def login(client: ApiClient, account: Account) -> Resp:
    challenge = await client.request("auth.challenge", "GET", "/auth/login/challenge", retry_401=False)
    if not challenge.ok or not isinstance(challenge.body, dict):
        raise LoginError(f"challenge 실패: status={challenge.status} body={str(challenge.body)[:200]}")

    payload = crypto.encrypt_login(account.username, account.password, challenge.body)
    response = await client.request("auth.login", "POST", "/auth/login", json=payload, retry_401=False)
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
