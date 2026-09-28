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

import explorer_path_test as explorer
import login_session_check as login


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
DEFAULT_REPORT = runtime_output_path(r"reports\trash_cleanup_test_report.json")
DEFAULT_LOG = runtime_output_path(r"reports\trash_cleanup_test.log")
DEFAULT_SCREENSHOT = runtime_output_path(r"reports\trash_after_open.png")
DEFAULT_SELECTION_SCREENSHOT = runtime_output_path(r"reports\trash_after_document_selection.png")
DEFAULT_CONTEXT_MENU_SCREENSHOT = runtime_output_path(r"reports\trash_after_context_menu.png")
DEFAULT_DELETE_SCREENSHOT = runtime_output_path(r"reports\trash_after_permanent_delete.png")

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
        print("휴지통 처리 대상을 선택하세요.")
        print("1. 폴더")
        print("2. 문서")
        try:
            return select_mode(input("선택: "))
        except ValueError as exc:
            print(str(exc))


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


async def select_document_checkboxes(page: Any, selection_limit: int = 0) -> dict[str, Any]:
    frame = await main_frame(page)
    collected_by_name: dict[str, dict[str, Any]] = {}
    selected_by_name: dict[str, dict[str, Any]] = {}
    unselected_items: list[dict[str, Any]] = []
    skipped_latest: list[dict[str, Any]] = []
    scroll_history: list[dict[str, Any]] = []

    collect_visible_script = """(body, { extensions }) => {
            const extensionSet = new Set(extensions.map((item) => String(item).toLowerCase()));
            const items = [];
            const skippedItems = [];
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

            const checkboxCells = Array.from(document.querySelectorAll("td[data-column-name='_checked']"));
            for (const cell of checkboxCells) {
                if (!visible(cell)) {
                    continue;
                }
                const checkbox = cell.querySelector("input[type='checkbox'], [role='checkbox']");
                if (!checkbox || !visible(checkbox)) {
                    continue;
                }

                const rowKey = cell.getAttribute("data-row-key");
                if (rowKey === null || rowKey === undefined || rowKey === "") {
                    skippedItems.push({ reason: "NO_ROW_KEY", text: textFromElements([cell]) });
                    continue;
                }

                const sameRowCells = Array.from(document.querySelectorAll(`[data-row-key="${CSS.escape(rowKey)}"]`))
                    .filter((element) => element.getAttribute("data-column-name") !== "_checked" && visible(element));
                const rowText = textFromElements(sameRowCells);
                if (rowLooksLikeFolder(sameRowCells)) {
                    skippedItems.push({
                        rowKey,
                        reason: "FOLDER_ROW_SKIPPED",
                        text: rowText.slice(0, 500),
                        cellCount: sameRowCells.length
                    });
                    continue;
                }
                const matched = fileNameFromElements(sameRowCells);
                if (!matched) {
                    skippedItems.push({
                        rowKey,
                        reason: "NO_DOCUMENT_EXTENSION",
                        text: rowText.slice(0, 500),
                        cellCount: sameRowCells.length
                    });
                    continue;
                }

                items.push({ rowKey, fileName: matched.fileName, extension: matched.extension });
            }

            return {
                status: items.length ? "VISIBLE_DOCUMENT_ROWS_COLLECTED" : "NO_VISIBLE_DOCUMENT_ROW",
                items,
                itemCount: items.length,
                skippedCount: skippedItems.length,
                skippedSample: skippedItems.slice(0, 10)
            };
        }"""

    select_visible_script = """(body, { targetNames, limit, alreadySelectedCount }) => {
            const targetNameSet = new Set(targetNames);
            const selectedItems = [];
            const unselectedItems = [];
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
                const matches = Array.from(trimFileMeta(text).matchAll(/([^\\\\/]+?)\\.([A-Za-z0-9][A-Za-z0-9_-]{0,11})(?=\\s|$)/g));
                for (const match of matches) {
                    return { fileName: trimFileMeta(`${match[1]}.${match[2]}`), extension: match[2].toLowerCase() };
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

            const checkboxCells = Array.from(document.querySelectorAll("td[data-column-name='_checked']"));
            for (const cell of checkboxCells) {
                if (limit > 0 && alreadySelectedCount + selectedItems.length >= limit) {
                    break;
                }
                if (!visible(cell)) {
                    continue;
                }
                const checkbox = cell.querySelector("input[type='checkbox'], [role='checkbox']");
                if (!checkbox || !visible(checkbox)) {
                    continue;
                }
                const rowKey = cell.getAttribute("data-row-key");
                if (rowKey === null || rowKey === undefined || rowKey === "") {
                    continue;
                }
                const sameRowCells = Array.from(document.querySelectorAll(`[data-row-key="${CSS.escape(rowKey)}"]`))
                    .filter((element) => element.getAttribute("data-column-name") !== "_checked" && visible(element));
                const rowText = textFromElements(sameRowCells);
                const matched = fileNameFromElements(sameRowCells);
                const checked = checkbox.matches("input")
                    ? Boolean(checkbox.checked)
                    : checkbox.getAttribute("aria-checked") === "true";
                if (rowLooksLikeFolder(sameRowCells) || !matched || !targetNameSet.has(rowKey)) {
                    if (checked) {
                        throw new Error("NON_DOCUMENT_ALREADY_CHECKED: " + rowKey);
                    }
                    continue;
                }
                if (!checked) {
                    checkbox.click();
                }
                if (!(checkbox.matches("input") ? checkbox.checked : checkbox.getAttribute("aria-checked") === "true")) {
                    throw new Error("DOCUMENT_CHECK_FAILED: " + rowKey);
                }
                selectedItems.push({ rowKey, fileName: matched.fileName, extension: matched.extension });
            }

            return {
                status: selectedItems.length ? "VISIBLE_DOCUMENT_CHECKBOXES_SELECTED" : "NO_VISIBLE_DOCUMENT_CHECKBOX_SELECTED",
                selectedCount: selectedItems.length,
                selectedItems,
                unselectedCount: unselectedItems.length,
                unselectedSample: unselectedItems.slice(0, 10)
            };
        }"""

    scroll_script = """() => {
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

            let target = candidates
                .filter(Boolean)
                .sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight))[0];

            if (!target) {
                return { status: "NO_SCROLL_TARGET" };
            }

            const beforeTop = target.scrollTop;
            const maxTop = Math.max(0, target.scrollHeight - target.clientHeight);
            const step = Math.max(120, Math.floor(target.clientHeight * 0.85));
            target.scrollTop = Math.min(maxTop, beforeTop + step);
            target.dispatchEvent(new Event("scroll", { bubbles: true }));
            target.dispatchEvent(new WheelEvent("wheel", { bubbles: true, deltaY: step }));

            return {
                status: target.scrollTop > beforeTop ? "SCROLLED" : "END_REACHED",
                beforeTop,
                afterTop: target.scrollTop,
                maxTop,
                clientHeight: target.clientHeight,
                scrollHeight: target.scrollHeight,
                className: target.className || "",
                tagName: target.tagName || ""
            };
        }"""

    scroll_top_script = """() => {
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

    max_scroll_rounds = 2000
    no_new_rounds = 0
    previous_scroll_top: int | None = None

    pending_requests: set[Any] = set()
    loop = asyncio.get_running_loop()
    last_activity = loop.time()
    seen_rows: set[str] = set()
    stable_rounds = 0
    deadline = loop.time() + 180

    def request_started(request: Any) -> None:
        nonlocal last_activity
        if request.resource_type in {"xhr", "fetch"}:
            pending_requests.add(request)
            last_activity = loop.time()

    def request_finished(request: Any) -> None:
        nonlocal last_activity
        if request in pending_requests:
            pending_requests.discard(request)
            last_activity = loop.time()

    page.on("request", request_started)
    page.on("requestfinished", request_finished)
    page.on("requestfailed", request_finished)
    try:
        for round_no in range(max_scroll_rounds):
            visible_result = await frame.locator("body").evaluate(collect_visible_script, {"extensions": list(DOCUMENT_EXTENSIONS)})
            skipped_latest = visible_result.get("skippedSample", [])
            for item in visible_result.get("items", []):
                collected_by_name.setdefault(item["rowKey"], item)
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
                last_activity = loop.time()
            scroll_result = await frame.locator("body").evaluate(scroll_script)
            if scroll_result.get("status") == "NO_SCROLL_TARGET":
                raise RuntimeError("목록 스크롤 영역을 찾지 못해 선택을 중단합니다.")
            at_bottom = scroll_result.get("status") == "END_REACHED"
            quiet = not new_rows and not state["loading"] and not pending_requests
            stable_rounds = stable_rounds + 1 if at_bottom and quiet else 0
            scroll_history.append({**scroll_result, "round": round_no + 1,
                                   "totalCollectedCount": len(collected_by_name),
                                   "seenRowCount": len(seen_rows), "stableRounds": stable_rounds})
            if stable_rounds >= 3 and loop.time() - last_activity >= 5:
                break
            if loop.time() >= deadline:
                raise RuntimeError(f"서버 지연: 목록 수집 완료 미확인, 확인 행 {len(seen_rows)}건 / 문서 {len(collected_by_name)}건. 선택 중단.")
            await page.wait_for_timeout(500 if at_bottom else 180)
        else:
            raise RuntimeError("목록 수집 반복 한도 초과: 선택을 중단합니다.")
    finally:
        page.remove_listener("request", request_started)
        page.remove_listener("requestfinished", request_finished)
        page.remove_listener("requestfailed", request_finished)

    target_names = list(collected_by_name.keys())
    if selection_limit > 0:
        target_names = target_names[:selection_limit]

    await frame.locator("body").evaluate(scroll_top_script)
    await page.wait_for_timeout(250)

    selection_history: list[dict[str, Any]] = []
    no_new_rounds = 0
    previous_scroll_top = None

    for round_no in range(max_scroll_rounds):
        visible_result = await frame.locator("body").evaluate(
            select_visible_script,
            {
                "targetNames": target_names,
                "limit": selection_limit,
                "alreadySelectedCount": len(selected_by_name),
            },
        )
        before_count = len(selected_by_name)
        for item in visible_result.get("selectedItems", []):
            selected_by_name.setdefault(item["rowKey"], item)
        unselected_items.extend(visible_result.get("unselectedSample", []))
        new_count = len(selected_by_name) - before_count
        selection_history.append(
            {
                "round": round_no + 1,
                "status": visible_result.get("status"),
                "newSelectedCount": new_count,
                "totalSelectedCount": len(selected_by_name),
                "unselectedCount": visible_result.get("unselectedCount", 0),
            }
        )
        no_new_rounds = no_new_rounds + 1 if new_count == 0 else 0

        target_reached = len(selected_by_name) >= len(target_names)
        limit_reached = selection_limit > 0 and len(selected_by_name) >= selection_limit
        if target_reached or limit_reached:
            break

        scroll_result = await frame.locator("body").evaluate(scroll_script)
        current_scroll_top = scroll_result.get("afterTop")
        end_reached = scroll_result.get("status") != "SCROLLED"
        same_position = previous_scroll_top is not None and current_scroll_top == previous_scroll_top
        previous_scroll_top = current_scroll_top
        if end_reached or (same_position and no_new_rounds >= 2):
            break
        await page.wait_for_timeout(120)

    if len(selected_by_name) != len(target_names):
        raise RuntimeError(f"문서 선택 불완전: 대상 {len(target_names)}건 / 선택 {len(selected_by_name)}건. 삭제 중단.")
    selected_items = list(selected_by_name.values())
    return {
        "status": "DOCUMENT_CHECKBOXES_SELECTED" if selected_items else "NO_DOCUMENT_CHECKBOX_SELECTED",
        "selectedCount": len(selected_items),
        "selectedItems": selected_items,
        "unselectedNonDocumentsCount": len(unselected_items),
        "unselectedNonDocumentsSample": unselected_items[:20],
        "collectedCount": len(collected_by_name),
        "collectedItemsSample": list(collected_by_name.values())[:20],
        "skippedSample": skipped_latest,
        "collectScrollRounds": len(scroll_history),
        "collectScrollHistorySample": scroll_history[-10:],
        "selectionRounds": len(selection_history),
        "selectionHistorySample": selection_history[-10:],
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
        notice_result = await frame.locator("body").evaluate(
            """async (body, { timeoutMs }) => {
                const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
                const startedAt = Date.now();
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

                while (Date.now() - startedAt <= timeoutMs) {
                    const notices = Array.from(document.querySelectorAll(noticeSelectors.join(","))).filter((element) => {
                        if (!visible(element)) {
                            return false;
                        }
                        const text = (element.innerText || element.textContent || "").replace(/\\s+/g, " ").trim();
                        return text.length > 0;
                    });
                    if (notices.length) {
                        const notice = notices[0];
                        return {
                            status: "NOTICE_DETECTED",
                            waitedMs: Date.now() - startedAt,
                            text: (notice.innerText || notice.textContent || "").replace(/\\s+/g, " ").trim().slice(0, 1000),
                            tagName: notice.tagName,
                            className: notice.className || "",
                            role: notice.getAttribute("role") || ""
                        };
                    }
                    await sleep(200);
                }
                return { status: "NOTICE_NOT_DETECTED", waitedMs: Date.now() - startedAt };
            }""",
            {"timeoutMs": timeout_ms},
        )
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
        "mode": "TRASH_CLEANUP_TEST",
        "target_type": mode,
        "execute": bool(args.execute_delete),
        "user_id": account.user_id,
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
        context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
        page = await context.new_page()
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
            result["row_check"] = await count_rows(page)
            log_line(
                lines,
                (
                    f"목록 확인: 전체 {result['row_check']['count']}건, "
                    f"문서 {result['row_check'].get('documentCount', 0)}건, "
                    f"폴더 {result['row_check'].get('folderCount', 0)}건"
                ),
                args.log,
            )

            if mode == "document":
                log_line(lines, "전체 목록 수집 시작: 끝 도달 및 추가 로딩 종료 확인 후 문서를 선택합니다.", args.log)
                selection_limit = args.delete_selection_limit if args.execute_delete else 0
                selection = await select_document_checkboxes(page, selection_limit=selection_limit)
                result["document_selection"] = selection
                result["after_document_selection_screenshot"] = await save_screenshot(page, args.selection_screenshot)
                log_line(lines, f"문서 수집 완료: {selection.get('collectedCount', 0)}건", args.log)
                log_line(lines, f"문서 선택 완료: {selection['selectedCount']}건", args.log)
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
                    log_line(lines, "완전 삭제 실행", args.log)
                    delete_result = await click_permanent_delete_and_wait_notice(page, args.delete_notice_timeout_ms)
                    result["permanent_delete"] = delete_result
                    result["after_permanent_delete_screenshot"] = await save_screenshot(page, args.delete_screenshot)
                    log_line(lines, f"완전 삭제 결과: {delete_result['status']}", args.log)
                    if delete_result["status"] == "NOTICE_DETECTED":
                        result["status"] = "DELETE_COMPLETED"
                        notice = delete_result.get("notice") or {}
                        notice_text = notice.get("text") or "삭제 완료 알림 감지"
                        log_line(lines, f"최종 결과: 삭제 완료 - {notice_text}", args.log)
                    else:
                        result["status"] = "DELETE_NOTICE_NOT_DETECTED"
                        log_line(lines, "최종 결과: 삭제 요청 후 완료 알림 미감지", args.log)
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
