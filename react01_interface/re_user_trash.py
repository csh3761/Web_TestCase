# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")).resolve() / relative_path
    return PROJECT_ROOT / relative_path


def runtime_output_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / relative_path
    return PROJECT_ROOT / relative_path


def configure_playwright_browsers_path() -> None:
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        return
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "ms-playwright")
        candidates.append(Path(getattr(sys, "_MEIPASS", "")).resolve() / "ms-playwright")
    candidates.append(Path.cwd() / "ms-playwright")
    for candidate in candidates:
        if candidate.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(candidate)
            return


DEFAULT_CONFIG = resource_path(r"config\react01_login_config.json")
DEFAULT_REPORT = runtime_output_path(r"reports\re_user_trash_login_report.json")
DEFAULT_LOG = runtime_output_path(r"reports\re_user_trash_login.log")
DEFAULT_SELECTION_SCREENSHOT = runtime_output_path(r"reports\re_user_trash_after_selection.png")
DEFAULT_CONTEXT_MENU_SCREENSHOT = runtime_output_path(r"reports\re_user_trash_after_context_menu.png")
DEFAULT_DELETE_SCREENSHOT = runtime_output_path(r"reports\re_user_trash_after_delete.png")


@dataclass(frozen=True)
class Account:
    user_id: str
    user_name: str


def configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(line_buffering=True, write_through=True)
        except Exception:
            pass


def append_log_file(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def log_line(lines: list[str], message: str, log_path: Path | None = None) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}"
    lines.append(line)
    print(line, flush=True)
    if log_path is not None:
        append_log_file(log_path, line)


def write_outputs(args: argparse.Namespace, result: dict[str, Any], lines: list[str]) -> None:
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.log.exists():
        args.log.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def wait_for_enter_key() -> None:
    print("확인 후 Enter: ", end="", flush=True)
    if os.name == "nt":
        import msvcrt

        while True:
            key = msvcrt.getwch()
            if key in {"\r", "\n"}:
                print()
                return
    try:
        input()
    except EOFError:
        print("\n입력 스트림을 사용할 수 없습니다. Ctrl+C로 종료하세요.")
        while True:
            import time

            time.sleep(60)


async def wait_before_close(args: argparse.Namespace, lines: list[str]) -> None:
    if args.no_final_enter:
        return
    log_line(lines, "화면 확인 대기: 확인 후 Enter 입력 시 웹을 닫고 종료합니다.", args.log)
    wait_for_enter_key()
    args.final_wait_completed = True


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


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


def read_account_from_user(args: argparse.Namespace) -> tuple[Account, str]:
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
    return Account(user_id=username, user_name=username), password


async def fill_first_visible(page: Any, selector_list: str, value: str) -> None:
    for selector in [item.strip() for item in selector_list.split(",")]:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=5000)
            await locator.fill(value)
            return
        except Exception:
            continue
    raise RuntimeError(f"입력 가능한 selector를 찾지 못했습니다: {selector_list}")


async def click_first_visible(page: Any, selector_list: str) -> None:
    for selector in [item.strip() for item in selector_list.split(",")]:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=5000)
            await locator.click()
            return
        except Exception:
            continue
    raise RuntimeError(f"클릭 가능한 selector를 찾지 못했습니다: {selector_list}")


async def save_screenshot(page: Any, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(path), full_page=True)
    return str(path)


async def snapshot_page(page: Any) -> dict[str, Any]:
    frames: list[dict[str, Any]] = []
    for frame in page.frames:
        body_text = ""
        try:
            body_text = (await frame.locator("body").inner_text(timeout=1500)).strip()
        except Exception:
            pass
        frames.append({"name": frame.name, "url": frame.url, "body_sample": body_text[:1200]})
    return {"page_url": page.url, "page_title": await page.title(), "frames": frames}


