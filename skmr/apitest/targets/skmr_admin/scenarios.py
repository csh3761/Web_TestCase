# -*- coding: utf-8 -*-
"""skmr_admin(EcmManager API, 업무함관리자/시스템관리자) 시나리오. 우선 읽기 전용만: smoke(기능), login(동시 로그인/부하)."""
from __future__ import annotations

from typing import Any

from ...core.runner import VU, Scenario
from . import auth
from .api import EcmManagerApi


async def _login(vu: VU) -> EcmManagerApi:
    auth.install_refresh_handler(vu.client, vu.account)
    response = await auth.login(vu.client, vu.account)
    vu.state["login_username"] = response.get("username")  # EcmManager 로그인 응답엔 username 이 없음(토큰만) -> 보통 None, me()로 확인
    api = EcmManagerApi(vu.client)
    vu.state["api"] = api
    return api


async def _check_identity(vu: VU) -> dict[str, Any]:
    me = await vu.state["api"].me()
    actual = me.get("username") if me.body else None
    return {"status": me.status, "username": actual, "ok": me.ok and actual == vu.account.username}


def _identity_check(vus: list[VU]) -> dict[str, Any]:
    ready = [v for v in vus if v.ready]
    ok = bool(ready) and all(
        v.state.get("identity_before", {}).get("ok") and v.state.get("identity_after", {}).get("ok") for v in ready
    )
    return {"session_identity": ok}


class SmokeScenario(Scenario):
    name = "admin_smoke"
    description = "[skmr_admin] 기능 점검: 로그인 -> me -> 관리자 목록 조회 몇 종 (쓰기 없음)"
    target = "skmr_admin"

    async def setup(self, vu: VU) -> None:
        await _login(vu)

    async def run(self, vu: VU, iteration: int) -> None:
        api: EcmManagerApi = vu.state["api"]
        steps: dict[str, bool] = {}

        me = await api.me()
        steps["me"] = me.ok and me.get("username") == vu.account.username

        for label, call in (
            ("users", api.users), ("depts", api.depts), ("security_policies", api.security_policies),
            ("menus", api.menus), ("common_codes", api.common_codes), ("org_tree", api.org_tree),
            ("managed_scopes", api.managed_scopes),
        ):
            resp = await call()
            # 역할에 따라 일부 관리자 전용 API 는 403 이 정상일 수 있어, 거부 응답도 "서버가 제대로 응답했다"로 본다
            steps[label] = resp.status in (200,) or resp.status in (401, 403)

        vu.state.setdefault("steps", []).append(steps)

    async def finalize(self, vus: list[VU]) -> dict[str, Any]:
        merged: dict[str, bool] = {}
        for vu in vus:
            for steps in vu.state.get("steps", []):
                for key, ok in steps.items():
                    merged[key] = merged.get(key, True) and ok
        return {f"step.{k}": v for k, v in merged.items()}


class LoginScenario(Scenario):
    name = "admin_login"
    description = "[skmr_admin] 동시 로그인 + 세션 유지 확인. --relogin 이면 매 반복마다 재로그인"
    target = "skmr_admin"

    @classmethod
    def add_args(cls, parser: Any) -> None:
        parser.add_argument("--relogin", action="store_true", help="반복마다 새로 로그인 (로그인 API 부하)")

    async def setup(self, vu: VU) -> None:
        await _login(vu)
        vu.state["identity_before"] = await _check_identity(vu)

    async def run(self, vu: VU, iteration: int) -> None:
        if self.args.relogin and iteration > 0:
            await auth.login(vu.client, vu.account)
        me = await vu.state["api"].me()
        if me.get("username") != vu.account.username:
            vu.state["identity_mismatch"] = vu.state.get("identity_mismatch", 0) + 1

    async def teardown(self, vu: VU) -> None:
        vu.state["identity_after"] = await _check_identity(vu)

    async def finalize(self, vus: list[VU]) -> dict[str, Any]:
        checks = _identity_check(vus)
        checks["no_identity_mismatch"] = not any(v.state.get("identity_mismatch") for v in vus)
        return checks


SCENARIOS: dict[str, type[Scenario]] = {s.name: s for s in (SmokeScenario, LoginScenario)}
