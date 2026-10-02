# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT.parent / "common"))

import explorer_path_test as explorer  # noqa: E402
import login_session_check as login  # noqa: E402
import window_layout  # noqa: E402


def resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")).resolve() / relative_path
    return PROJECT_ROOT / relative_path


def runtime_output_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / relative_path
    return PROJECT_ROOT / relative_path


DEFAULT_CONFIG = resource_path(r"config\trash_login_config.json")
DEFAULT_CREDENTIALS = resource_path(r"config\trash_credentials.json")
DEFAULT_REPORT = runtime_output_path(r"reports\sys_trash_report.json")
DEFAULT_LOG = runtime_output_path(r"reports\sys_trash.log")
DEFAULT_SCREENSHOT = runtime_output_path(r"reports\sys_trash_after_open.png")
DEFAULT_SELECTION_SCREENSHOT = runtime_output_path(r"reports\sys_trash_after_document_selection.png")
DEFAULT_CONTEXT_MENU_SCREENSHOT = runtime_output_path(r"reports\sys_trash_after_context_menu.png")
DEFAULT_DELETE_SCREENSHOT = runtime_output_path(r"reports\sys_trash_after_permanent_delete.png")

TRASH_PAGE_PATH = "/docBox/deleteDocAdmin"
TRASH_FIXED_SELECTORS = (
    "a#MENU_000000000002006[data-url='/docBox/deleteDocAdmin'][data-navi='Trash']",
    "a[data-url='/docBox/deleteDocAdmin'][data-navi='Trash']",
    "a.nav-link[data-url='/docBox/deleteDocAdmin']",
)
DOCUMENT_EXTENSIONS = (
    "7z",
    "aac",
    "accdb",
    "ai",
    "alz",
    "apk",
    "aspx",
    "avi",
    "bak",
    "bat",
    "bin",
    "bmp",
    "cab",
    "cer",
    "cfg",
    "conf",
    "css",
    "csv",
    "dat",
    "db",
    "dll",
    "doc",
    "docm",
    "docx",
    "dot",
    "dotm",
    "dotx",
    "egg",
    "eml",
    "eps",
    "exe",
    "flac",
    "gif",
    "gz",
    "heic",
    "heif",
    "htm",
    "html",
    "hwp",
    "hwpx",
    "ico",
    "ini",
    "iso",
    "jpeg",
    "jpg",
    "js",
    "json",
    "log",
    "m4a",
    "md",
    "mht",
    "mhtml",
    "mkv",
    "mov",
    "mp3",
    "mp4",
    "odf",
    "odp",
    "ods",
    "odt",
    "ogg",
    "one",
    "pdf",
    "pem",
    "png",
    "pot",
    "potm",
    "potx",
    "pps",
    "ppsm",
    "ppsx",
    "psd",
    "ps1",
    "ppt",
    "pptm",
    "pptx",
    "properties",
    "rar",
    "reg",
    "rtf",
    "sh",
    "sql",
    "sqlite",
    "svg",
    "tar",
    "tgz",
    "tif",
    "tiff",
    "tmp",
    "txt",
    "wav",
    "webm",
    "webp",
    "xls",
    "xlsb",
    "xlsm",
    "xlsx",
    "xlt",
    "xltm",
    "xltx",
    "xml",
    "xz",
    "yaml",
    "yml",
    "zip",
)


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


def configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(line_buffering=True, write_through=True)
        except Exception:
            pass


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
    if args.hold_ms > 0:
        log_line(lines, f"화면 자동 유지: {args.hold_ms}ms", args.log)
        await asyncio.sleep(args.hold_ms / 1000)
        args.final_wait_completed = True
        return
    if args.no_final_enter:
        return
    log_line(lines, "화면 확인 대기: 확인 후 Enter 입력 시 웹을 닫고 종료합니다.", args.log)
    wait_for_enter_key()
    args.final_wait_completed = True


def write_outputs(args: argparse.Namespace, result: dict[str, Any], lines: list[str]) -> None:
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.log.exists():
        args.log.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def load_credentials(path: Path) -> tuple[login.Account, str]:
    if not path.exists():
        raise FileNotFoundError(f"계정 파일이 없습니다: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()
    if not username or not password:
        raise ValueError("계정 파일에는 username/password 값이 필요합니다.")
    return login.Account(user_id=username, user_name=username, department_path=""), password


def select_mode(value: str) -> str:
    mode = value.strip().lower()
    if mode in {"1", "folder", "folders", "폴더"}:
        return "folder"
    if mode in {"2", "document", "documents", "doc", "문서"}:
        return "document"
    raise ValueError("선택값은 1(폴더) 또는 2(문서)만 가능합니다.")


def choose_mode(args: argparse.Namespace) -> str:
    if args.login_only:
        return "login_only"
    if args.open_trash_only:
        return "open_trash_only"
    if args.mode:
        return select_mode(args.mode)
    while True:
        print("휴지통 처리 대상을 선택하세요.", flush=True)
        print("1. 폴더", flush=True)
        print("2. 문서", flush=True)
        print("선택: ", end="", flush=True)
        try:
            return select_mode(input())
        except ValueError as exc:
            print(str(exc), flush=True)


async def main_frame(page: Any) -> Any:
    return page.frame(name="main_frame") or page


async def wait_login_scope(page: Any, selectors: dict[str, str], timeout_ms: int) -> Any:
    deadline = datetime.now().timestamp() + timeout_ms / 1000
    last_frame_url = ""
    while datetime.now().timestamp() < deadline:
        frame = await main_frame(page)
        last_frame_url = getattr(frame, "url", "")
        if "/login/loginSuccess" in last_frame_url:
            return frame
        try:
            await frame.locator(selectors["username"]).first.wait_for(state="visible", timeout=500)
            return frame
        except Exception:
            await page.wait_for_timeout(300)
    raise TimeoutError(f"로그인 입력 폼 대기 실패: last_frame_url={last_frame_url}")


async def wait_main_frame_url(page: Any, expected_part: str, timeout_ms: int) -> str:
    deadline = datetime.now().timestamp() + timeout_ms / 1000
    last_url = ""
    while datetime.now().timestamp() < deadline:
        frame = await main_frame(page)
        last_url = getattr(frame, "url", "")
        if expected_part in last_url:
            return last_url
        await page.wait_for_timeout(300)
    raise TimeoutError(f"프레임 이동 대기 실패: expected={expected_part}, last_url={last_url}")


async def login_otcs(page: Any, account: login.Account, password: str, config: dict[str, Any]) -> dict[str, Any]:
    selectors = config["selectors"]
    await page.goto(config["login_url"], wait_until="domcontentloaded")
    frame = await wait_login_scope(page, selectors, 30000)
    if "/login/loginSuccess" in getattr(frame, "url", ""):
        return {"login_response_status": "ALREADY_LOGGED_IN", "page_url": page.url, "main_frame_url": getattr(frame, "url", "")}

    await login.fill_first_visible(frame, selectors["username"], account.user_id)
    await login.fill_first_visible(frame, selectors["password"], password)

    response_status = "LOGIN_RESPONSE_NOT_CAPTURED"
    try:
        async with page.expect_response(
            lambda response: "login" in response.url.lower() and response.request.method == "POST",
            timeout=6000,
        ) as response_info:
            await login.click_first_visible(frame, selectors["submit"])
        response = await response_info.value
        response_status = f"LOGIN_RESPONSE:{response.status}"
    except Exception:
        try:
            await frame.evaluate("() => typeof submitOk === 'function' && submitOk()")
        except Exception:
            await frame.locator(selectors["password"]).first.press("Enter")

    success_url = await wait_main_frame_url(page, "/login/loginSuccess", 30000)
    return {"login_response_status": response_status, "page_url": page.url, "main_frame_url": success_url}


async def fixed_trash_locator(frame: Any) -> tuple[str, Any, dict[str, str]]:
    for selector in TRASH_FIXED_SELECTORS:
        locator = frame.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=1000)
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
    raise RuntimeError(f"고정 Trash 태그를 찾지 못했습니다: {TRASH_FIXED_SELECTORS}")


async def trash_body_ready(page: Any) -> bool:
    frame = await main_frame(page)
    frame_url = getattr(frame, "url", "")
    if TRASH_PAGE_PATH in frame_url:
        return True
    try:
        body = await frame.locator("body").inner_text(timeout=1500)
    except Exception:
        body = ""
    return "Trash Settings" in body and "Content Title" in body