async def login_react01(page: Any, account: Account, password: str, config: dict[str, Any]) -> dict[str, Any]:
    """react01.ifns.devel 도메인 전용 로그인.

    HYNIX의 login_otcs()는 iframe(main_frame) 존재를 전제로 하지만, 이 도메인은
    구조가 아직 확인되지 않은(React SPA로 추정) 별도 사이트이므로 page를 직접
    사용한다. selector는 login_config.json의 값을 참고한 추정치이며, 실제 DOM과
    다르면 --headless false 상태로 직접 화면을 보며 selector를 맞춰야 한다.
    """
    selectors = config["selectors"]
    before_url = page.url
    await page.goto(config["login_url"], wait_until="domcontentloaded")
    await fill_first_visible(page, selectors["username"], account.user_id)
    await fill_first_visible(page, selectors["password"], password)

    response_status = "LOGIN_RESPONSE_NOT_CAPTURED"
    try:
        async with page.expect_response(
            lambda response: "login" in response.url.lower() and response.request.method == "POST",
            timeout=8000,
        ) as response_info:
            await click_first_visible(page, selectors["submit"])
        response = await response_info.value
        response_status = f"LOGIN_RESPONSE:{response.status}"
    except Exception:
        try:
            await page.locator(selectors["password"]).first.press("Enter")
        except Exception:
            pass

    # networkidle은 SPA 폴링 때문에 사실상 타임아웃(15s)을 거의 항상 다 채우므로,
    # 로그인 후에만 나타나는 실제 요소(전사휴지통 링크) 등장을 기다리는 방식으로 대체한다.
    try:
        await page.locator(
            selectors.get("enterprise_trash", "a[href='/enterprise-trash']")
        ).first.wait_for(state="visible", timeout=8000)
    except Exception:
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass

    return {
        "login_response_status": response_status,
        "before_url": before_url,
        "page_url": page.url,
        "navigated": page.url != before_url,
    }


async def open_enterprise_trash(page: Any, config: dict[str, Any]) -> dict[str, Any]:
    """로그인 후 홈 화면의 '전사휴지통' 카드를 클릭해 /enterprise-trash로 이동한다.

    probe_react01_menu.py로 확인한 결과, 이 링크는 iframe 밖 최상위 문서에 있고
    href="/enterprise-trash"가 가장 안정적인 기준이다(class는 유틸리티 클래스라
    리팩터링에 취약하고, id/aria-label은 없음).
    """
    selectors = config["selectors"]
    selector = selectors.get("enterprise_trash", "a[href='/enterprise-trash']")
    expected_path = config.get("enterprise_trash_path", "/enterprise-trash")
    before_url = page.url

    await click_first_visible(page, selector)

    navigated = False
    try:
        await page.wait_for_url(f"**{expected_path}**", timeout=10000)
        navigated = True
    except Exception:
        navigated = expected_path in page.url

    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    return {
        "status": "ENTERPRISE_TRASH_OPENED" if navigated else "ENTERPRISE_TRASH_NAVIGATION_NOT_CONFIRMED",
        "selector": selector,
        "before_url": before_url,
        "page_url": page.url,
    }


ROW_SELECTOR = ".explorer-file-table__row"
ROW_NAME_CELL_SELECTOR = ".explorer-file-table__cell--name"
SELECTED_ROW_SELECTOR = ".explorer-file-table__row.is-selected"
PERMANENT_DELETE_LABEL = "완전삭제(엔진삭제)"  # 공백 제거 후 비교 기준 (원문: "완전삭제(엔진 삭제)")

COUNT_ROWS_SCRIPT = """() => {
    const rows = Array.from(document.querySelectorAll('.explorer-file-table__row'));
    return {
        totalRows: rows.length,
        selectedRows: rows.filter((row) => row.className.includes('is-selected')).length,
    };
}"""

READ_TOTAL_COUNT_SCRIPT = """() => {
    const text = document.body.innerText || "";
    const match = text.match(/\\uCD1D\\s*([0-9,]+)\\s*\\uAC74/);
    return match ? parseInt(match[1].replace(/,/g, ""), 10) : null;
}"""

FIND_LEAF_TEXT_SCRIPT = """async ({ targetText, timeoutMs }) => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, "");
    const startedAt = Date.now();
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    while (Date.now() - startedAt <= timeoutMs) {
        const all = Array.from(document.querySelectorAll("*"));
        const match = all.find((node) =>
            node.children.length === 0 &&
            visible(node) &&
            cleanText(node.innerText || node.textContent || "") === targetText
        );
        if (match) {
            const box = match.getBoundingClientRect();
            return {
                status: "FOUND",
                tagName: match.tagName,
                className: match.className || "",
                x: box.left + box.width / 2,
                y: box.top + box.height / 2,
            };
        }
        await sleep(150);
    }
    return { status: "NOT_FOUND" };
}"""

