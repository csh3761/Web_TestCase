# -*- coding: utf-8 -*-
"""IDS(탐색기 가상 드라이브) 시나리오: smoke(읽기 전용 탐색기 동작 재현).

실제 IDS 탐색기에서 'My Work -> 어떤 폴더' 로 들어가는 동작을 API 호출만으로 재현한다.
전부 조회(읽기 전용) API 라 서버 데이터를 바꾸지 않는다.
"""
from __future__ import annotations

from typing import Any

from ...core.runner import VU, Scenario
from . import auth
from .api import IdsApi

# 탐색기 최상위 3개 작업함 (callAgentFolderMenu.do 의 TOP_ROOT_ID 응답에 들어있는 고정 rid)
WORK_BOXES = [("dept_doc", "Team Work"), ("personal_doc", "My Work"), ("public_doc", "Project Work")]


async def _login(vu: VU) -> IdsApi:
    await auth.login(vu.client, vu.account)
    api = IdsApi(vu.client, vu.account.username)
    vu.state["api"] = api
    return api


class SmokeScenario(Scenario):
    name = "ids_smoke"
    description = "IDS 탐색기 동작 점검: 로그인 -> 최상위 메뉴 -> 작업함별 하위 폴더 -> 문서 목록 (전부 읽기 전용)"
    target = "ids"

    async def setup(self, vu: VU) -> None:
        await _login(vu)

    async def run(self, vu: VU, iteration: int) -> None:
        api: IdsApi = vu.state["api"]
        steps: dict[str, bool] = {}

        top = await api.top_menu()
        steps["menu.top"] = top.ok and isinstance(top.get("list"), list) and len(top.get("list")) > 0

        for rid, label in WORK_BOXES:
            folder_resp = await api.folder_menu(rid)
            steps[f"menu.folder.{rid}"] = folder_resp.ok
            sub_list = folder_resp.get("list") if folder_resp.ok else None
            sub_list = sub_list if isinstance(sub_list, list) else []

            # 작업함 바로 아래 문서 목록 (비어있는 게 정상인 경우도 많음 -> 호출 성공 여부만 확인)
            root_docs = await api.doc_list(rid)
            steps[f"doc.list.{rid}.root"] = root_docs.ok

            if sub_list:
                first = sub_list[0]
                sub_rid = str(first.get("rid", ""))
                if sub_rid:
                    sub_docs = await api.doc_list(sub_rid)
                    steps[f"doc.list.{rid}.subfolder"] = sub_docs.ok

        vu.state.setdefault("steps", []).append(steps)

    async def finalize(self, vus: list[VU]) -> dict[str, Any]:
        merged: dict[str, bool] = {}
        for vu in vus:
            for steps in vu.state.get("steps", []):
                for key, ok in steps.items():
                    merged[key] = merged.get(key, True) and ok
        return {f"step.{k}": v for k, v in merged.items()}


SCENARIOS: dict[str, type[Scenario]] = {SmokeScenario.name: SmokeScenario}