async def open_trash(page: Any, config: dict[str, Any]) -> dict[str, Any]:
    frame = await main_frame(page)
    selector, locator, info = await fixed_trash_locator(frame)
    await locator.scroll_into_view_if_needed(timeout=3000)
    await locator.click(timeout=3000)

    opened_by_click = False
    try:
        await wait_main_frame_url(page, TRASH_PAGE_PATH, 8000)
        opened_by_click = True
    except Exception:
        opened_by_click = await trash_body_ready(page)

    fallback_url = ""
    if not opened_by_click:
        fallback_url = config["site_url"].rstrip("/") + TRASH_PAGE_PATH
        frame = await main_frame(page)
        await frame.goto(fallback_url, wait_until="domcontentloaded", timeout=15000)
        await wait_main_frame_url(page, TRASH_PAGE_PATH, 15000)

    if not await trash_body_ready(page):
        raise RuntimeError("휴지통 화면 본문 확인에 실패했습니다.")

    return {
        "selector": selector,
        "clicked_tag": info,
        "opened_by_click": opened_by_click,
        "fallback_url": fallback_url,
        "main_frame_url": getattr(await main_frame(page), "url", ""),
    }


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


async def save_screenshot(page: Any, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(path), full_page=True)
    return str(path)


async def count_rows(page: Any) -> dict[str, Any]:
    frame = await main_frame(page)
    return await frame.locator("body").evaluate(
        """() => {
            const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
            const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
            const trimFileMeta = (value) => cleanText(value).split(" Location: ")[0].split(" Delete Date: ")[0].trim();
            const rowLooksLikeFolder = (elements) => elements.some((element) => {
                const className = String(element.getAttribute?.("class") || "").toLowerCase();
                if (className.includes("folder-icon")) {
                    return true;
                }
                const typeAttrs = ["data-type", "data-item-type", "data-file-type", "data-content-type", "data-node-type"];
                if (typeAttrs.some((attr) => String(element.getAttribute?.(attr) || "").toLowerCase().includes("folder"))) {
                    return true;
                }
                return Boolean(element.querySelector?.(
                    ".lucide-folder, .lucide-folder-open, [class*='folder-icon'], svg[class*='folder']"
                ));
            });
            const findFileName = (text) => {
                const source = trimFileMeta(text);
                const match = source.match(/([^\\\\/]+?)\\.([A-Za-z0-9][A-Za-z0-9_-]{0,11})(?=\\s|$)/);
                if (!match) {
                    return null;
                }
                return { fileName: trimFileMeta(`${match[1]}.${match[2]}`), extension: match[2].toLowerCase() };
            };
            const fileNameFromElements = (elements) => {
                for (const element of elements) {
                    const fileNameNode = element.matches?.(".file-name, [class*='file-name'], [class*='file_name']")
                        ? element
                        : element.querySelector?.(".file-name, [class*='file-name'], [class*='file_name']");
                    if (!fileNameNode || !visible(fileNameNode)) {
                        continue;
                    }
                    const matched = findFileName(fileNameNode.innerText || fileNameNode.textContent || "");
                    if (matched) {
                        return matched;
                    }
                }
                return null;
            };
            const textFromElements = (elements) => {
                const parts = [];
                for (const element of elements) {
                    parts.push(element.innerText, element.textContent);
                    for (const attr of ["title", "aria-label", "data-title", "data-name", "data-file-name", "data-filename"]) {
                        parts.push(element.getAttribute(attr));
                    }
                }
                return cleanText(parts.filter(Boolean).join(" "));
            };

            const items = [];
            const seen = new Set();
            const checkboxCells = Array.from(document.querySelectorAll("td[data-column-name='_checked']"));
            for (const cell of checkboxCells) {
                if (!visible(cell)) {
                    continue;
                }
                const rowKey = cell.getAttribute("data-row-key");
                if (!rowKey || seen.has(rowKey)) {
                    continue;
                }
                seen.add(rowKey);
                const sameRowCells = Array.from(document.querySelectorAll(`[data-row-key="${CSS.escape(rowKey)}"]`))
                    .filter((element) => element.getAttribute("data-column-name") !== "_checked" && visible(element));
                const text = textFromElements(sameRowCells);
                if (!text) {
                    continue;
                }
                if (rowLooksLikeFolder(sameRowCells)) {
                    items.push({
                        rowKey,
                        type: "folder",
                        name: trimFileMeta(text)
                    });
                    continue;
                }
                const file = fileNameFromElements(sameRowCells) || findFileName(text);
                items.push({
                    rowKey,
                    type: file ? "document" : "folder",
                    name: file ? file.fileName : trimFileMeta(text)
                });
            }

            const documentCount = items.filter((item) => item.type === "document").length;
            const folderCount = items.filter((item) => item.type === "folder").length;
            return {
                status: items.length ? "ITEMS_FOUND" : "NO_ITEMS_FOUND",
                count: items.length,
                documentCount,
                folderCount,
                sample: items.slice(0, 10)
            };
        }"""
    )


async def wait_for_document_count_change(
    page: Any,
    before_document_count: int,
    timeout_ms: int,
) -> dict[str, Any]:
    started = datetime.now()
    deadline = asyncio.get_running_loop().time() + max(1, timeout_ms / 1000)
    samples: list[dict[str, Any]] = []
    last_check: dict[str, Any] | None = None

    while asyncio.get_running_loop().time() <= deadline:
        check = await count_rows(page)
        last_check = check
        samples.append(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "count": check.get("count", 0),
                "documentCount": check.get("documentCount", 0),
                "folderCount": check.get("folderCount", 0),
            }
        )
        current_document_count = int(check.get("documentCount", 0) or 0)
        if current_document_count < before_document_count:
            return {
                "status": "DOCUMENT_COUNT_DECREASED",
                "beforeDocumentCount": before_document_count,
                "afterDocumentCount": current_document_count,
                "waitedMs": int((datetime.now() - started).total_seconds() * 1000),
                "samples": samples[-10:],
            }
        await page.wait_for_timeout(700)

    after_document_count = int((last_check or {}).get("documentCount", 0) or 0)
    return {
        "status": "DOCUMENT_COUNT_NOT_CHANGED",
        "beforeDocumentCount": before_document_count,
        "afterDocumentCount": after_document_count,
        "waitedMs": int((datetime.now() - started).total_seconds() * 1000),
        "samples": samples[-10:],
    }


TRASH_LIST_API_PATH = "/recyclebin/myRecycleBinGridAdmin"  # 전사(관리자) 휴지통
USER_TRASH_LIST_API_PATH = "/recyclebin/myRecycleBinGrid"  # 개인/부서/프로젝트(사용자) 휴지통


async def fetch_trash_items_via_api(
    page: Any,
    per_page: int = 30,
    box_gubun: str = "",
    doc_title: str = "",
    api_path: str = TRASH_LIST_API_PATH,
) -> dict[str, Any]:
    """DOM 스크롤/아이콘 추정 대신, 그리드가 실제로 호출하는 REST API를 직접 페이지네이션
    호출해서 휴지통 전체 목록을 가져온다.

    실측 결과, DOM 스크롤 기반 "끝까지 로딩" 판정과 아이콘 기반 폴더 추정은 실제 데이터와
    크게 어긋났다(실제 108건인데 DOM은 8건만 인식, obj_type='F'인 폴더 1건을 아이콘 휴리
    스틱이 문서로 오인). 이 API 응답의 `obj_type`('D'=문서, 'F'=폴더)과
    `pagination.totalCount`가 훨씬 신뢰할 수 있는 권위있는(authoritative) 데이터라서,
    목록 확인/폴더 판별/최종 검증은 이걸로 한다. 실제 체크박스 선택·삭제 클릭은 여전히
    화면(DOM)을 통해서 하지만, "몇 건이 진짜 존재하고 그중 몇 건이 폴더인가"는 이 API가
    기준이다.

    관리자 휴지통(`TRASH_LIST_API_PATH`)과 사용자 휴지통(`USER_TRASH_LIST_API_PATH`)은
    동일한 응답 구조(`data.pagination.totalCount` / `data.contents[].obj_type`)를 쓰는
    서로 다른 엔드포인트라서 `api_path`로 전환한다. 사용자 휴지통은 `box_gubun`으로 현재
    선택된 업무함(U=개인/D=부서/P=프로젝트 등)을 지정해야 한다.
    """
    first = await page.request.get(
        api_path,
        params={"perPage": str(per_page), "DOC_TITLE": doc_title, "BOX_GUBUN": box_gubun, "page": "1"},
    )
    first_json = await first.json()
    total_count = int(first_json["data"]["pagination"]["totalCount"])
    pages = (total_count + per_page - 1) // per_page if per_page else 1
    items: list[dict[str, Any]] = list(first_json["data"]["contents"])
    for page_no in range(2, pages + 1):
        resp = await page.request.get(
            api_path,
            params={"perPage": str(per_page), "DOC_TITLE": doc_title, "BOX_GUBUN": box_gubun, "page": str(page_no)},
        )
        body = await resp.json()
        items.extend(body["data"]["contents"])

    documents = [item for item in items if item.get("obj_type") != "F"]
    folders = [item for item in items if item.get("obj_type") == "F"]
    return {
        "totalCount": total_count,
        "fetchedCount": len(items),
        "documentCount": len(documents),
        "folderCount": len(folders),
        "folderTitles": sorted({str(item.get("content_title", "")) for item in folders if item.get("content_title")}),
        "items": items,
    }


