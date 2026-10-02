# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT.parent / "common"))

import explorer_path_test as explorer
import login_session_check as login

from sys_trash import (  # noqa: E402
    DEFAULT_CONFIG,
    USER_TRASH_LIST_API_PATH,
    acknowledge_visible_notice_once,
    append_log_file,
    configure_console_output,
    configure_playwright_browsers_path,
    fetch_trash_items_via_api,
    log_line,
    login_otcs,
    main_frame,
    open_context_menu_on_first_visible_selected_document,
    save_screenshot,
    select_document_checkboxes,
    snapshot_page,
    wait_for_delete_notice_forever,
    wait_for_enter_key,
    wait_for_document_count_change,
)




def runtime_output_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / relative_path
    return PROJECT_ROOT / relative_path


DEFAULT_REPORT = runtime_output_path(r"reports\user_trash_login_report.json")
DEFAULT_LOG = runtime_output_path(r"reports\user_trash_login.log")
DEFAULT_SCREENSHOT = runtime_output_path(r"reports\user_trash_after_open.png")
DEFAULT_SELECTION_SCREENSHOT = runtime_output_path(r"reports\user_trash_after_document_selection.png")
DEFAULT_CONTEXT_MENU_SCREENSHOT = runtime_output_path(r"reports\user_trash_after_context_menu.png")
DEFAULT_DELETE_SCREENSHOT = runtime_output_path(r"reports\user_trash_after_permanent_delete.png")

USER_TRASH_SELECTORS = (
    "a#MENU_000000000002005",
    "#MENU_000000000002005",
)

WORKBOXES = (
    {"value": "u", "index": 0, "name": "my work"},
    {"value": "d", "index": 1, "name": "team work"},
    {"value": "p", "index": 2, "name": "project work"},
)


def write_outputs(args: argparse.Namespace, result: dict[str, Any], lines: list[str]) -> None:
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.log.exists():
        args.log.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


async def wait_before_close(args: argparse.Namespace, lines: list[str]) -> None:
    if args.no_final_enter:
        return
    log_line(lines, "화면 확인 대기: 확인 후 Enter 입력 시 웹을 닫고 종료합니다.", args.log)
    wait_for_enter_key()
    args.final_wait_completed = True


def read_masked_password(prompt: str = "P/W 입력: ") -> str:
    if os.name != "nt":
        import getpass

        return getpass.getpass(prompt).strip()

    import msvcrt

    print(prompt, end="", flush=True)
    chars: list[str] = []
    while True:
        key = msvcrt.getwch()
        if key in {"\r", "\n"}:
            print()
            return "".join(chars).strip()
        if key == "\003":
            raise KeyboardInterrupt
        if key in {"\b", "\x7f"}:
            if chars:
                chars.pop()
                print("\b \b", end="", flush=True)
            continue
        if key in {"\x00", "\xe0"}:
            msvcrt.getwch()
            continue
        chars.append(key)
        print("*", end="", flush=True)


def read_account_from_user(args: argparse.Namespace) -> tuple[login.Account, str]:
    username = (args.username or "").strip()
    password = args.password or ""

    if not username:
        username = input("ID 입력: ").strip()
    if not password:
        password = read_masked_password()

    if not username:
        raise ValueError("ID 값이 비어 있습니다.")
    if not password:
        raise ValueError("P/W 값이 비어 있습니다.")
    return login.Account(user_id=username, user_name=username, department_path=""), password


async def fixed_user_trash_locator(frame: Any) -> tuple[str, Any, dict[str, str]]:
    for selector in USER_TRASH_SELECTORS:
        locator = frame.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=1500)
            info = await locator.evaluate(
                """(node) => ({
                    tag: node.tagName,
                    id: node.getAttribute("id") || "",
                    role: node.getAttribute("role") || "",
                    className: node.getAttribute("class") || "",
                    text: (node.innerText || node.textContent || "").trim(),
                    dataUrl: node.getAttribute("data-url") || "",
                    dataNavi: node.getAttribute("data-navi") || "",
                    menuType: node.getAttribute("menu-type") || ""
                })"""
            )
            return selector, locator, info
        except Exception:
            continue
    raise RuntimeError(f"유저 휴지통 태그를 찾지 못했습니다: {USER_TRASH_SELECTORS}")


