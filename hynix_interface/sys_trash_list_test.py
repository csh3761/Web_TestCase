# -*- coding: utf-8 -*-
"""휴지통 문서 목록 조회 전용 테스트.

sys_trash.py와 동일한 경로(전사 관리자 휴지통 화면)로 로그인/진입하지만, 체크박스
선택이나 삭제는 전혀 하지 않는다. 목록 끝까지 스크롤해 전량을 로딩시킨 뒤, 그 화면에
있는 문서 목록만 뽑아서 리포트로 남긴다 (TRASH-A 삭제 계열과 별개의 읽기 전용 케이스).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "hynix_interface"))
sys.path.insert(0, str(PROJECT_ROOT / "HYNIX"))

from sys_trash import (  # noqa: E402
    DEFAULT_CONFIG,
    DEFAULT_CREDENTIALS,
    DOCUMENT_EXTENSIONS,
    SCROLL_TO_TOP_SCRIPT,
    append_log_file,
    configure_console_output,
    configure_playwright_browsers_path,
    load_credentials,
    log_line,
    login_otcs,
    main_frame,
    open_trash,
    runtime_output_path,
    save_screenshot,
    scroll_grid_to_full_load,
    snapshot_page,
    wait_before_close,
)
import login_session_check as login  # noqa: E402


DEFAULT_REPORT = runtime_output_path(r"reports\sys_trash_list_test_report.json")
DEFAULT_LOG = runtime_output_path(r"reports\sys_trash_list_test.log")
DEFAULT_SCREENSHOT = runtime_output_path(r"reports\sys_trash_list_after_open.png")

# select_document_checkboxes의 select_visible_script와 같은 폴더/문서 판별 규칙을 쓰되,
# 여기서는 체크박스를 클릭하지 않고 이름/확장자만 읽어서 목록으로 반환한다.
LIST_ALL_ROWS_SCRIPT = """(body, { extensions }) => {
        const extensionSet = new Set(extensions.map((item) => String(item).toLowerCase()));
        const documents = [];
        const folders = [];
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
            const rowText = textFromElements(sameRowCells);
            if (rowLooksLikeFolder(sameRowCells)) {
                folders.push({ rowKey, name: trimFileMeta(rowText) });
                continue;
            }
            const matched = fileNameFromElements(sameRowCells);
            documents.push({
                rowKey,
                fileName: matched ? matched.fileName : trimFileMeta(rowText),
                extension: matched ? matched.extension : null,
                nameMatchedExtension: Boolean(matched)
            });
        }

        return { documents, folders };
    }"""


async def list_all_rows(frame: Any) -> dict[str, Any]:
    """스크롤 없이, 지금 DOM에 반영돼 있는 전체 목록에서 문서/폴더 목록을 한 번에 읽는다."""
    return await frame.locator("body").evaluate(
        LIST_ALL_ROWS_SCRIPT,
        {"extensions": list(DOCUMENT_EXTENSIONS)},
    )


async def run(args: argparse.Namespace) -> int:
    configure_playwright_browsers_path()
    from playwright.async_api import async_playwright

    config = login.load_json(args.config)
    account, password = load_credentials(args.credential_file)
    lines: list[str] = []
    result: dict[str, Any] = {
        "mode": "TRASH_LIST_TEST",
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

            log_line(lines, "휴지통 이동 시작", args.log)
            trash_result = await open_trash(page, config)
            result["trash_navigation"] = trash_result
            log_line(lines, "휴지통 이동 성공", args.log)

            result["after_trash_screenshot"] = await save_screenshot(page, args.screenshot)

            frame = await main_frame(page)
            pass_history: list[dict[str, Any]] = []
            log_line(lines, "목록 끝까지 스크롤 시작 (선택/삭제 없이 목록만 조회)", args.log)
            await frame.locator("body").evaluate(SCROLL_TO_TOP_SCRIPT)
            await page.wait_for_timeout(250)
            load_result = await scroll_grid_to_full_load(page, frame, pass_history)
            result["load_result"] = load_result
            result["scroll_rounds"] = len(pass_history)
            log_line(
                lines,
                f"목록 로딩 완료: {load_result['status']} (행 {load_result.get('rowCount', 0)}건, "
                f"{load_result.get('rounds', 0)}라운드)",
                args.log,
            )

            await frame.locator("body").evaluate(SCROLL_TO_TOP_SCRIPT)
            await page.wait_for_timeout(250)
            listing = await list_all_rows(frame)
            documents = listing.get("documents", [])
            folders = listing.get("folders", [])
            result["document_count"] = len(documents)
            result["folder_count"] = len(folders)
            result["documents"] = documents
            result["folders"] = folders
            log_line(
                lines,
                f"목록 조회 완료: 문서 {len(documents)}건 / 폴더 {len(folders)}건 (문서만 추려 리포트에 기록)",
                args.log,
            )

            result["status"] = "LIST_OK"
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
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.log.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            if not args.log.exists():
                args.log.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main() -> int:
    configure_console_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--credential-file", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--screenshot", type=Path, default=DEFAULT_SCREENSHOT)
    parser.add_argument("--hold-ms", type=int, default=0)
    parser.add_argument("--no-final-enter", action="store_true")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as exc:
        line = f"{datetime.now().isoformat(timespec='seconds')} 치명 오류: {exc}"
        print(line, flush=True)
        append_log_file(args.log, line)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