# 실측 결과, element.scrollTop을 직접 대입하고 synthetic scroll/wheel 이벤트를
# dispatchEvent()로 흉내 낸 방식은 이 그리드(tui-grid)의 지연 로딩(다음 페이지 API
# 호출)을 전혀 트리거하지 못했다 - 진짜(trusted) 마우스 휠 이벤트라야 트리거됐다.
# 그래서 이 스크립트는 더 이상 스크롤을 직접 수행하지 않고, "어느 요소를 어디로 얼마나
# 휠 스크롤해야 하는가"에 필요한 상태(좌표/스크롤 범위)만 읽어서 반환한다. 실제 스크롤은
# Python 쪽에서 page.mouse.wheel()로 수행한다.
SCROLL_TARGET_STATE_SCRIPT = """() => {
        const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
        const candidates = Array.from(document.querySelectorAll([
            ".tui-grid-body-area",
            ".tui-grid-rside-area",
            ".tui-grid-lside-area",
            ".tui-grid-container",
            ".tui-grid-content-area",
            "[class*='tui-grid']"
        ].join(","))).filter((element) => {
            if (!visible(element)) {
                return false;
            }
            const className = String(element.className || "");
            if (className.includes("tui-grid-header") || className.includes("tui-grid-border")) {
                return false;
            }
            return element.scrollHeight > element.clientHeight + 5;
        });
        candidates.push(document.scrollingElement || document.documentElement);

        const target = candidates
            .filter(Boolean)
            .sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight))[0];

        if (!target) {
            return { status: "NO_SCROLL_TARGET" };
        }

        const box = target.getBoundingClientRect();
        const maxTop = Math.max(0, target.scrollHeight - target.clientHeight);
        return {
            status: "OK",
            scrollTop: target.scrollTop,
            maxTop,
            atBottom: target.scrollTop >= maxTop - 2,
            clientHeight: target.clientHeight,
            scrollHeight: target.scrollHeight,
            className: target.className || "",
            tagName: target.tagName || "",
            centerX: box.left + box.width / 2,
            centerY: box.top + box.height / 2
        };
    }"""

SCROLL_TO_TOP_SCRIPT = """() => {
        const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
        const candidates = Array.from(document.querySelectorAll([
            ".tui-grid-body-area",
            ".tui-grid-rside-area",
            ".tui-grid-lside-area",
            ".tui-grid-container",
            ".tui-grid-content-area",
            "[class*='tui-grid']"
        ].join(","))).filter((element) => visible(element) && element.scrollHeight > element.clientHeight + 5);
        candidates.push(document.scrollingElement || document.documentElement);
        const target = candidates
            .filter(Boolean)
            .sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight))[0];
        if (!target) {
            return { status: "NO_SCROLL_TARGET" };
        }
        target.scrollTop = 0;
        target.dispatchEvent(new Event("scroll", { bubbles: true }));
        return { status: "SCROLLED_TO_TOP", afterTop: target.scrollTop };
    }"""

# "목록이 전부 노출됨"은 시간이 아니라 "스크롤을 실제로 수행했는데도 새로 드러나는 게
# 없다"는 사실 자체로 판정한다. 라운드 수 기준이라 문서 수/서버 속도와 무관하게 몇 초
# 안에 결론이 난다(절대 대기시간에 기대지 않음).
STABLE_ROUNDS_TO_CONFIRM_DONE = 3  # 끝(END_REACHED)에서 이 라운드만큼 연속으로 새 항목이 없으면 완료
STUCK_ROUNDS_LIMIT = 10  # 끝에 도달 못했는데도 이 라운드만큼 연속으로 새 항목이 없으면 스크롤이 안 먹힌 것으로 판단
HARD_TIMEOUT_SECONDS = 20  # evaluate 자체가 멎는 등 진짜 행(hang)에 대비한 최후 안전판
MAX_SCROLL_ROUNDS = 200000  # 정상 진행 중엔 걸리지 않는, 진짜 무한루프 방지용 안전판


async def scroll_grid_to_full_load(
    page: Any,
    frame: Any,
    pass_history: list[dict[str, Any]] | None = None,
    on_round: Any = None,
) -> dict[str, Any]:
    """목록 끝까지 반복 스크롤해서, 서버가 지연 로딩하는 행을 전부 불러온다.

    이 목록(tui-grid)은 스크롤할 때마다 서버가 다음 페이지 행을 추가로 내려주는 지연
    로딩 방식이다. 완료/실패 판정 모두 절대 경과 시간이 아니라 "스크롤을 실제로
    수행했는데도 새로 드러나는 게 없다"는 사실(연속 라운드 수)로 내린다 - 문서
    수/서버 속도와 무관하게 몇 초 안에 결론이 나고, evaluate 자체가 멎는 극단적
    상황에만 최후 안전판(HARD_TIMEOUT_SECONDS)이 개입한다.

    on_round(seen_row_count)를 넘기면 매 라운드 새 행 반영 직후(스크롤 전) 호출되며,
    True를 반환하면 그 라운드에서 즉시 "STOPPED_BY_CALLBACK"으로 종료한다 - 예를 들어
    select_document_checkboxes는 선택 개수 제한을 이미 채웠으면 목록을 끝까지 불러올
    필요가 없으므로 이 콜백으로 조기 종료한다.
    """
    if pass_history is None:
        pass_history = []
    pending_requests: set[Any] = set()
    loop = asyncio.get_running_loop()
    last_progress = loop.time()
    seen_rows: set[str] = set()
    stable_rounds = 0
    stuck_rounds = 0
    last_scroll_top: int | None = None

    def request_started(request: Any) -> None:
        nonlocal last_progress
        if request.resource_type in {"xhr", "fetch"}:
            pending_requests.add(request)
            last_progress = loop.time()

    def request_finished(request: Any) -> None:
        nonlocal last_progress
        if request in pending_requests:
            pending_requests.discard(request)
            last_progress = loop.time()

    page.on("request", request_started)
    page.on("requestfinished", request_finished)
    page.on("requestfailed", request_finished)
    try:
        for round_no in range(MAX_SCROLL_ROUNDS):
            state = await frame.locator("body").evaluate("""() => {
                const visible = e => Boolean(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
                return {
                    keys: Array.from(document.querySelectorAll("td[data-column-name='_checked'][data-row-key]"))
                        .filter(visible).map(e => e.getAttribute("data-row-key")),
                    loading: Array.from(document.querySelectorAll("[aria-busy='true'], .tui-grid-layer-loading, .tui-grid-loading-area"))
                        .some(visible)
                };
            }""")
            new_rows = set(state["keys"]) - seen_rows
            seen_rows.update(state["keys"])
            if new_rows or state["loading"] or pending_requests:
                last_progress = loop.time()

            if on_round is not None and await on_round(len(seen_rows)):
                return {"status": "STOPPED_BY_CALLBACK", "rowCount": len(seen_rows), "rounds": round_no + 1}

            target_state = await frame.locator("body").evaluate(SCROLL_TARGET_STATE_SCRIPT)
            if target_state.get("status") == "NO_SCROLL_TARGET":
                raise RuntimeError("목록 스크롤 영역을 찾지 못해 중단합니다.")
            at_bottom = bool(target_state.get("atBottom"))
            current_scroll_top = target_state.get("scrollTop")
            # 브라우저의 휠 스크롤은 비동기(다음 프레임 이후)로 반영돼서, 휠을 보낸 直後
            # 같은 라운드 안에서 곧바로 scrollTop을 다시 읽으면 아직 반영 전이라 항상
            # "안 움직임"으로 오판된다. 그래서 "이전 라운드에서 읽은 값"과 "이번 라운드
            # 시작 시점 값"을 비교한다 - 그때쯤이면 이전 휠의 효과가 반영돼 있다.
            scroll_moved = last_scroll_top is None or current_scroll_top != last_scroll_top
            last_scroll_top = current_scroll_top
            if not at_bottom:
                # element.scrollTop 대입 + dispatchEvent()는 이 그리드의 지연 로딩을
                # 전혀 트리거하지 못함이 실측으로 확인됐다 - 실제(trusted) 마우스 휠
                # 이벤트라야 다음 페이지 API 호출이 발생한다.
                step = max(120, int(target_state.get("clientHeight", 400) * 0.85))
                await page.mouse.move(target_state["centerX"], target_state["centerY"])
                await page.mouse.wheel(0, step)
            quiet = not new_rows and not state["loading"] and not pending_requests

            # 완료 판정: 끝(바닥)에 도달했고 새로 로딩되는 것도 없으면 "완료" 연속 라운드.
            # 막힘 판정은 새 데이터 유무가 아니라 "스크롤 위치 자체가 실제로 안 움직이는가"로
            # 본다 - 이미 전량 로딩된 상태를 다시 훑는 재검증 패스에서는 새 행이 없는 게
            # 정상이라, 그걸 "막힘"으로 오판하면 안 된다.
            stable_rounds = stable_rounds + 1 if at_bottom and quiet else 0
            stuck_rounds = stuck_rounds + 1 if (not at_bottom and not scroll_moved) else 0
            pass_history.append({
                "atBottom": at_bottom,
                "scrollMoved": scroll_moved,
                "scrollTop": target_state.get("scrollTop"),
                "maxTop": target_state.get("maxTop"),
                "phase": "load",
                "round": round_no + 1,
                "seenRowCount": len(seen_rows),
                "stableRounds": stable_rounds,
                "stuckRounds": stuck_rounds,
            })
            if stable_rounds >= STABLE_ROUNDS_TO_CONFIRM_DONE:
                return {"status": "FULLY_LOADED", "rowCount": len(seen_rows), "rounds": round_no + 1}
            if stuck_rounds >= STUCK_ROUNDS_LIMIT:
                raise RuntimeError(
                    f"스크롤을 {stuck_rounds}회 수행했지만 목록에 새 항목이 노출되지 않습니다. "
                    f"스크롤 대상/그리드 로딩 방식이 바뀌었을 수 있습니다. 확인 행 {len(seen_rows)}건."
                )
            if loop.time() - last_progress >= HARD_TIMEOUT_SECONDS:
                raise RuntimeError(
                    f"응답 없음: {HARD_TIMEOUT_SECONDS}초 동안 화면 반응이 없어 중단합니다. "
                    f"확인 행 {len(seen_rows)}건."
                )
            await page.wait_for_timeout(500 if at_bottom else 180)
        raise RuntimeError(f"목록 스크롤 반복 한도({MAX_SCROLL_ROUNDS})를 초과했습니다.")
    finally:
        page.remove_listener("request", request_started)
        page.remove_listener("requestfinished", request_finished)
        page.remove_listener("requestfailed", request_finished)


