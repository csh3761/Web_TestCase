# -*- coding: utf-8 -*-
"""IDS(탐색기 가상 드라이브) 엔드포인트 래퍼.

IDS 데스크탑 클라이언트(Windows 탐색기에 'IDS' 가상 폴더로 보이는 프로그램)가 실제로 호출하는
pcexplorer/*.do API 를 mitmproxy 로 캡처해서 확인한 내용 그대로 재현한다.
  - 전부 application/x-www-form-urlencoded POST (JSON 아님)
  - 세션은 httpx 쿠키 저장소(JSESSIONID)가 자동으로 유지한다
  - user_id 는 매 호출마다 base64(username) 로 보낸다 (헤더가 아니라 매번 body 파라미터로 감)
"""
from __future__ import annotations

import base64
from urllib.parse import urlencode

from ...core.client import ApiClient, Resp

FORM_HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}


def b64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


async def form_request(client: ApiClient, name: str, path: str, payload: dict[str, str], **kwargs) -> Resp:
    body = urlencode(payload).encode("utf-8")
    return await client.request(name, "POST", path, content=body, headers=FORM_HEADERS, **kwargs)


class IdsApi:
    def __init__(self, client: ApiClient, username: str) -> None:
        self.c = client
        self.user_id = b64(username)

    # ---- 탐색기 트리 (읽기 전용)
    async def top_menu(self) -> Resp:
        """최상위 메뉴(Team Work/My Work/Quick Link/공유받은폴더/Project Work/Common Box)."""
        return await form_request(
            self.c, "menu.top", "/main/menu/callAgentFolderMenu.do",
            {"user_id": self.user_id, "rid": "TOP_ROOT_ID"},
        )

    async def folder_menu(self, rid: str) -> Resp:
        """메뉴/폴더 하나의 하위 폴더 목록. rid 는 top_menu 의 rid 값이거나 하위 폴더의 rid."""
        return await form_request(
            self.c, "menu.folder", "/main/menu/callAgentDocFolderMenu.do",
            {"user_id": self.user_id, "rid": rid},
        )

    async def doc_list(self, folder_id: str, page: int = 1, page_line: int = 50000) -> Resp:
        """폴더 안의 문서 목록."""
        return await form_request(
            self.c, "doc.list", "/doc/mydoc/myDocList.do",
            {
                "user_id": self.user_id,
                "r_folder_id": folder_id,
                "_pageNumber": str(page),
                "_pageLineCount": str(page_line),
            },
        )
