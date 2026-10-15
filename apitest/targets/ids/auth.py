# -*- coding: utf-8 -*-
"""IDS 로그인 (순수 API).

login.do 는 비밀번호를 받지 않는다 (mitmproxy 로 실제 클라이언트 트래픽을 캡처해 확인).
IDS 는 웹(OTCS) 로그인 때 확인된 사용자 정보를 그대로 물려받는 설계라, user_id(base64) 만 보내면
서버가 세션(JSESSIONID)을 내려준다. 응답 본문은 항상 "{}" (성공/실패를 body 로 구분하지 않음 -> 세션
쿠키 발급 여부로 성공을 판단한다).
"""
from __future__ import annotations

from ...core.client import ApiClient, Resp
from ...core.config import Account
from .api import b64, form_request


class LoginError(RuntimeError):
    pass


async def login(client: ApiClient, account: Account) -> Resp:
    response = await form_request(
        client, "auth.login", "/main/login/login.do", {"userId": b64(account.username)}, retry_401=False,
    )
    if not response.ok or "JSESSIONID" not in client.cookies:
        raise LoginError(f"login 실패: status={response.status} body={str(response.body)[:200]}")
    return response