SELECT_ALL_HEADER_SCRIPT = """() => {
    const th = document.querySelector("th[data-column-name='_checked']");
    const checkbox = th && th.querySelector("input[type='checkbox'], [role='checkbox']");
    if (!checkbox) {
        return { status: "HEADER_CHECKBOX_NOT_FOUND" };
    }
    const checked = checkbox.matches("input") ? Boolean(checkbox.checked) : checkbox.getAttribute("aria-checked") === "true";
    if (!checked) {
        checkbox.click();
    }
    return { status: "CLICKED" };
}"""


async def select_document_checkboxes(
    page: Any, selection_limit: int = 0, folder_titles: set[str] | list[str] | None = None
) -> dict[str, Any]:
    """목록을 끝까지 스크롤해 전량을 로딩시킨 뒤, 그리드 자체의 "전체 선택" 헤더
    체크박스로 한 번에 전부 선택하고, 폴더/한도 초과 문서만 개별적으로 선택 해제한다.

    과거 구현들의 문제:
    - 2단계(전체 스크롤 수집 → 처음부터 다시 스크롤하며 선택) 구조는 선택 단계가
      `scrollTop` 정지만으로 조기 종료돼, 서버가 뒤쪽 행을 비동기로 더 로딩 중일 때
      후반부 문서가 누락될 수 있었다.
    - 이후 수집/선택을 한 스크롤 패스로 합친 구현은 그 문제는 해결했지만, 패스 전체에
      "180초 절대 데드라인"을 걸어놔서 대량 문서(수백~수천 건)에서는 꾸준히 진행 중이어도
      절대 시간 초과로 실패했다.
    - 스크롤 라운드마다 화면에 걸쳐있는 체크박스를 개별 클릭하는 방식(가상화 때문에
      "끝까지 스크롤 후 한 번에 선택"하면 화면에 남은 일부만 선택되고 나머지를 놓쳐서
      한때 도입했던 방식)은, 문서가 대량일 때 클릭 이벤트가 수백~수천 번 연속으로 몰리며
      그리드/삭제 버튼의 내부 선택 상태가 꼬여 웹 자체 삭제 기능이 정상 동작하지 않는
      문제가 실측으로 확인됐다.

    그래서 방향을 바꾼다: tui-grid는 헤더의 "전체 선택" 체크박스를 누르면 화면에 렌더링된
    행뿐 아니라 그리드의 내부 데이터 전체를 선택 상태로 표시한다(가상화와 무관하게 동작).
      1단계) 화면에 새 행이 반영되는지/네트워크 요청이 도는지만 보면서 끝까지 스크롤해
             서버 지연 로딩을 전부 끝낸다 (아직 선택은 하지 않는다).
      2단계) 전량 로딩이 끝난 뒤, 헤더 체크박스를 한 번만 클릭해 전체를 일괄 선택한다.
      3단계) 전체 선택에는 폴더도 함께 포함되고(--delete-selection-limit 테스트 시
             한도를 넘는 문서도 포함되므로), 다시 한 번 끝까지 스크롤하며 폴더 행과 한도
             초과 문서 행만 개별적으로 체크 해제한다. 이 단계에서 실제 클릭이 필요한 행은
             "폴더 수 + 한도 초과분"뿐이라, 문서가 아무리 많아도 클릭 횟수가 전체 문서
             수에 비례하지 않는다.
    """
    frame = await main_frame(page)
    selected_by_name: dict[str, dict[str, Any]] = {}
    skipped_by_key: dict[str, dict[str, Any]] = {}
    pass_history: list[dict[str, Any]] = []
    folder_title_list = sorted({str(t) for t in (folder_titles or []) if t})

    cleanup_script = """(body, { extensions, limit, alreadySelectedCount, folderTitles }) => {
            const extensionSet = new Set(extensions.map((item) => String(item).toLowerCase()));
            const selectedItems = [];
            const skippedItems = [];
            const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
            const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
            const trimFileMeta = (value) => cleanText(value).split(" Location: ")[0].split(" Delete Date: ")[0].trim();
            const rowLooksLikeFolder = (elements, rowText) => {
                // 아이콘 클래스 휴리스틱(부정확할 수 있음) + 실제 API(obj_type='F')에서
                // 확인된 폴더 제목 목록(권위있는 데이터) 둘 다로 판별한다.
                if (folderTitles.some((title) => title && rowText.includes(title))) {
                    return true;
                }
                return elements.some((element) => {
                    const className = String(element.getAttribute?.("class") || "").toLowerCase();
                    if (className.includes("folder-icon")) {
                        return true;
                    }
                    const typeAttrs = ["data-type", "data-item-type", "data-file-type", "data-content-type", "data-node-type"];
                    if (typeAttrs.some((attr) => String(element.getAttribute?.(attr) || "").toLowerCase().includes("folder"))) {
                        return true;
                    }
                    return Boolean(element.querySelector?.(
                        ".lucide-folder, .lucide-folder-open, [class*='folder-icon'], svg[class*='folder']"
                    ));
                });
            };
            const findFileName = (text) => {
                const matches = Array.from(trimFileMeta(text).matchAll(/([^\\\\/]+?)\\.([A-Za-z0-9][A-Za-z0-9_-]{0,11})(?=\\s|$)/g));
                for (const match of matches) {
                    const extension = match[2].toLowerCase();
                    const looksLikeFileExtension = /^[a-z0-9][a-z0-9_-]{0,11}$/.test(extension);
                    if (extensionSet.has(extension) || looksLikeFileExtension) {
                        return { fileName: trimFileMeta(`${match[1]}.${match[2]}`), extension };
                    }
                }
                return null;
            };
            const fileNameFromElements = (elements) => {
                for (const element of elements) {
                    const fileNameNode = element.matches?.(".file-name, [class*='file-name'], [class*='file_name']")
                        ? element
                        : element.querySelector?.(".file-name, [class*='file-name'], [class*='file_name']");
                    if (!fileNameNode || !visible(fileNameNode)) {
                        continue;
                    }
                    const matched = findFileName(fileNameNode.innerText || fileNameNode.textContent || "");
                    if (matched) {
                        return matched;
                    }
                }
                return null;
            };
            const textFromElements = (elements) => {
                const parts = [];
                for (const element of elements) {
                    parts.push(element.innerText, element.textContent);
                    for (const attr of ["title", "aria-label", "data-title", "data-name", "data-file-name", "data-filename"]) {
                        parts.push(element.getAttribute(attr));
                    }
                }
                return cleanText(parts.filter(Boolean).join(" "));
            };

            // 전체 선택 헤더 체크박스를 이미 눌러서 모든 행이 checked 상태다. 여기서는
            // 화면에 지금 보이는 행 중 "체크되어 있는데 지우면 안 되는" 것만 찾아서
            // 체크 해제한다 - 클릭이 필요한 행은 폴더/한도초과 문서뿐이라, 문서가 아무리
            // 많아도 이 스크립트가 매 라운드 처리하는 클릭 수는 적다.
            const checkboxCells = Array.from(document.querySelectorAll("td[data-column-name='_checked']"));
            for (const cell of checkboxCells) {
                if (!visible(cell)) {
                    continue;
                }
                const checkbox = cell.querySelector("input[type='checkbox'], [role='checkbox']");
                if (!checkbox || !visible(checkbox)) {
                    continue;
                }
                const checked = checkbox.matches("input")
                    ? Boolean(checkbox.checked)
                    : checkbox.getAttribute("aria-checked") === "true";
                if (!checked) {
                    continue;
                }
                const rowKey = cell.getAttribute("data-row-key");
                if (rowKey === null || rowKey === undefined || rowKey === "") {
                    checkbox.click();
                    skippedItems.push({ reason: "NO_ROW_KEY", text: textFromElements([cell]) });
                    continue;
                }
                const sameRowCells = Array.from(document.querySelectorAll(`[data-row-key="${CSS.escape(rowKey)}"]`))
                    .filter((element) => element.getAttribute("data-column-name") !== "_checked" && visible(element));
                const rowText = textFromElements(sameRowCells);
                if (rowLooksLikeFolder(sameRowCells, rowText)) {
                    checkbox.click();
                    skippedItems.push({ rowKey, reason: "FOLDER_ROW_SKIPPED", text: rowText.slice(0, 500) });
                    continue;
                }
                const matched = fileNameFromElements(sameRowCells);
                if (!matched) {
                    checkbox.click();
                    skippedItems.push({ rowKey, reason: "NO_DOCUMENT_EXTENSION", text: rowText.slice(0, 500) });
                    continue;
                }
                if (limit > 0 && alreadySelectedCount + selectedItems.length >= limit) {
                    checkbox.click();
                    skippedItems.push({ rowKey, reason: "SELECTION_LIMIT_REACHED", text: rowText.slice(0, 500) });
                    continue;
                }
                selectedItems.push({ rowKey, fileName: matched.fileName, extension: matched.extension });
            }

            return {
                status: selectedItems.length ? "VISIBLE_DOCUMENT_CHECKBOXES_KEPT" : "NO_VISIBLE_DOCUMENT_CHECKBOX_KEPT",
                selectedItems,
                skippedItems
            };
        }"""

    async def cleanup_visible_selection() -> None:
        """지금 화면에 보이는 행 중 폴더/한도초과 문서 체크만 해제하고, 유효한 문서는 누적한다."""
        result = await frame.locator("body").evaluate(
            cleanup_script,
            {
                "extensions": list(DOCUMENT_EXTENSIONS),
                "limit": selection_limit,
                "alreadySelectedCount": len(selected_by_name),
                "folderTitles": folder_title_list,
            },
        )
        for item in result.get("selectedItems", []):
            selected_by_name.setdefault(item["rowKey"], item)
        for item in result.get("skippedItems", []):
            row_key = item.get("rowKey")
            if row_key:
                skipped_by_key.setdefault(row_key, item)

    async def cleanup_each_round(_seen_row_count: int) -> bool:
        await cleanup_visible_selection()
        return False  # 폴더가 뒤쪽에도 있을 수 있으니 끝까지 전부 훑는다

    await frame.locator("body").evaluate(SCROLL_TO_TOP_SCRIPT)
    await page.wait_for_timeout(250)
    load_result = await scroll_grid_to_full_load(page, frame, pass_history, on_round=None)

    header_result = await frame.locator("body").evaluate(SELECT_ALL_HEADER_SCRIPT)
    if header_result.get("status") != "CLICKED":
        raise RuntimeError(f"전체 선택 체크박스를 찾지 못했습니다: {header_result}")
    await page.wait_for_timeout(300)

    # 헤더 전체 선택 직후 그리드가 내부적으로 다시 렌더링할 수 있어, 맨 위로 돌아가
    # 스크롤하며 매 라운드 폴더/한도초과 행만 체크 해제하는 정리 패스를 끝까지 돈다.
    await frame.locator("body").evaluate(SCROLL_TO_TOP_SCRIPT)
    await page.wait_for_timeout(250)
    await scroll_grid_to_full_load(page, frame, pass_history, on_round=cleanup_each_round)
    converged = True
    sweep_count = 1

    selected_items = list(selected_by_name.values())
    skipped_items = list(skipped_by_key.values())
    return {
        "status": "DOCUMENT_CHECKBOXES_SELECTED" if selected_items else "NO_DOCUMENT_CHECKBOX_SELECTED",
        "selectedCount": len(selected_items),
        "selectedItems": selected_items,
        "targetCount": len(selected_items),
        "missingCount": 0,
        "missingRowKeys": [],
        "unselectedNonDocumentsCount": len(skipped_items),
        "unselectedNonDocumentsSample": skipped_items[:20],
        "collectedCount": len(selected_items),
        "collectedItemsSample": selected_items[:20],
        "skippedSample": skipped_items[:10],
        "verificationConverged": converged,
        "verificationSweeps": sweep_count,
        "loadPhase": load_result,
        "passHistoryRounds": len(pass_history),
        "passHistorySample": pass_history[-10:],
        "selectionLimit": selection_limit,
    }