DOM_CONFIRM_SCRIPT = """async (timeoutMs) => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const startedAt = Date.now();
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const modalSelectors = [
        "[role='alertdialog']",
        "[role='dialog']",
        "[data-state='open']",
        ".modal",
        "[class*='dialog']",
        "[class*='Dialog']",
    ];
    const confirmText = /OK|Ok|\\uD655\\uC778|\\uC608|Yes|Delete|delete|\\uC0AD\\uC81C/i;
    const cancelText = /Cancel|\\uCDE8\\uC18C|\\uC544\\uB2C8\\uC624|No/i;
    while (Date.now() - startedAt <= timeoutMs) {
        const modals = Array.from(document.querySelectorAll(modalSelectors.join(","))).filter(visible);
        for (const modal of modals) {
            const modalText = (modal.innerText || modal.textContent || "").replace(/\\s+/g, " ").trim();
            if (!modalText) continue;
            const buttons = Array.from(
                modal.querySelectorAll("button, a, input[type='button'], input[type='submit']")
            ).filter(visible);
            const confirmButton = buttons.find((button) => {
                const text = (button.innerText || button.textContent || button.value || "").replace(/\\s+/g, " ").trim();
                return confirmText.test(text) && !cancelText.test(text);
            });
            if (confirmButton) {
                confirmButton.click();
                return {
                    status: "DOM_CONFIRM_CLICKED",
                    modalText: modalText.slice(0, 1000),
                    buttonText: (confirmButton.innerText || confirmButton.textContent || confirmButton.value || "")
                        .replace(/\\s+/g, " ")
                        .trim(),
                };
            }
            return { status: "DOM_CONFIRM_DETECTED_BUT_BUTTON_NOT_FOUND", modalText: modalText.slice(0, 1000) };
        }
        await sleep(150);
    }
    return { status: "DOM_CONFIRM_NOT_DETECTED" };
}"""

NOTICE_SCRIPT = """async (timeoutMs) => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const startedAt = Date.now();
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const noticeSelectors = [
        "[class*='toast']",
        "[class*='Toast']",
        "[role='alert']",
        "[aria-live]",
        "[class*='notification']",
        "[class*='message']",
    ];
    while (Date.now() - startedAt <= timeoutMs) {
        const notices = Array.from(document.querySelectorAll(noticeSelectors.join(","))).filter((el) => {
            if (!visible(el)) return false;
            const text = (el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim();
            return text.length > 0;
        });
        if (notices.length) {
            const notice = notices[0];
            const text = (notice.innerText || notice.textContent || "").replace(/\\s+/g, " ").trim().slice(0, 500);
            const loadingPattern = /불러오는|로딩|Loading|처리\\s*중|삭제\\s*중|진행\\s*중/i;
            if (loadingPattern.test(text)) {
                // 로딩/진행 중 표시는 최종 알림이 아니므로 계속 대기한다.
                await sleep(200);
                continue;
            }
            const successPattern = /complete|completed|success|deleted|\\uC0AD\\uC81C\\s*(\\uC644\\uB8CC|\\uB418\\uC5C8\\uC2B5\\uB2C8\\uB2E4|\\uC131\\uACF5)/i;
            const errorPattern = /fail|failed|error|cannot|unable|\\uC2E4\\uD328|\\uC624\\uB958|\\uC5D0\\uB7EC|\\uBD88\\uAC00|\\uAD8C\\uD55C/i;
            let status = "NOTICE_DETECTED";
            if (errorPattern.test(text)) {
                status = "DELETE_ERROR_NOTICE_DETECTED";
            } else if (successPattern.test(text)) {
                status = "DELETE_SUCCESS_NOTICE_DETECTED";
            }
            return { status, text };
        }
        await sleep(200);
    }
    return { status: "NOTICE_NOT_DETECTED" };
}"""