async def wait_user_trash_ready(page: Any, timeout_ms: int = 15000) -> dict[str, Any]:
    deadline = datetime.now().timestamp() + timeout_ms / 1000
    last_url = ""
    last_body = ""
    while datetime.now().timestamp() <= deadline:
        frame = await main_frame(page)
        last_url = getattr(frame, "url", "")
        try:
            box = frame.locator("#BOX_GUBUN").first
            if await box.count() > 0:
                await box.wait_for(state="visible", timeout=1000)
                return {"status": "USER_TRASH_READY", "main_frame_url": last_url}
        except Exception:
            pass
        try:
            last_body = (await frame.locator("body").inner_text(timeout=1000)).strip()[:1000]
        except Exception:
            last_body = ""
        await page.wait_for_timeout(300)
    raise RuntimeError(f"유저 휴지통 화면 확인 실패: url={last_url}, body={last_body}")


async def open_user_trash(page: Any) -> dict[str, Any]:
    frame = await main_frame(page)
    selector, locator, info = await fixed_user_trash_locator(frame)
    await locator.scroll_into_view_if_needed(timeout=3000)
    await locator.click(timeout=3000)
    ready = await wait_user_trash_ready(page)
    return {
        "selector": selector,
        "clicked_tag": info,
        **ready,
    }


async def switch_workbox(page: Any, workbox: dict[str, Any]) -> dict[str, Any]:
    frame = await main_frame(page)
    box = frame.locator("#BOX_GUBUN").first
    await box.wait_for(state="visible", timeout=10000)
    options_before = await box.evaluate(
        """(node) => Array.from(node.options).map((option, index) => ({
            index,
            value: option.value,
            text: (option.innerText || option.textContent || "").trim()
        }))"""
    )
    method = "value"
    try:
        await box.select_option(workbox["value"], timeout=3000)
    except Exception:
        method = "index"
        try:
            await box.select_option(index=int(workbox["index"]), timeout=3000)
        except Exception:
            method = "js-index"
            changed = await box.evaluate(
                """(node, index) => {
                    const option = node.options[index];
                    if (!option) {
                        return false;
                    }
                    node.selectedIndex = index;
                    node.value = option.value;
                    node.dispatchEvent(new Event("input", { bubbles: true }));
                    node.dispatchEvent(new Event("change", { bubbles: true }));
                    return true;
                }""",
                int(workbox["index"]),
            )
            if not changed:
                raise RuntimeError(f"#BOX_GUBUN 옵션을 선택하지 못했습니다: {workbox}")
    await page.wait_for_timeout(800)
    selected = await box.evaluate(
        """(node) => {
            const option = node.options[node.selectedIndex];
            return {
                index: node.selectedIndex,
                value: node.value,
                text: option ? (option.innerText || option.textContent || "").trim() : ""
            };
        }"""
    )
    return {
        "status": "WORKBOX_SELECTED",
        "target": workbox,
        "method": method,
        "options": options_before,
        "selected": selected,
    }


DELETE_SUCCESS_PATTERN = re.compile(
    r"complete|completed|success|deleted|permanent\s+delete|삭제\s*(완료|되었습니다|성공)|완전\s*삭제",
    re.IGNORECASE,
)
DELETE_ERROR_PATTERN = re.compile(
    r"fail|failed|error|cannot|unable|실패|오류|에러|불가|권한|취소",
    re.IGNORECASE,
)


async def wait_for_delete_api_notice(api_notices: list[dict[str, Any]], poll_interval: float = 0.2) -> dict[str, Any]:
    """삭제 실행 시 호출되는 POST API 응답(returnMessage)을 무한 대기하며 감지한다.

    DOM에서 알림 요소를 추측하는 대신, 서버가 실제로 반환한 완료 메시지
    (예: {"returnMessage":"삭제 되었습니다."})를 기준으로 판정한다.
    """
    started_at = time.monotonic()
    while True:
        if api_notices:
            notice = api_notices[0]
            text = (notice.get("returnMessage") or "").strip()
            if DELETE_ERROR_PATTERN.search(text):
                status = "DELETE_ERROR_NOTICE_DETECTED"
            elif DELETE_SUCCESS_PATTERN.search(text):
                status = "DELETE_SUCCESS_NOTICE_DETECTED"
            else:
                status = "NOTICE_DETECTED"
            return {
                "status": status,
                "source": "api",
                "waitedMs": int((time.monotonic() - started_at) * 1000),
                "text": text,
                "url": notice.get("url", ""),
            }
        await asyncio.sleep(poll_interval)