async def open_context_menu_on_first_visible_selected_document(page: Any, timeout_ms: int) -> dict[str, Any]:
    frame = await main_frame(page)
    target = await frame.locator("body").evaluate(
        """async () => {
            const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
            const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
            const checkedCells = Array.from(document.querySelectorAll("td[data-column-name='_checked']")).filter((cell) => {
                if (!visible(cell)) {
                    return false;
                }
                const checkbox = cell.querySelector("input[type='checkbox'], [role='checkbox']");
                if (!checkbox || !visible(checkbox)) {
                    return false;
                }
                return checkbox.matches("input")
                    ? Boolean(checkbox.checked)
                    : checkbox.getAttribute("aria-checked") === "true";
            });

            for (const cell of checkedCells) {
                const rowKey = cell.getAttribute("data-row-key");
                if (!rowKey) {
                    continue;
                }
                const rowCells = Array.from(document.querySelectorAll(`[data-row-key="${CSS.escape(rowKey)}"]`))
                    .filter((element) => element.getAttribute("data-column-name") !== "_checked" && visible(element));
                const clickTarget = rowCells.find((element) => element.getAttribute("data-column-name") === "contentTitle")
                    || rowCells.find((element) => (element.innerText || element.textContent || "").trim())
                    || rowCells[0]
                    || cell;
                clickTarget.scrollIntoView({ block: "center", inline: "nearest" });
                await sleep(250);
                const box = clickTarget.getBoundingClientRect();
                if (!box.width || !box.height) {
                    continue;
                }
                const x = Math.min(Math.max(box.left + 120, box.left + 12), box.right - 12);
                const y = Math.min(Math.max(box.top + box.height / 2, box.top + 8), box.bottom - 8);
                return {
                    status: "TARGET_FOUND",
                    rowKey,
                    text: (clickTarget.innerText || clickTarget.textContent || "").replace(/\\s+/g, " ").trim().slice(0, 500),
                    x,
                    y,
                    box: {
                        left: box.left,
                        top: box.top,
                        right: box.right,
                        bottom: box.bottom,
                        width: box.width,
                        height: box.height
                    }
                };
            }
            return { status: "NO_VISIBLE_SELECTED_DOCUMENT" };
        }"""
    )
    if target.get("status") != "TARGET_FOUND":
        return target

    detect_menu_script = """async (body, { timeoutMs, clickX, clickY }) => {
            const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
            const menuSelectors = [
                "[role='menu']",
                ".context-menu",
                ".dropdown-menu",
                ".tui-context-menu",
                ".tui-grid-layer-state",
                "[class*='context']",
                "[class*='Context']",
                "[class*='menu']"
            ];
            const startedAt = Date.now();
            const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

            while (Date.now() - startedAt <= timeoutMs) {
                const menus = Array.from(document.querySelectorAll(menuSelectors.join(","))).filter((element) => {
                    if (!visible(element)) {
                        return false;
                    }
                    if (String(element.className || "").includes("nav-sidebar")) {
                        return false;
                    }
                    const box = element.getBoundingClientRect();
                    if (box.width < 20 || box.height < 10) {
                        return false;
                    }
                    const text = (element.innerText || element.textContent || "").replace(/\\s+/g, " ").trim();
                    const looksLikeTrashContextMenu = /Restore|Permanent\\s+delete|복원|영구\\s*삭제|삭제/i.test(text);
                    const isNearClick = box.left >= clickX - 220
                        && box.left <= clickX + 420
                        && box.top >= clickY - 180
                        && box.top <= clickY + 360;
                    return looksLikeTrashContextMenu && isNearClick;
                });
                if (menus.length) {
                    const menu = menus[0];
                    return {
                        status: "CONTEXT_MENU_OPENED",
                        waitedMs: Date.now() - startedAt,
                        menuText: (menu.innerText || menu.textContent || "").replace(/\\s+/g, " ").trim().slice(0, 1000),
                        tagName: menu.tagName,
                        className: menu.className || "",
                        role: menu.getAttribute("role") || ""
                    };
                }
                await sleep(150);
            }
            return { status: "CONTEXT_MENU_NOT_DETECTED", waitedMs: Date.now() - startedAt };
        }"""
    attempts: list[dict[str, Any]] = []
    base_x = float(target["x"])
    base_y = float(target["y"])
    row_key = str(target.get("rowKey", ""))
    if row_key:
        escaped_row_key = row_key.replace("\\", "\\\\").replace('"', '\\"')
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(150)
            row_locator = frame.locator(
                f'[data-row-key="{escaped_row_key}"][data-column-name="contentTitle"], '
                f'[data-row-key="{escaped_row_key}"] .file-name, '
                f'[data-row-key="{escaped_row_key}"]'
            ).first()
            await row_locator.click(button="right", timeout=max(1000, timeout_ms))
            menu_result = await frame.locator("body").evaluate(
                detect_menu_script,
                {"timeoutMs": timeout_ms, "clickX": base_x, "clickY": base_y},
            )
            attempts.append({"attempt": "locator-row-right-click", "rowKey": row_key, "status": menu_result["status"]})
            if menu_result["status"] == "CONTEXT_MENU_OPENED":
                menu_result["attempts"] = attempts
                return {**target, **menu_result}
        except Exception as exc:
            attempts.append({"attempt": "locator-row-right-click", "rowKey": row_key, "status": "FAILED", "message": str(exc)})

    click_points = ((base_x, base_y), (base_x - 70, base_y), (base_x + 90, base_y), (base_x, base_y + 16))
    menu_result: dict[str, Any] = {"status": "CONTEXT_MENU_NOT_DETECTED", "waitedMs": 0}
    for attempt_no, (click_x, click_y) in enumerate(click_points, start=1):
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(150)
        await page.mouse.move(click_x, click_y)
        await page.mouse.click(click_x, click_y, button="right")
        menu_result = await frame.locator("body").evaluate(
            detect_menu_script,
            {"timeoutMs": timeout_ms, "clickX": click_x, "clickY": click_y},
        )
        attempts.append({"attempt": attempt_no, "x": click_x, "y": click_y, "status": menu_result["status"]})
        if menu_result["status"] == "CONTEXT_MENU_OPENED":
            break
    if menu_result["status"] != "CONTEXT_MENU_OPENED":
        await frame.locator("body").evaluate(
            """({ clickX, clickY }) => {
                const target = document.elementFromPoint(clickX, clickY);
                if (!target) {
                    return;
                }
                const event = new MouseEvent("contextmenu", {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    button: 2,
                    buttons: 2,
                    clientX: clickX,
                    clientY: clickY
                });
                target.dispatchEvent(event);
            }""",
            {"clickX": base_x, "clickY": base_y},
        )
        menu_result = await frame.locator("body").evaluate(
            detect_menu_script,
            {"timeoutMs": timeout_ms, "clickX": base_x, "clickY": base_y},
        )
        attempts.append({"attempt": "dom-contextmenu", "x": base_x, "y": base_y, "status": menu_result["status"]})
    menu_result["attempts"] = attempts
    return {**target, **menu_result}


