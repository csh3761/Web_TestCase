# -*- coding: utf-8 -*-
"""가상 유저(VU) 실행기.

시나리오 생명주기: setup(로그인 등) -> [동시 시작 게이트] -> run(i) 반복 -> teardown -> finalize(전체 검증)
- users 가 계정 수보다 많으면 계정을 순환 배정한다 (같은 계정의 다중 세션).
- 한 VU의 setup 이 실패해도 게이트가 풀리도록 도착 카운트 방식을 쓴다 (barrier 교착 방지).
- ramp_up_s 만큼 VU 시작 시점을 균등하게 분산한다.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from .client import ApiClient
from .config import Account, TargetConfig
from .metrics import Recorder


@dataclass
class VU:
    index: int
    account: Account
    client: ApiClient
    recorder: Recorder
    cfg: TargetConfig
    state: dict[str, Any] = field(default_factory=dict)
    ready: bool = False

    @property
    def name(self) -> str:
        return f"vu{self.index}:{self.account.username}"


class Scenario:
    """시나리오 베이스. 필요한 메서드만 오버라이드한다."""

    name = "scenario"
    description = ""

    @classmethod
    def add_args(cls, parser: Any) -> None: ...

    def __init__(self, args: Any) -> None:
        self.args = args

    async def setup(self, vu: VU) -> None: ...

    async def run(self, vu: VU, iteration: int) -> None: ...

    async def teardown(self, vu: VU) -> None: ...

    async def finalize(self, vus: list[VU]) -> dict[str, Any]:
        """전체 VU 종료 후 교차 검증. {검증이름: bool|값} 형태로 돌려주면 리포트 checks 에 들어간다."""
        return {}


class _Gate:
    def __init__(self, parties: int) -> None:
        self._remaining = parties
        self._event = asyncio.Event()

    async def arrive_and_wait(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self._event.set()
        await self._event.wait()


async def run_scenario(
    scenario: Scenario,
    cfg: TargetConfig,
    recorder: Recorder,
    *,
    users: int,
    iterations: int = 1,
    duration_s: float = 0,
    ramp_up_s: float = 0,
    sync_start: bool = True,
) -> tuple[list[VU], dict[str, Any]]:
    if not cfg.accounts:
        raise ValueError("사용할 계정이 없습니다.")
    vus = [
        VU(i, cfg.accounts[i % len(cfg.accounts)], ApiClient(cfg, recorder, cfg.accounts[i % len(cfg.accounts)].username),
           recorder, cfg)
        for i in range(users)
    ]
    gate = _Gate(len(vus)) if sync_start else None
    run_started: dict[str, float] = {}

    async def vu_main(vu: VU) -> None:
        if ramp_up_s > 0 and len(vus) > 1:
            await asyncio.sleep(ramp_up_s * vu.index / (len(vus) - 1))
        try:
            await scenario.setup(vu)
            vu.ready = True
        except Exception as exc:  # setup 실패는 지표에 남기고 해당 VU만 제외
            recorder.add("scenario.setup", 0, 0, False, user=vu.name, error=f"{type(exc).__name__}: {exc}")
        if gate is not None:
            await gate.arrive_and_wait()
        if not vu.ready:
            return
        run_started.setdefault("t", time.perf_counter())
        end = time.perf_counter() + duration_s if duration_s > 0 else None
        i = 0
        try:
            while True:
                if end is not None:
                    if time.perf_counter() >= end:
                        break
                elif i >= iterations:
                    break
                try:
                    await scenario.run(vu, i)
                except Exception as exc:
                    recorder.add("scenario.run", 0, 0, False, user=vu.name, error=f"{type(exc).__name__}: {exc}")
                i += 1
        finally:
            try:
                await scenario.teardown(vu)
            except Exception as exc:
                recorder.add("scenario.teardown", 0, 0, False, user=vu.name, error=f"{type(exc).__name__}: {exc}")

    recorder.reset_clock()
    try:
        await asyncio.gather(*(vu_main(vu) for vu in vus))
        checks = await scenario.finalize(vus)
    finally:
        await asyncio.gather(*(vu.client.aclose() for vu in vus), return_exceptions=True)
    return vus, checks