async def click_delete_menu_and_confirm(frame: Any, page: Any, timeout_ms: int) -> dict[str, Any]:
    """'Delete' 컨텍스트 메뉴 클릭 + 확인(Ok/Cancel) 모달 클릭까지만 수행한다.

    완료 알림 대기는 포함하지 않는다 - 호출자가 알아서 처리한다. 정식 삭제 흐름
    (click_delete_and_wait_notice)과 alert 감지 진단 테스트가 이 클릭 로직을 공유한다.
    """
    menu_item = await frame.locator("body").evaluate(
        """async (body, { timeoutMs }) => {
            const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
            const startedAt = Date.now();
            const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
            const candidates = [
                ".context-menu-list .context-menu-item",
                ".context-menu-list li",
                "[class*='context'] li",
                "[class*='context'] button",
                "[class*='context'] a"
            ];

            while (Date.now() - startedAt <= timeoutMs) {
                const items = Array.from(document.querySelectorAll(candidates.join(","))).filter(visible);
                const deleteItem = items.find((item) => {
                    const text = (item.innerText || item.textContent || "").replace(/\\s+/g, " ").trim();
                    return /^Delete$/i.test(text) || /^삭제$/.test(text);
                });
                if (deleteItem) {
                    const text = (deleteItem.innerText || deleteItem.textContent || "").replace(/\\s+/g, " ").trim();
                    const box = deleteItem.getBoundingClientRect();
                    return {
                        status: "DELETE_MENU_ITEM_FOUND",
                        waitedMs: Date.now() - startedAt,
                        menuItemText: text,
                        tagName: deleteItem.tagName,
                        className: deleteItem.className || "",
                        x: box.left + box.width / 2,
                        y: box.top + box.height / 2
                    };
                }
                await sleep(150);
            }
            return { status: "DELETE_MENU_NOT_FOUND", waitedMs: Date.now() - startedAt };
        }""",
        {"timeoutMs": timeout_ms},
    )
    if menu_item["status"] != "DELETE_MENU_ITEM_FOUND":
        return {"menu_item": menu_item, "confirm_result": {"status": "SKIPPED"}}

    await page.mouse.click(float(menu_item["x"]), float(menu_item["y"]))
    await page.wait_for_timeout(600)
    confirm_result = await frame.locator("body").evaluate(
        """async (body, { timeoutMs }) => {
            const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
            const startedAt = Date.now();
            const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
            const modalSelectors = [
                ".modal",
                ".swal2-popup",
                ".bootbox",
                "[role='dialog']",
                "[class*='confirm']",
                "[class*='Confirm']"
            ];
            const confirmText = /OK|Ok|확인|예|Yes|Delete|delete|삭제/i;
            const cancelText = /Cancel|취소|아니오|No/i;

            while (Date.now() - startedAt <= timeoutMs) {
                const modals = Array.from(document.querySelectorAll(modalSelectors.join(","))).filter(visible);
                for (const modal of modals) {
                    const modalText = (modal.innerText || modal.textContent || "").replace(/\\s+/g, " ").trim();
                    if (!modalText) {
                        continue;
                    }
                    const buttons = Array.from(modal.querySelectorAll("button, a, input[type='button'], input[type='submit']"))
                        .filter(visible);
                    const confirmButton = buttons.find((button) => {
                        const text = (button.innerText || button.textContent || button.value || "").replace(/\\s+/g, " ").trim();
                        return confirmText.test(text) && !cancelText.test(text);
                    });
                    if (confirmButton) {
                        confirmButton.click();
                        return {
                            status: "DOM_CONFIRM_CLICKED",
                            waitedMs: Date.now() - startedAt,
                            modalText: modalText.slice(0, 1000),
                            buttonText: (confirmButton.innerText || confirmButton.textContent || confirmButton.value || "").replace(/\\s+/g, " ").trim()
                        };
                    }
                    return {
                        status: "DOM_CONFIRM_DETECTED_BUT_BUTTON_NOT_FOUND",
                        waitedMs: Date.now() - startedAt,
                        modalText: modalText.slice(0, 1000)
                    };
                }
                await sleep(150);
            }
            return { status: "DOM_CONFIRM_NOT_DETECTED", waitedMs: Date.now() - startedAt };
        }""",
        {"timeoutMs": timeout_ms},
    )
    # 확인 모달 클릭 직후 DOM에서 아직 안 사라진 잔상을 완료 알림으로 오인하는 것을
    # 막기 위한 짧은 유예(sys_trash.py의 관리자 삭제 흐름과 동일하게 600ms).
    await page.wait_for_timeout(600)
    return {"menu_item": menu_item, "confirm_result": confirm_result}