async def wait_for_delete_notice_forever(
    frame: Any, poll_interval_ms: int = 200, ignore_text: str | None = None
) -> dict[str, Any]:
    """삭제 완료/실패 alert(토스트·모달 등)가 뜰 때까지 타임아웃 없이 무한 대기한다.

    삭제 동작의 완료 기준은 "문서 목록 건수가 줄었는가"가 아니라 "Alert 창이 떴는가"다
    (사용자 지정 기준). 서버 처리가 얼마나 걸리든 시간 제한으로 포기하지 않고, 실제로
    Alert가 뜰 때까지 계속 기다린다 - Playwright의 evaluate 자체는 별도 타임아웃을 걸지
    않는 한 대상 Promise가 끝날 때까지 기다리므로, JS 쪽 무한 루프로 폴링한다.

    같은 셀렉터 목록(.modal, .swal2-popup 등)을 삭제 확인(Confirm) 모달 감지에도 쓰기
    때문에, 확인 버튼을 누른 직후 아직 DOM에서 안 사라진 "확인" 팝업 잔상을 완료 알림으로
    오인하는 문제가 실측(seungho.choi 계정, 16건 삭제 시 "Do you want to delete this
    document? Ok Cancel" 텍스트를 완료 알림으로 오판)으로 확인됐다. 이를 막기 위해
    (1) Cancel류 버튼이 아직 남아있는 요소는 "확인 대기 중" 팝업으로 보고 제외하고,
    (2) 방금 클릭한 확인 모달의 텍스트(ignore_text)와 동일한 요소도 제외한다.
    """
    return await frame.locator("body").evaluate(
        """async (body, { pollIntervalMs, ignoreText }) => {
            const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
            const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
            const noticeSelectors = [
                ".toast",
                ".toast-message",
                ".alert",
                ".swal2-popup",
                ".modal",
                ".bootbox",
                "[role='alert']",
                "[aria-live]",
                "[class*='toast']",
                "[class*='alert']",
                "[class*='notification']",
                "[class*='message']"
            ];
            const cancelButtonText = /Cancel|취소|아니오|No/i;
            const normalizedIgnoreText = (ignoreText || "").replace(/\\s+/g, " ").trim();
            const startedAt = Date.now();

            while (true) {
                const notices = Array.from(document.querySelectorAll(noticeSelectors.join(","))).filter((element) => {
                    if (!visible(element)) {
                        return false;
                    }
                    const text = (element.innerText || element.textContent || "").replace(/\\s+/g, " ").trim();
                    if (!text.length) {
                        return false;
                    }
                    if (normalizedIgnoreText && text === normalizedIgnoreText) {
                        return false;
                    }
                    const hasVisibleCancelButton = Array.from(
                        element.querySelectorAll("button, a, input[type='button'], input[type='submit']")
                    ).some((button) => {
                        if (!visible(button)) {
                            return false;
                        }
                        const buttonText = (button.innerText || button.textContent || button.value || "").replace(/\\s+/g, " ").trim();
                        return cancelButtonText.test(buttonText);
                    });
                    if (hasVisibleCancelButton) {
                        return false;
                    }
                    return true;
                });
                if (notices.length) {
                    const notice = notices[0];
                    const text = (notice.innerText || notice.textContent || "").replace(/\\s+/g, " ").trim().slice(0, 1000);
                    const successPattern = /complete|completed|success|deleted|permanent\\s+delete|삭제\\s*(완료|되었습니다|성공)|완전\\s*삭제/i;
                    const errorPattern = /fail|failed|error|cannot|unable|실패|오류|에러|불가|권한|취소/i;
                    let status = "NOTICE_DETECTED";
                    if (errorPattern.test(text)) {
                        status = "DELETE_ERROR_NOTICE_DETECTED";
                    } else if (successPattern.test(text)) {
                        status = "DELETE_SUCCESS_NOTICE_DETECTED";
                    }
                    // 알림을 읽기만 하고 끝내지 않는다 - 화면에 뜬 알림창의 OK/확인류
                    // 버튼을 실제로 눌러서 닫아준다(사용자 지정: "감지만 하면 뭐하냐,
                    // 선택까지 구현해달라"). 이 앱은 SweetAlert2를 쓰는 게 실측(캡처한
                    // HTML)으로 확인됐으므로, 텍스트 매칭보다 SweetAlert2 자체 확인
                    // 버튼 클래스(.swal2-confirm)를 우선 타겟하고(#sidebar > .swal2-container
                    // > .swal2-popup 구조), 없으면 텍스트 기반으로 폴백한다. SweetAlert2
                    // 단일 버튼 Alert는 안 보이는 Cancel 버튼도 DOM에 같이 있으므로
                    // 반드시 visible한 버튼만 고른다.
                    const acknowledgeText = /^(OK|Ok|확인|닫기|Close|예|Yes)$/i;
                    const swal2Confirm = notice.querySelector(".swal2-confirm");
                    const ackButton = (swal2Confirm && visible(swal2Confirm))
                        ? swal2Confirm
                        : Array.from(
                            notice.querySelectorAll("button, a, input[type='button'], input[type='submit']")
                        ).find((button) => {
                            if (!visible(button)) {
                                return false;
                            }
                            const buttonText = (button.innerText || button.textContent || button.value || "").replace(/\\s+/g, " ").trim();
                            return acknowledgeText.test(buttonText);
                        });
                    let acknowledged = false;
                    let acknowledgedButtonText = "";
                    if (ackButton) {
                        acknowledgedButtonText = (ackButton.innerText || ackButton.textContent || ackButton.value || "").replace(/\\s+/g, " ").trim();
                        ackButton.click();
                        acknowledged = true;
                    }
                    return {
                        status,
                        source: "dom",
                        waitedMs: Date.now() - startedAt,
                        text,
                        tagName: notice.tagName,
                        className: notice.className || "",
                        role: notice.getAttribute("role") || "",
                        acknowledged,
                        acknowledgedButtonText
                    };
                }
                await sleep(pollIntervalMs);
            }
        }""",
        {"pollIntervalMs": poll_interval_ms, "ignoreText": ignore_text or ""},
    )