async def select_rows_on_current_page(page: Any, limit: int = 0) -> dict[str, Any]:
    """현재 페이지의 행을 선택한다.

    `limit<=0`이면 첫 행 클릭 -> 마지막 행 Shift+클릭으로 페이지 전체를 선택하고,
    `limit>0`이면 첫 행부터 `limit`번째 행까지만 Shift+클릭으로 선택한다
    (`limit=1`이면 첫 행 단일 클릭만 수행 - 실삭제 테스트용 임시 안전 모드).

    probe_enterprise_trash_select2.py로 검증: 단일 클릭은 교체 선택(1건),
    Shift+클릭은 첫 클릭 지점부터 대상까지 범위 선택이 된다.
    """
    rows = page.locator(ROW_SELECTOR)
    row_count = await rows.count()
    if row_count == 0:
        return {"status": "NO_ROWS_ON_PAGE", "rowCount": 0, "selectedCount": 0, "targetCount": 0}

    target_index = row_count - 1 if limit <= 0 or limit > row_count else limit - 1
    target_count = target_index + 1

    first_name = rows.first.locator(ROW_NAME_CELL_SELECTOR).first
    await first_name.scroll_into_view_if_needed(timeout=5000)
    await first_name.click(timeout=5000)

    if target_index > 0:
        target_name = rows.nth(target_index).locator(ROW_NAME_CELL_SELECTOR).first
        await target_name.scroll_into_view_if_needed(timeout=5000)
        await target_name.click(modifiers=["Shift"], timeout=5000)

    counts = await page.evaluate(COUNT_ROWS_SCRIPT)
    status = (
        "TARGET_ROWS_SELECTED"
        if counts["selectedRows"] == target_count and target_count > 0
        else "PARTIAL_SELECTION"
        if counts["selectedRows"] > 0
        else "NO_ROWS_SELECTED"
    )
    return {
        "status": status,
        "rowCount": counts["totalRows"],
        "targetCount": target_count,
        "selectedCount": counts["selectedRows"],
    }


async def open_context_menu_on_selected_row(page: Any) -> dict[str, Any]:
    """선택된 행 중 하나를 화면 안으로 스크롤한 뒤 그 위에서 우클릭한다.

    이전 실행에서 Shift+클릭으로 목록이 맨 아래까지 스크롤된 상태였는데, 화면 밖으로
    벗어난 첫 행의 예전(stale) 좌표로 우클릭해 목록이 아닌 엉뚱한 위치를 클릭하는
    문제가 있었다. 반드시 우클릭 직전에 scroll_into_view_if_needed()로 대상 행을
    뷰포트 안에 넣고, 그 시점의 bounding_box를 새로 읽어 실제 행 위에서 우클릭한다.
    """
    selected_rows = page.locator(SELECTED_ROW_SELECTOR)
    count = await selected_rows.count()
    if count == 0:
        return {"status": "NO_SELECTED_ROW"}

    target_row = selected_rows.first
    await target_row.scroll_into_view_if_needed(timeout=5000)
    await page.wait_for_timeout(150)
    box = await target_row.bounding_box()
    if not box:
        return {"status": "NO_BOUNDING_BOX"}

    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    await page.mouse.move(x, y)
    await page.mouse.click(x, y, button="right")
    return {"status": "RIGHT_CLICKED", "x": x, "y": y}


async def find_permanent_delete_menu_item(page: Any, timeout_ms: int) -> dict[str, Any]:
    return await page.evaluate(FIND_LEAF_TEXT_SCRIPT, {"targetText": PERMANENT_DELETE_LABEL, "timeoutMs": timeout_ms})


async def wait_for_total_count_change(page: Any, before_count: int | None, timeout_ms: int) -> dict[str, Any]:
    """'총 N건' 표시가 실제로 줄어들 때까지 폴링한다.

    30건 일괄삭제 검증 중, 토스트가 "불러오는 중" 같은 로딩 상태를 먼저 보여주고
    실제 처리는 더 걸리는 경우가 있어(1건 삭제는 빨라서 우연히 통과) 알림 텍스트
    하나만으로 판정하지 않고, 서버가 실제로 건수를 반영할 때까지 직접 재확인한다.
    """
    started = datetime.now()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(1, timeout_ms / 1000)
    last_count = before_count
    while loop.time() <= deadline:
        current = await page.evaluate(READ_TOTAL_COUNT_SCRIPT)
        last_count = current
        if before_count is not None and current is not None and current < before_count:
            return {
                "status": "TOTAL_COUNT_DECREASED",
                "beforeCount": before_count,
                "afterCount": current,
                "waitedMs": int((datetime.now() - started).total_seconds() * 1000),
            }
        await page.wait_for_timeout(700)
    return {
        "status": "TOTAL_COUNT_NOT_CHANGED",
        "beforeCount": before_count,
        "afterCount": last_count,
        "waitedMs": int((datetime.now() - started).total_seconds() * 1000),
    }


