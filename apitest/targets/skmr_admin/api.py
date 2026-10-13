# -*- coding: utf-8 -*-
"""skmr-api-admin(EcmManager API) 엔드포인트 래퍼. 우선 읽기 전용부터 (쓰기/삭제는 범위 확정 후 추가)."""
from __future__ import annotations

from ...core.client import ApiClient, Resp


class EcmManagerApi:
    def __init__(self, client: ApiClient) -> None:
        self.c = client

    async def me(self) -> Resp:
        return await self.c.request("auth.me", "GET", "/auth/me")

    async def users(self) -> Resp:
        return await self.c.request("admin.users", "GET", "/admin/users")

    async def depts(self) -> Resp:
        return await self.c.request("admin.depts", "GET", "/admin/depts")

    async def security_policies(self) -> Resp:
        return await self.c.request("admin.security_policies", "GET", "/admin/security-policies")

    async def menus(self) -> Resp:
        return await self.c.request("admin.menus", "GET", "/admin/menus")

    async def common_codes(self) -> Resp:
        return await self.c.request("admin.common_codes", "GET", "/admin/common-codes")

    async def org_tree(self) -> Resp:
        return await self.c.request("org.tree", "GET", "/org/tree")

    async def managed_scopes(self) -> Resp:
        return await self.c.request("managed_scopes", "GET", "/managed-scopes")

    async def health(self) -> Resp:
        # 다른 엔드포인트와 달리 /api/v1 이 아니라 /api 바로 아래라, cfg.api_prefix 가 자동으로
        # 붙는 일반 request() 경로로는 도달 못한다. 내부 httpx 클라이언트로 전체 경로를 직접 호출한다.
        response = await self.c._http.request("GET", "/api/health")  # noqa: SLF001
        try:
            body = response.json()
        except ValueError:
            body = response.text[:500]
        return Resp(response.status_code, body, 0.0, response.status_code < 300, dict(response.headers))