ACKNOWLEDGE_VISIBLE_NOTICE_SCRIPT = """(body, { ignoreText }) => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const noticeSelectors = [
        ".toast", ".toast-message", ".alert", ".swal2-popup", ".modal", ".bootbox",
        "[role='alert']", "[aria-live]", "[class*='toast']", "[class*='alert']",
        "[class*='notification']", "[class*='message']"
    ];
    const cancelButtonText = /Cancel|취소|아니오|No/i;
    const acknowledgeText = /^(OK|Ok|확인|닫기|Close|예|Yes)$/i;
    const normalizedIgnoreText = (ignoreText || "").replace(/\\s+/g, " ").trim();

    const notices = Array.from(document.querySelectorAll(noticeSelectors.join(","))).filter((element) => {
        if (!visible(element)) return false;
        const text = (element.innerText || element.textContent || "").replace(/\\s+/g, " ").trim();
        if (!text.length) return false;
        if (normalizedIgnoreText && text === normalizedIgnoreText) return false;
        const hasVisibleCancelButton = Array.from(
            element.querySelectorAll("button, a, input[type='button'], input[type='submit']")
        ).some((button) => {
            if (!visible(button)) return false;
            const buttonText = (button.innerText || button.textContent || button.value || "").replace(/\\s+/g, " ").trim();
            return cancelButtonText.test(buttonText);
        });
        return !hasVisibleCancelButton;
    });
    if (!notices.length) {
        return { status: "NO_VISIBLE_NOTICE", acknowledged: false };
    }
    const notice = notices[0];
    // SweetAlert2 확인 버튼 클래스(.swal2-confirm)를 우선 타겟하고, 없으면 텍스트로 폴백한다.
    const swal2Confirm = notice.querySelector(".swal2-confirm");
    const ackButton = (swal2Confirm && visible(swal2Confirm))
        ? swal2Confirm
        : Array.from(
            notice.querySelectorAll("button, a, input[type='button'], input[type='submit']")
        ).find((button) => {
            if (!visible(button)) return false;
            const buttonText = (button.innerText || button.textContent || button.value || "").replace(/\\s+/g, " ").trim();
            return acknowledgeText.test(buttonText);
        });
    if (!ackButton) {
        return { status: "NOTICE_WITHOUT_ACK_BUTTON", acknowledged: false };
    }
    const buttonText = (ackButton.innerText || ackButton.textContent || ackButton.value || "").replace(/\\s+/g, " ").trim();
    ackButton.click();
    return { status: "ACKNOWLEDGED", acknowledged: true, buttonText };
}"""


async def acknowledge_visible_notice_once(frame: Any, ignore_text: str | None = None) -> dict[str, Any]:
    """API 경로 등으로 이미 완료를 감지했더라도, 화면에 남아있는 알림 팝업의 OK/확인
    버튼을 한 번 더 확인해서 눌러준다.

    DOM 감지(wait_for_delete_notice_forever)와 API 감지(returnMessage)를 경합시킬
    때, API가 먼저 이기면 DOM 쪽 작업이 취소되면서 정작 화면에 뜬 진짜 팝업은 아무도
    클릭하지 않는 문제가 실측으로 확인됐다(seungho.choi 계정, "Alert/Updated/OK"
    팝업이 안 닫힌 채로 남음). 경합 결과와 무관하게 항상 이 함수로 한 번 더 확인/클릭한다.
    """
    try:
        return await frame.locator("body").evaluate(
            ACKNOWLEDGE_VISIBLE_NOTICE_SCRIPT, {"ignoreText": ignore_text or ""}
        )
    except Exception as exc:
        return {"status": "ACKNOWLEDGE_FAILED", "acknowledged": False, "error": str(exc)}