async def run_single_delete_cycle(
    page: Any,
    args: argparse.Namespace,
    lines: list[str],
    cycle_label: str,
) -> dict[str, Any]:
    """현재 페이지에서 '전체선택 -> 우클릭 -> 완전삭제(엔진 삭제)' 한 사이클을 실행한다.

    --loop-until-empty 모드에서 페이지가 자동 리필되는 현재 페이지를 대상으로
    반복 호출된다(probe로 확인: 삭제 후 같은 화면에 다음 배치가 채워짐).
    """
    cycle: dict[str, Any] = {"cycle": cycle_label}

    total_before = await page.evaluate(READ_TOTAL_COUNT_SCRIPT)
    cycle["total_count_before"] = total_before
    log_line(lines, f"[{cycle_label}] 삭제 전 총 건수: {total_before}", args.log)

    selection = await select_rows_on_current_page(page, limit=args.selection_limit)
    cycle["selection"] = selection
    log_line(
        lines,
        f"[{cycle_label}] 선택 결과: {selection['status']} "
        f"({selection['selectedCount']}/{selection.get('targetCount', selection['rowCount'])}건, "
        f"페이지 전체 {selection['rowCount']}건)",
        args.log,
    )

    if selection["selectedCount"] == 0:
        cycle["status"] = "NO_DOCUMENTS_TO_DELETE"
        log_line(lines, f"[{cycle_label}] 삭제 대상 없음", args.log)
        return cycle

    context_open = await open_context_menu_on_selected_row(page)
    cycle["context_menu_open"] = context_open
    log_line(lines, f"[{cycle_label}] 우클릭 결과: {context_open['status']}", args.log)
    if context_open["status"] != "RIGHT_CLICKED":
        cycle["status"] = "RIGHT_CLICK_FAILED"
        return cycle

    menu_item = await find_permanent_delete_menu_item(page, args.context_menu_timeout_ms)
    cycle["delete_menu_item"] = menu_item
    log_line(lines, f"[{cycle_label}] '완전삭제(엔진 삭제)' 메뉴 탐지: {menu_item['status']}", args.log)
    if menu_item["status"] != "FOUND":
        cycle["status"] = "DELETE_MENU_NOT_FOUND"
        return cycle

    log_line(lines, f"[{cycle_label}] 완전삭제(엔진 삭제) 클릭 실행", args.log)
    dialog_events: list[dict[str, Any]] = []

    async def handle_dialog(dialog: Any) -> None:
        dialog_events.append({"type": dialog.type, "message": dialog.message})
        await dialog.accept()

    page.on("dialog", handle_dialog)
    try:
        await page.mouse.click(menu_item["x"], menu_item["y"])
        await page.wait_for_timeout(600)
        confirm_result = await page.evaluate(DOM_CONFIRM_SCRIPT, 3000)
        cycle["confirm"] = confirm_result
        log_line(lines, f"[{cycle_label}] 확인창 처리: {confirm_result['status']}", args.log)
        notice_result = await page.evaluate(NOTICE_SCRIPT, args.delete_notice_timeout_ms)
        cycle["notice"] = notice_result
        cycle["dialogs"] = dialog_events
        log_line(lines, f"[{cycle_label}] 알림 감지: {notice_result['status']}", args.log)
    finally:
        page.remove_listener("dialog", handle_dialog)

    log_line(lines, f"[{cycle_label}] 총 건수 감소 대기 (최대 {args.delete_verify_timeout_ms}ms)", args.log)
    verify_result = await wait_for_total_count_change(page, total_before, args.delete_verify_timeout_ms)
    cycle["count_verification"] = verify_result
    total_after = verify_result["afterCount"]
    cycle["total_count_after"] = total_after
    log_line(
        lines,
        f"[{cycle_label}] 건수 확인: {verify_result['status']} ({verify_result['waitedMs']}ms 대기)",
        args.log,
    )

    if notice_result["status"] == "DELETE_ERROR_NOTICE_DETECTED":
        cycle["status"] = "DELETE_FAILED_NOTICE_DETECTED"
    elif verify_result["status"] == "TOTAL_COUNT_DECREASED":
        cycle["status"] = "DELETE_COMPLETED"
    else:
        cycle["status"] = "DELETE_NOT_VERIFIED"

    log_line(
        lines,
        f"[{cycle_label}] 사이클 결과: {cycle['status']} (총 {total_before}건 -> {total_after}건)",
        args.log,
    )
    return cycle


