# -*- coding: utf-8 -*-
"""순수 HTTP API 클라이언트 (브라우저 없음).

- 가상 유저(VU)마다 인스턴스를 하나씩 쓴다: 쿠키 저장소/인증 헤더가 인스턴스별로 분리된다.
- 모든 호출은 논리 이름(name)으로 지표에 기록된다 (예: "upload.chunk").
  경로의 uploadId 같은 가변 값이 지표 키를 흩뜨리지 않게 하기 위함.
- 401을 받으면 on_unauthorized(토큰 갱신) 후 1회 재시도한다. 최종 결과만 지표에 기록하고,
  재시도 발생 횟수는 counters["auth.401_retry"]로 센다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import httpx

from .config import TargetConfig
from .metrics import Recorder


@dataclass
class Resp:
    status: int
    body: Any
    ms: float
    ok: bool
    headers: dict[str, str]

    def get(self, key: str, default: Any = None) -> Any:
        return self.body.get(key, default) if isinstance(self.body, dict) else default


class ApiClient:
    def __init__(self, cfg: TargetConfig, recorder: Recorder, user: str = "") -> None:
        self.cfg = cfg
        self.recorder = recorder
        self.user = user
        self.auth_headers: dict[str, str] = {}
        self.on_unauthorized: Callable[[], Awaitable[None]] | None = None
        self._http = httpx.AsyncClient(
            base_url=cfg.base_url,
            headers=dict(cfg.headers),
            verify=cfg.verify_tls,
            timeout=httpx.Timeout(cfg.timeout_s),
            limits=httpx.Limits(max_connections=cfg.max_connections),
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    @property
    def cookies(self) -> httpx.Cookies:
        return self._http.cookies

    async def request(
        self,
        name: str,
        method: str,
        path: str,
        *,
        json: Any = None,
        content: bytes | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retry_401: bool = True,
        ok_statuses: range | tuple[int, ...] = range(200, 300),
    ) -> Resp:
        """name 으로 지표를 기록하며 호출한다. 네트워크 예외는 status=0 으로 기록하고 Resp 로 돌려준다."""
        url = self.cfg.url(path)
        for attempt in (1, 2):
            merged = {**self.auth_headers, **(headers or {})}
            start = time.perf_counter()
            try:
                response = await self._http.request(method, url, json=json, content=content, params=params, headers=merged)
                status, error = response.status_code, ""
            except httpx.HTTPError as exc:
                response, status, error = None, 0, f"{type(exc).__name__}: {exc}"
            ms = (time.perf_counter() - start) * 1000

            if status == 401 and retry_401 and attempt == 1 and self.on_unauthorized is not None:
                self.recorder.count("auth.401_retry")
                await self.on_unauthorized()
                continue

            body: Any = None
            if response is not None:
                try:
                    body = response.json()
                except ValueError:
                    body = response.text[:500]
            ok = status in ok_statuses
            if not ok and not error:
                error = str(body)[:120]
            self.recorder.add(
                name, status, ms, ok, user=self.user, error=error, nbytes=len(content) if content else 0
            )
            return Resp(status, body, ms, ok, dict(response.headers) if response is not None else {})
        raise AssertionError("unreachable")