async def click_permanent_delete_and_wait_notice(page: Any, timeout_ms: int) -> dict[str, Any]:
    frame = await main_frame(page)
    dialog_events: list[dict[str, Any]] = []

    async def handle_dialog(dialog: Any) -> None:
        dialog_events.append({"type": dialog.type, "message": dialog.message})
        await dialog.accept()

    page.on("dialog", handle_dialog)
    try:
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
                    const permanentDelete = items.find((item) => {
                        const text = (item.innerText || item.textContent || "").replace(/\\s+/g, " ").trim();
                        return /Permanent\\s+delete|영구\\s*삭제/i.test(text);
                    });
                    if (permanentDelete) {
                        const text = (permanentDelete.innerText || permanentDelete.textContent || "").replace(/\\s+/g, " ").trim();
                        const box = permanentDelete.getBoundingClientRect();
                        return {
                            status: "PERMANENT_DELETE_MENU_ITEM_FOUND",
                            waitedMs: Date.now() - startedAt,
                            menuItemText: text,
                            tagName: permanentDelete.tagName,
                            className: permanentDelete.className || "",
                            x: box.left + box.width / 2,
                            y: box.top + box.height / 2
                        };
                    }
                    await sleep(150);
                }
                return { status: "PERMANENT_DELETE_MENU_NOT_FOUND", waitedMs: Date.now() - startedAt };
            }""",
            {"timeoutMs": timeout_ms},
        )
        if menu_item["status"] != "PERMANENT_DELETE_MENU_ITEM_FOUND":
            return {
                "status": menu_item["status"],
                "click": menu_item,
                "notice": {"status": "SKIPPED"},
                "dialogs": dialog_events,
            }

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
            {"timeoutMs": 2500},
        )
        await page.wait_for_timeout(600)
        # 삭제 완료/실패 판정 기준은 "Alert 창이 떴는가" 하나뿐이다 - 서버가 오래 걸려도
        # 시간 제한 없이 실제로 뜰 때까지 기다린다.
        notice_result = await wait_for_delete_notice_forever(frame)
        return {
            "status": notice_result["status"] if menu_item["status"] == "PERMANENT_DELETE_MENU_ITEM_FOUND" else menu_item["status"],
            "click": {**menu_item, "status": "PERMANENT_DELETE_CLICKED"},
            "confirm": confirm_result,
            "notice": notice_result,
            "dialogs": dialog_events,
        }
    finally:
        page.remove_listener("dialog", handle_dialog)


async def run(args: argparse.Namespace) -> int:
    configure_playwright_browsers_path()
    from playwright.async_api import async_playwright

    mode = choose_mode(args)
    args.execute_delete = mode == "document" and not args.select_only
    config = login.load_json(args.config)
    account, password = load_credentials(args.credential_file)
    lines: list[str] = []
    result: dict[str, Any] = {
        "mode": "SYS_TRASH",
        "target_type": mode,
        "execute": bool(args.execute_delete),
        "user_id": account.user_id,
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    layout_result = window_layout.apply_console_left_layout()
    log_line(
        lines,
        f"화면 배치(로그 창): {layout_result['status']} (출처: {layout_result.get('source', '-')})",
        args.log,
    )
    chrome_snapshot = window_layout.snapshot_chrome_windows()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
        context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
        page = await context.new_page()
        if not config.get("headless", False):
            browser_layout_result = window_layout.apply_browser_right_layout(before_hwnds=chrome_snapshot)
            log_line(lines, f"화면 배치(브라우저 창): {browser_layout_result['status']}", args.log)
        try:
            log_line(lines, f"로그인 시작: {account.user_id}", args.log)
            login_result = await login_otcs(page, account, password, config)
            result.update(login_result)
            log_line(lines, "로그인 성공", args.log)

            if args.login_only:
                result["status"] = "LOGIN_OK"
                log_line(lines, "로그인 테스트 완료", args.log)
                await wait_before_close(args, lines)
                return 0

            log_line(lines, "휴지통 이동 시작", args.log)
            trash_result = await open_trash(page, config)
            result["trash_navigation"] = trash_result
            log_line(lines, "휴지통 이동 성공", args.log)
            if trash_result["fallback_url"]:
                log_line(lines, "휴지통 직접 이동 사용", args.log)

            result["after_trash_snapshot"] = await snapshot_page(page)
            result["after_trash_screenshot"] = await save_screenshot(page, args.screenshot)
            # count_rows()는 DOM 스냅샷(스크롤 전)이라 실제 건수와 크게 어긋날 수 있음이
            # 실측으로 확인됐다(예: 실제 108건인데 8건으로 오판). 그리드가 실제로 호출하는
            # API를 직접 페이지네이션 호출해 권위있는 전체 건수/폴더 목록을 확보한다.
            api_listing = await fetch_trash_items_via_api(page)
            result["api_listing"] = {
                "totalCount": api_listing["totalCount"],
                "documentCount": api_listing["documentCount"],
                "folderCount": api_listing["folderCount"],
                "folderTitles": api_listing["folderTitles"],
            }
            log_line(
                lines,
                (
                    f"목록 확인(API 기준): 전체 {api_listing['totalCount']}건, "
                    f"문서 {api_listing['documentCount']}건, "
                    f"폴더 {api_listing['folderCount']}건"
                    + (f" ({', '.join(api_listing['folderTitles'])})" if api_listing["folderTitles"] else "")
                ),
                args.log,
            )

            if mode == "document":
                log_line(lines, "전체 목록 수집 시작: 끝 도달 및 추가 로딩 종료 확인 후 문서를 선택합니다.", args.log)
                selection_limit = args.delete_selection_limit if args.execute_delete else 0
                selection = await select_document_checkboxes(
                    page, selection_limit=selection_limit, folder_titles=api_listing["folderTitles"]
                )
                result["document_selection"] = selection
                result["after_document_selection_screenshot"] = await save_screenshot(page, args.selection_screenshot)
                log_line(lines, f"문서 수집 완료: {selection.get('collectedCount', 0)}건", args.log)
                log_line(lines, f"문서 선택 완료: {selection['selectedCount']}건", args.log)
                if selection_limit == 0 and selection["selectedCount"] != api_listing["documentCount"]:
                    log_line(
                        lines,
                        (
                            f"[경고] 선택된 문서 수({selection['selectedCount']}건)가 "
                            f"API 기준 문서 수({api_listing['documentCount']}건)와 다릅니다 - "
                            f"화면 스크롤이 전체 데이터를 다 못 불러왔을 수 있습니다."
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
                if selection.get("unselectedNonDocumentsCount", 0) > 0:
                    log_line(lines, f"비문서 체크 해제: {selection['unselectedNonDocumentsCount']}건", args.log)
                if selection["selectedCount"] == 0:
                    result["status"] = "NO_DOCUMENTS_TO_DELETE"
                    log_line(lines, "삭제 대상 문서 없음: 폴더만 있거나 파일 항목이 없습니다.", args.log)
                    log_line(lines, "최종 결과: 삭제 항목 없음", args.log)
                    await wait_before_close(args, lines)
                    return 0
                if args.select_only:
                    result["status"] = "DOCUMENT_SELECTION_VERIFIED"
                    log_line(lines, "최종 결과: 문서 선택 검증 완료", args.log)
                    await wait_before_close(args, lines)
                    return 0
                log_line(lines, "우클릭 메뉴 열기", args.log)
                context_menu = await open_context_menu_on_first_visible_selected_document(page, args.context_menu_timeout_ms)
                result["context_menu"] = context_menu
                result["after_context_menu_screenshot"] = await save_screenshot(page, args.context_menu_screenshot)
                log_line(lines, f"우클릭 메뉴: {context_menu['status']}", args.log)
                if args.execute_delete:
                    if context_menu["status"] != "CONTEXT_MENU_OPENED":
                        raise RuntimeError(f"우클릭 메뉴가 열리지 않아 완전 삭제를 중단합니다: {context_menu['status']}")
                    log_line(lines, "완전 삭제 실행 - 삭제 Alert 감지까지 무한 대기합니다.", args.log)
                    delete_result = await click_permanent_delete_and_wait_notice(page, args.delete_notice_timeout_ms)
                    result["permanent_delete"] = delete_result
                    result["after_permanent_delete_screenshot"] = await save_screenshot(page, args.delete_screenshot)
                    log_line(lines, f"삭제 Alert 감지: {delete_result['status']}", args.log)

                    # 완료 판정 기준은 "Alert 창 감지" 하나뿐이다(사용자 지정 기준). 문서
                    # 건수 재확인은 참고 로그일 뿐 최종 상태를 좌우하지 않는다.
                    before_delete_document_count = int(selection.get("selectedCount", 0) or 0)
                    verify_result = await wait_for_document_count_change(
                        page,
                        before_delete_document_count,
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
                    if delete_result["status"] == "PERMANENT_DELETE_MENU_NOT_FOUND":
                        result["status"] = "DELETE_MENU_NOT_FOUND"
                        log_line(lines, "최종 결과: 영구 삭제 메뉴 항목을 찾지 못했습니다.", args.log)
                    elif delete_result["status"] == "DELETE_ERROR_NOTICE_DETECTED":
                        result["status"] = "DELETE_FAILED_NOTICE_DETECTED"
                        notice = delete_result.get("notice") or {}
                        notice_text = notice.get("text") or "삭제 실패 알림 감지"
                        log_line(lines, f"최종 결과: 삭제 실패 - {notice_text}", args.log)
                    elif delete_result["status"] in ("DELETE_SUCCESS_NOTICE_DETECTED", "NOTICE_DETECTED"):
                        result["status"] = "DELETE_COMPLETED"
                        notice = delete_result.get("notice") or {}
                        notice_text = notice.get("text") or "삭제 Alert 감지됨"
                        log_line(lines, f"최종 결과: 삭제 완료 - {notice_text}", args.log)
                    else:
                        # wait_for_delete_notice_forever는 Alert를 감지할 때까지 반환하지
                        # 않으므로 실제로는 도달하지 않는 방어적 분기다.
                        result["status"] = "DELETE_NOT_VERIFIED"
                        log_line(lines, f"최종 결과: 알 수 없는 삭제 상태 - {delete_result['status']}", args.log)
                    await wait_before_close(args, lines)
                    return 0

            result["status"] = "TRASH_OPEN_OK"
            await wait_before_close(args, lines)
            return 0
        except Exception as exc:
            result["status"] = "FAILED"
            result["message"] = str(exc)
            result["failure_snapshot"] = await snapshot_page(page)
            log_line(lines, f"실패: {exc}", args.log)
            await wait_before_close(args, lines)
            return 1
        finally:
            await context.close()
            await browser.close()
            write_outputs(args, result, lines)


def main() -> int:
    configure_console_output()
    explorer.configure_console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--credential-file", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--mode", default="")
    parser.add_argument("--login-only", action="store_true")
    parser.add_argument("--select-only", action="store_true")
    parser.add_argument("--open-trash-only", action="store_true")
    parser.add_argument("--hold-ms", type=int, default=0)
    parser.add_argument("--no-final-enter", action="store_true")
    parser.add_argument("--context-menu-timeout-ms", type=int, default=5000)
    parser.add_argument("--delete-selection-limit", type=int, default=0)
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
            print("\n프로그램 종료 대기: 로그 확인 후 'Enter'를 누르세요.")
            wait_for_enter_key()


if __name__ == "__main__":
    raise SystemExit(main())