async def run_delete_all_loop(page: Any, args: argparse.Namespace, lines: list[str]) -> dict[str, Any]:
    """목록이 빌 때까지(또는 안전 한도까지) 삭제 사이클을 반복한다."""
    cycles: list[dict[str, Any]] = []
    cycle_index = 1
    final_total: int | None = None

    while True:
        current_total = await page.evaluate(READ_TOTAL_COUNT_SCRIPT)
        if current_total is not None and current_total <= 0:
            final_total = current_total
            log_line(lines, "총 건수 0건 확인 -> 루프 종료", args.log)
            break

        row_count = await page.locator(ROW_SELECTOR).count()
        if row_count == 0:
            final_total = current_total
            log_line(lines, "페이지에 남은 행이 없음 -> 루프 종료", args.log)
            break

        if cycle_index > args.max_cycles:
            final_total = current_total
            log_line(lines, f"최대 반복 횟수({args.max_cycles}) 도달 -> 루프 중단", args.log)
            break

        cycle_label = f"cycle-{cycle_index}"
        cycle_result = await run_single_delete_cycle(page, args, lines, cycle_label)
        cycles.append(cycle_result)

        if cycle_result["status"] != "DELETE_COMPLETED":
            final_total = cycle_result.get("total_count_after", current_total)
            log_line(lines, f"[{cycle_label}] 실패/미검증 상태로 루프 중단: {cycle_result['status']}", args.log)
            break

        final_total = cycle_result.get("total_count_after")
        cycle_index += 1

    return {"cycles": cycles, "final_total_count": final_total, "cycles_run": len(cycles)}