async def click_delete_and_wait_notice(page: Any, timeout_ms: int) -> dict[str, Any]:
    frame = await main_frame(page)
    dialog_events: list[dict[str, Any]] = []
    api_notices: list[dict[str, Any]] = []

    async def handle_dialog(dialog: Any) -> None:
        dialog_events.append({"type": dialog.type, "message": dialog.message})
        await dialog.accept()

    async def handle_response(response: Any) -> None:
        try:
            if response.request.method != "POST":
                return
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                return
            body = await response.json()
        except Exception:
            return
        if isinstance(body, dict) and "returnMessage" in body:
            api_notices.append(
                {
                    "url": response.url,
                    "status": response.status,
                    "returnMessage": body.get("returnMessage", ""),
                }
            )

    page.on("dialog", handle_dialog)
    page.on("response", handle_response)
    try:
        click_result = await click_delete_menu_and_confirm(frame, page, timeout_ms)
        menu_item = click_result["menu_item"]
        confirm_result = click_result["confirm_result"]
        if menu_item["status"] != "DELETE_MENU_ITEM_FOUND":
            return {
                "status": menu_item["status"],
                "click": menu_item,
                "confirm": {"status": "SKIPPED"},
                "notice": {"status": "SKIPPED"},
                "dialogs": dialog_events,
            }

        # 확인 모달 텍스트를 ignore_text로 넘겨서, 방금 클릭한 확인창 잔상을 완료
        # 알림으로 재검출하지 않도록 한다(실측: seungho.choi 계정 16건 삭제 시 확인
        # 팝업 "Do you want to delete this document? Ok Cancel"을 완료 알림으로
        # 오판한 사례로 확인됨).
        confirm_modal_text = (confirm_result.get("modalText") or "").strip()

        # 삭제 완료/실패 감지는 타임아웃을 두지 않는다 - 서버 처리가 오래 걸려도
        # "못 찾음"으로 포기하지 않고 실제로 신호가 올 때까지 기다린다(무한 대기).
        # POST 삭제 API의 returnMessage(예: "삭제 되었습니다.")와 DOM 알림 요소 중
        # 먼저 감지되는 쪽을 완료 신호로 채택한다 - API 쪽이 더 확실한 근거이므로
        # 우선하되, 화면에 API 응답 없이 DOM 알림만 뜨는 케이스에도 대응한다.
        dom_task = asyncio.ensure_future(
            wait_for_delete_notice_forever(frame, ignore_text=confirm_modal_text or None)
        )
        api_task = asyncio.ensure_future(wait_for_delete_api_notice(api_notices))
        done, pending = await asyncio.wait({dom_task, api_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        notice_result = done.pop().result()

        # API 경로가 DOM보다 먼저 이기면 DOM 작업이 취소되면서, 화면에 실제로 뜬
        # 알림 팝업(예: SweetAlert2 "Alert/Updated/OK")은 아무도 클릭하지 않은 채
        # 남는 문제가 실측으로 확인됐다. 감지 경로와 무관하게 화면에 남은 알림을
        # 몇 초간 재확인하며 OK/확인 버튼을 클릭해서 반드시 닫아준다 - 팝업의
        # 반투명 배경이 남아있으면 다음 업무함 조작(스크롤 등)을 막을 수 있다.
        acknowledge_result = {"status": "NOT_ATTEMPTED", "acknowledged": False}
        for _ in range(15):
            acknowledge_result = await acknowledge_visible_notice_once(frame, ignore_text=confirm_modal_text or None)
            if acknowledge_result.get("acknowledged") or acknowledge_result.get("status") == "NO_VISIBLE_NOTICE":
                break
            await asyncio.sleep(0.3)

        return {
            "status": notice_result["status"],
            "click": {**menu_item, "status": "DELETE_CLICKED"},
            "confirm": confirm_result,
            "notice": notice_result,
            "acknowledge": acknowledge_result,
            "dialogs": dialog_events,
            "api_notices": api_notices,
        }
    finally:
        page.remove_listener("dialog", handle_dialog)
        page.remove_listener("response", handle_response)


def summarize_delete_alert(delete_result: dict[str, Any]) -> dict[str, Any]:
    dialogs = delete_result.get("dialogs") or []
    confirm = delete_result.get("confirm") or {}
    notice = delete_result.get("notice") or {}
    confirm_status = confirm.get("status", "")
    notice_status = notice.get("status", "")

    if dialogs:
        return {
            "status": "JS_DIALOG_ACCEPTED",
            "handled": True,
            "source": "dialog",
            "dialogCount": len(dialogs),
            "confirmStatus": confirm_status,
            "noticeStatus": notice_status,
        }
    if confirm_status == "DOM_CONFIRM_CLICKED":
        return {
            "status": "DOM_CONFIRM_CLICKED",
            "handled": True,
            "source": "dom-confirm",
            "dialogCount": 0,
            "confirmStatus": confirm_status,
            "noticeStatus": notice_status,
        }
    if notice_status in {
        "NOTICE_DETECTED",
        "DELETE_SUCCESS_NOTICE_DETECTED",
        "DELETE_ERROR_NOTICE_DETECTED",
    }:
        return {
            "status": "NOTICE_DETECTED_WITHOUT_CONFIRM",
            "handled": True,
            "source": "notice",
            "dialogCount": 0,
            "confirmStatus": confirm_status,
            "noticeStatus": notice_status,
        }
    return {
        "status": "ALERT_NOT_HANDLED",
        "handled": False,
        "source": "none",
        "dialogCount": 0,
        "confirmStatus": confirm_status,
        "noticeStatus": notice_status,
    }


async def delete_current_workbox_documents(
    page: Any, args: argparse.Namespace, lines: list[str], workbox: dict[str, Any]
) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "UNKNOWN"}

    # count_rows()는 DOM 스냅샷(스크롤 전)이라 실제 건수와 어긋날 수 있음이 관리자
    # 휴지통에서 실측으로 확인됐다(실제 108건인데 8건으로 오판). 그리드가 실제로 호출하는
    # API(/recyclebin/myRecycleBinGrid)를 직접 페이지네이션 호출해 권위있는 전체 건수/
    # 폴더 목록을 확보한다.
    api_listing = await fetch_trash_items_via_api(
        page, box_gubun=str(workbox["value"]).upper(), api_path=USER_TRASH_LIST_API_PATH
    )
    result["api_listing"] = {
        "totalCount": api_listing["totalCount"],
        "documentCount": api_listing["documentCount"],
        "folderCount": api_listing["folderCount"],
        "folderTitles": api_listing["folderTitles"],
    }
    log_line(
        lines,
        (
            f"목록 확인(API 기준): 전체 {api_listing['totalCount']}건 "
            f"문서 {api_listing['documentCount']}건 "
            f"폴더 {api_listing['folderCount']}건"
            + (f" ({', '.join(api_listing['folderTitles'])})" if api_listing["folderTitles"] else "")
        ),
        args.log,
    )

    log_line(lines, "전체 목록 수집 시작: 스크롤 끝까지 로딩 후 문서만 선택합니다.", args.log)
    selection = await select_document_checkboxes(
        page, selection_limit=0, folder_titles=api_listing["folderTitles"]
    )
    result["document_selection"] = selection
    result["after_document_selection_screenshot"] = await save_screenshot(page, args.selection_screenshot)
    log_line(lines, f"문서 수집 완료: {selection.get('collectedCount', 0)}건", args.log)
    log_line(lines, f"문서 선택 완료: {selection['selectedCount']}건", args.log)
    if selection["selectedCount"] != api_listing["documentCount"]:
        log_line(
            lines,
            (
                f"[경고] 선택된 문서 수({selection['selectedCount']}건)가 "
                f"API 기준 문서 수({api_listing['documentCount']}건)와 다릅니다."
            ),
            args.log,
        )
    if selection.get("missingCount", 0) > 0:
        log_line(
            lines,
            (
                f"문서 일부 미선택: 대상 {selection.get('targetCount', 0)}건 / "
                f"선택 {selection['selectedCount']}건 / 미선택 {selection['missingCount']}건"
            ),
            args.log,
        )

    if selection["selectedCount"] == 0:
        result["status"] = "NO_DOCUMENTS_TO_DELETE"
        log_line(lines, "삭제 대상 문서 없음", args.log)
        return result

    if args.select_only:
        result["status"] = "DOCUMENT_SELECTION_VERIFIED"
        log_line(lines, "문서 선택 검증 완료", args.log)
        return result

    log_line(lines, "우클릭 메뉴 열기", args.log)
    context_menu = await open_context_menu_on_first_visible_selected_document(page, args.context_menu_timeout_ms)
    result["context_menu"] = context_menu
    result["after_context_menu_screenshot"] = await save_screenshot(page, args.context_menu_screenshot)
    log_line(lines, f"우클릭 메뉴: {context_menu['status']}", args.log)
    if context_menu["status"] != "CONTEXT_MENU_OPENED":
        raise RuntimeError(f"우클릭 메뉴가 열리지 않아 삭제를 중단합니다: {context_menu['status']}")

    log_line(lines, "Delete 삭제 실행 - 삭제 Alert 감지까지 무한 대기합니다.", args.log)
    delete_result = await click_delete_and_wait_notice(page, args.delete_notice_timeout_ms)
    result["delete_action"] = delete_result
    alert_result = summarize_delete_alert(delete_result)
    result["alert_handling"] = alert_result
    result["after_permanent_delete_screenshot"] = await save_screenshot(page, args.delete_screenshot)
    notice_detail = delete_result.get("notice") or {}
    log_line(
        lines,
        (
            f"Delete 삭제 결과: {delete_result['status']}"
            f" (감지 경로: {notice_detail.get('source', 'unknown')}, 메시지: {notice_detail.get('text', '')!r})"
        ),
        args.log,
    )
    log_line(lines, f"alert 처리 결과: {alert_result['status']}", args.log)
    acknowledge_detail = delete_result.get("acknowledge") or {}
    log_line(
        lines,
        (
            f"알림창 확인 클릭: {acknowledge_detail.get('status', 'UNKNOWN')}"
            f" (버튼: {acknowledge_detail.get('buttonText', '')!r})"
        ),
        args.log,
    )

    # 완료 판정 기준은 "Alert 창 감지" 하나뿐이다(사용자 지정 기준). 문서 건수 재확인은
    # 참고 로그일 뿐 최종 상태를 좌우하지 않는다.
    verify_result = await wait_for_document_count_change(
        page,
        int(selection.get("selectedCount", 0) or 0),
        args.delete_notice_timeout_ms,
    )
    result["delete_verification"] = verify_result
    log_line(
        lines,
        (
            f"[참고] 목록 건수 변화: {verify_result['status']} "
            f"({verify_result['beforeDocumentCount']}건 -> {verify_result['afterDocumentCount']}건)"
        ),
        args.log,
    )
    if delete_result["status"] == "DELETE_ERROR_NOTICE_DETECTED":
        result["status"] = "DELETE_FAILED_NOTICE_DETECTED"
    elif not alert_result["handled"]:
        result["status"] = "DELETE_ALERT_NOT_HANDLED"
    else:
        result["status"] = "DELETE_COMPLETED"
    return result


async def run(args: argparse.Namespace) -> int:
    configure_playwright_browsers_path()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    account, password = read_account_from_user(args)
    lines: list[str] = []
    result: dict[str, Any] = {
        "mode": "USER_TRASH_LOGIN_CHECK",
        "user_id": account.user_id,
        "execute": not args.select_only,
        "action": "delete",
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "workboxes": [],
    }

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
        context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
        page = await context.new_page()
        try:
            log_line(lines, f"유저 휴지통 로그인 시작: {account.user_id}", args.log)
            login_result = await login_otcs(page, account, password, config)
            result.update(login_result)
            result["after_login_snapshot"] = await snapshot_page(page)
            result["main_frame_url"] = getattr(await main_frame(page), "url", "")
            log_line(lines, "유저 휴지통 로그인 성공", args.log)
            log_line(lines, f"로그인 프레임: {result['main_frame_url']}", args.log)

            if args.login_only:
                result["status"] = "LOGIN_OK"
                await wait_before_close(args, lines)
                return 0

            log_line(lines, "유저 휴지통 이동 시작", args.log)
            trash_result = await open_user_trash(page)
            result["trash_navigation"] = trash_result
            result["after_trash_snapshot"] = await snapshot_page(page)
            result["after_trash_screenshot"] = await save_screenshot(page, args.screenshot)
            log_line(lines, "유저 휴지통 이동 성공", args.log)

            for workbox in WORKBOXES:
                log_line(lines, f"{workbox['name']} 선택", args.log)
                workbox_result: dict[str, Any] = {
                    "workbox": workbox,
                    "switch": await switch_workbox(page, workbox),
                }
                try:
                    workbox_result["delete"] = await delete_current_workbox_documents(page, args, lines, workbox)
                except Exception as exc:
                    workbox_result["status"] = "FAILED"
                    workbox_result["message"] = str(exc)
                    result["workboxes"].append(workbox_result)
                    raise
                workbox_result["status"] = workbox_result["delete"]["status"]
                result["workboxes"].append(workbox_result)
                if workbox_result["status"] == "DELETE_ALERT_NOT_HANDLED":
                    raise RuntimeError(f"{workbox['name']} alert 처리가 확인되지 않아 다음 작업함 진행을 중단합니다.")

            statuses = [item.get("status") for item in result["workboxes"]]
            if any(status == "FAILED" for status in statuses):
                result["status"] = "FAILED"
            elif any(status == "DELETE_ALERT_NOT_HANDLED" for status in statuses):
                result["status"] = "DELETE_ALERT_NOT_HANDLED"
            elif any(status == "DELETE_NOT_VERIFIED" for status in statuses):
                result["status"] = "DELETE_NOT_VERIFIED"
            elif any(status == "DELETE_FAILED_NOTICE_DETECTED" for status in statuses):
                result["status"] = "DELETE_FAILED_NOTICE_DETECTED"
            elif any(status == "DELETE_COMPLETED" for status in statuses):
                result["status"] = "DELETE_COMPLETED"
            elif all(status == "NO_DOCUMENTS_TO_DELETE" for status in statuses):
                result["status"] = "NO_DOCUMENTS_TO_DELETE"
            elif all(status == "DOCUMENT_SELECTION_VERIFIED" for status in statuses):
                result["status"] = "DOCUMENT_SELECTION_VERIFIED"
            else:
                result["status"] = "USER_TRASH_DONE"
            log_line(lines, f"최종 결과: {result['status']}", args.log)
            await wait_before_close(args, lines)
            return 0
        except Exception as exc:
            result["status"] = "FAILED"
            result["message"] = str(exc)
            try:
                result["failure_snapshot"] = await snapshot_page(page)
            except Exception:
                pass
            log_line(lines, f"유저 휴지통 실패: {exc}", args.log)
            await wait_before_close(args, lines)
            return 1
        finally:
            await context.close()
            await browser.close()
            write_outputs(args, result, lines)


def main() -> int:
    explorer.configure_console()
    configure_console_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--login-only", action="store_true")
    parser.add_argument("--select-only", action="store_true")
    parser.add_argument("--no-final-enter", action="store_true")
    parser.add_argument("--context-menu-timeout-ms", type=int, default=5000)
    parser.add_argument("--delete-notice-timeout-ms", type=int, default=10000)
    parser.add_argument("--screenshot", type=Path, default=DEFAULT_SCREENSHOT)
    parser.add_argument("--selection-screenshot", type=Path, default=DEFAULT_SELECTION_SCREENSHOT)
    parser.add_argument("--context-menu-screenshot", type=Path, default=DEFAULT_CONTEXT_MENU_SCREENSHOT)
    parser.add_argument("--delete-screenshot", type=Path, default=DEFAULT_DELETE_SCREENSHOT)
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as exc:
        line = f"{datetime.now().isoformat(timespec='seconds')} 치명 오류: {exc}"
        print(line, flush=True)
        append_log_file(args.log, line)
        return 1
    finally:
        if getattr(sys, "frozen", False) and not args.no_final_enter and not getattr(args, "final_wait_completed", False):
            print("\n종료 완료. 로그 확인 후 Enter를 누르면 프롬프트를 종료합니다.")
            wait_for_enter_key()


if __name__ == "__main__":
    raise SystemExit(main())