async def run(args: argparse.Namespace) -> int:
    configure_playwright_browsers_path()
    config = load_json(args.config)
    account, password = read_account_from_user(args)
    lines: list[str] = []
    result: dict[str, Any] = {
        "mode": "RE_USER_TRASH_ENTERPRISE_DELETE",
        "user_id": account.user_id,
        "execute": args.execute,
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
        context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
        page = await context.new_page()
        try:
            log_line(lines, f"로그인 시작: {account.user_id}", args.log)
            login_result = await login_react01(page, account, password, config)
            result.update(login_result)
            result["after_login_snapshot"] = await snapshot_page(page)
            log_line(lines, f"로그인 완료: {login_result['login_response_status']}", args.log)
            log_line(lines, f"현재 페이지: {result['page_url']}", args.log)

            if args.login_only:
                result["status"] = "LOGIN_OK"
                await wait_before_close(args, lines)
                return 0

            log_line(lines, "전사휴지통 이동 시작", args.log)
            trash_result = await open_enterprise_trash(page, config)
            result["enterprise_trash_navigation"] = trash_result
            log_line(lines, f"전사휴지통 이동 결과: {trash_result['status']} ({trash_result['page_url']})", args.log)
            if trash_result["status"] != "ENTERPRISE_TRASH_OPENED":
                result["status"] = trash_result["status"]
                result["after_navigation_snapshot"] = await snapshot_page(page)
                await wait_before_close(args, lines)
                return 1

            if args.open_trash_only:
                result["status"] = "ENTERPRISE_TRASH_OPENED"
                await wait_before_close(args, lines)
                return 0

            if args.loop_until_empty:
                if args.selection_limit != 0:
                    log_line(
                        lines,
                        f"--loop-until-empty 모드: --selection-limit {args.selection_limit} 대신 "
                        "0(페이지 전체)을 사용합니다.",
                        args.log,
                    )
                    args.selection_limit = 0
                await page.wait_for_timeout(1000)
                log_line(lines, "전체 삭제 루프 시작 (목록이 빌 때까지 반복)", args.log)
                loop_result = await run_delete_all_loop(page, args, lines)
                result["delete_cycles"] = loop_result["cycles"]
                result["total_cycles_run"] = loop_result["cycles_run"]
                result["final_total_count"] = loop_result["final_total_count"]
                result["after_delete_screenshot"] = await save_screenshot(page, args.delete_screenshot)

                if loop_result["final_total_count"] == 0:
                    result["status"] = "DELETE_ALL_COMPLETED"
                else:
                    result["status"] = "DELETE_ALL_STOPPED_EARLY"

                log_line(
                    lines,
                    f"전체 삭제 루프 종료: {result['status']} "
                    f"(사이클 {loop_result['cycles_run']}회, 최종 총 건수 {loop_result['final_total_count']})",
                    args.log,
                )
                await wait_before_close(args, lines)
                return 0 if result["status"] == "DELETE_ALL_COMPLETED" else 1

            await page.wait_for_timeout(1000)
            total_before = await page.evaluate(READ_TOTAL_COUNT_SCRIPT)
            result["total_count_before"] = total_before
            log_line(lines, f"삭제 전 총 건수: {total_before}", args.log)

            selection_label = "전체" if args.selection_limit <= 0 else f"{args.selection_limit}건 한정"
            log_line(lines, f"현재 페이지 선택 시작 ({selection_label})", args.log)
            selection = await select_rows_on_current_page(page, limit=args.selection_limit)
            result["selection"] = selection
            log_line(
                lines,
                f"선택 결과: {selection['status']} "
                f"({selection['selectedCount']}/{selection.get('targetCount', selection['rowCount'])}건, "
                f"페이지 전체 {selection['rowCount']}건)",
                args.log,
            )
            result["after_selection_screenshot"] = await save_screenshot(page, args.selection_screenshot)

            if selection["selectedCount"] == 0:
                result["status"] = "NO_DOCUMENTS_TO_DELETE"
                log_line(lines, "삭제 대상 없음", args.log)
                await wait_before_close(args, lines)
                return 0

            if args.select_only:
                result["status"] = "DOCUMENT_SELECTION_VERIFIED"
                log_line(lines, "선택 검증 완료 (--select-only)", args.log)
                await wait_before_close(args, lines)
                return 0

            log_line(lines, "선택된 행 위에서 우클릭", args.log)
            context_open = await open_context_menu_on_selected_row(page)
            result["context_menu_open"] = context_open
            log_line(lines, f"우클릭 결과: {context_open['status']}", args.log)
            if context_open["status"] != "RIGHT_CLICKED":
                raise RuntimeError(f"목록 안의 선택된 행 위에서 우클릭하지 못했습니다: {context_open['status']}")

            menu_item = await find_permanent_delete_menu_item(page, args.context_menu_timeout_ms)
            result["delete_menu_item"] = menu_item
            log_line(lines, f"'완전삭제(엔진 삭제)' 메뉴 탐지: {menu_item['status']}", args.log)
            result["context_menu_screenshot"] = await save_screenshot(page, args.context_menu_screenshot)

            if menu_item["status"] != "FOUND":
                raise RuntimeError(f"'완전삭제(엔진 삭제)' 메뉴 항목을 찾지 못했습니다: {menu_item['status']}")

            if not args.execute:
                await page.keyboard.press("Escape")
                result["status"] = "DELETE_MENU_VERIFIED"
                log_line(lines, "실행(--execute) 옵션이 없어 클릭하지 않고 메뉴를 닫습니다.", args.log)
                await wait_before_close(args, lines)
                return 0

            log_line(lines, "완전삭제(엔진 삭제) 클릭 실행", args.log)
            dialog_events: list[dict[str, Any]] = []

            async def handle_dialog(dialog: Any) -> None:
                dialog_events.append({"type": dialog.type, "message": dialog.message})
                await dialog.accept()

            page.on("dialog", handle_dialog)
            try:
                await page.mouse.click(menu_item["x"], menu_item["y"])
                await page.wait_for_timeout(600)
                confirm_result = await page.evaluate(DOM_CONFIRM_SCRIPT, 3000)
                result["confirm"] = confirm_result
                log_line(lines, f"확인창 처리: {confirm_result['status']}", args.log)
                notice_result = await page.evaluate(NOTICE_SCRIPT, args.delete_notice_timeout_ms)
                result["notice"] = notice_result
                result["dialogs"] = dialog_events
                log_line(lines, f"알림 감지: {notice_result['status']}", args.log)
            finally:
                page.remove_listener("dialog", handle_dialog)

            result["after_delete_screenshot"] = await save_screenshot(page, args.delete_screenshot)

            log_line(lines, f"총 건수 감소 대기 (최대 {args.delete_verify_timeout_ms}ms)", args.log)
            verify_result = await wait_for_total_count_change(page, total_before, args.delete_verify_timeout_ms)
            result["count_verification"] = verify_result
            total_after = verify_result["afterCount"]
            result["total_count_after"] = total_after
            log_line(
                lines,
                f"건수 확인: {verify_result['status']} ({verify_result['waitedMs']}ms 대기)",
                args.log,
            )

            if notice_result["status"] == "DELETE_ERROR_NOTICE_DETECTED":
                result["status"] = "DELETE_FAILED_NOTICE_DETECTED"
            elif verify_result["status"] == "TOTAL_COUNT_DECREASED":
                result["status"] = "DELETE_COMPLETED"
            else:
                result["status"] = "DELETE_NOT_VERIFIED"

            log_line(
                lines,
                f"최종 결과: {result['status']} (총 {total_before}건 -> {total_after}건)",
                args.log,
            )
            await wait_before_close(args, lines)
            return 0 if result["status"] == "DELETE_COMPLETED" else 1
        except Exception as exc:
            result["status"] = "FAILED"
            result["message"] = str(exc)
            try:
                result["failure_snapshot"] = await snapshot_page(page)
            except Exception:
                pass
            log_line(lines, f"실패: {exc}", args.log)
            await wait_before_close(args, lines)
            return 1
        finally:
            await context.close()
            await browser.close()
            write_outputs(args, result, lines)


def main() -> int:
    configure_console_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--login-only", action="store_true")
    parser.add_argument("--open-trash-only", action="store_true")
    parser.add_argument("--select-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--loop-until-empty",
        action="store_true",
        help="--execute와 함께 사용: 목록(총 건수)이 0이 될 때까지 현재 페이지에서 "
        "전체선택 -> 우클릭 -> 완전삭제를 반복한다 (페이지는 자동 리필됨).",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=60,
        help="--loop-until-empty 안전 한도 (사이클 반복 최대 횟수)",
    )
    parser.add_argument(
        "--selection-limit",
        type=int,
        default=1,
        help="현재 페이지에서 선택할 행 수 (기본값 1 = 임시 안전 모드, 0이면 페이지 전체 선택)",
    )
    parser.add_argument("--context-menu-timeout-ms", type=int, default=5000)
    parser.add_argument("--delete-notice-timeout-ms", type=int, default=10000)
    parser.add_argument(
        "--delete-verify-timeout-ms",
        type=int,
        default=30000,
        help="삭제 후 총 건수 감소를 확인할 때까지 최대 대기 시간 (일괄삭제는 시간이 더 걸릴 수 있음)",
    )
    parser.add_argument("--selection-screenshot", type=Path, default=DEFAULT_SELECTION_SCREENSHOT)
    parser.add_argument("--context-menu-screenshot", type=Path, default=DEFAULT_CONTEXT_MENU_SCREENSHOT)
    parser.add_argument("--delete-screenshot", type=Path, default=DEFAULT_DELETE_SCREENSHOT)
    parser.add_argument("--no-final-enter", action="store_true")
    args = parser.parse_args()
    if args.loop_until_empty and not args.execute:
        print("--loop-until-empty 옵션은 --execute와 함께 사용해야 합니다.", flush=True)
        return 1
    try:
        return asyncio.run(run(args))
    except Exception as exc:
        line = f"{datetime.now().isoformat(timespec='seconds')} 치명 오류: {exc}"
        print(line, flush=True)
        append_log_file(args.log, line)
        return 1
    finally:
        if (
            getattr(sys, "frozen", False)
            and not args.no_final_enter
            and not getattr(args, "final_wait_completed", False)
        ):
            print("\n프로그램 종료 대기: 로그 확인 후 'Enter'를 누르세요.")
            wait_for_enter_key()


if __name__ == "__main__":
    raise SystemExit(main())
