# -*- coding: utf-8 -*-
"""my work 삭제 후 완료 알림(alert) 감지 진단 테스트.

목적: 기존 감지 로직(DOM wait_for_delete_notice_forever / API returnMessage)이
my work 삭제에서는 완료 알림을 못 잡는 문제의 원인을 밝히기 위한 진단 도구다.
"정상/실패 판정"이 목적이 아니라, 삭제 확인 클릭 직후부터 일정 시간 동안
- 페이지 HTML 원본(변화가 있을 때마다)
- 발생한 모든 POST 응답(URL/상태/본문 원문)
- 네이티브 dialog 이벤트
를 그대로 파일로 긁어와 남긴다. 실제로 무엇이 뜨는지 원본 증거를 확보한 뒤,
그 결과를 보고 감지 로직(선택자/패턴)을 맞춰 고친다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
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
)
from user_trash import (  # noqa: E402
    WORKBOXES,
    click_delete_menu_and_confirm,
    open_user_trash,
    read_account_from_user,
    switch_workbox,
)


def runtime_output_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / relative_path
    return PROJECT_ROOT / relative_path


DEFAULT_REPORT = runtime_output_path(r"reports\user_trash_alert_test_report.json")
DEFAULT_LOG = runtime_output_path(r"reports\user_trash_alert_test.log")
DEFAULT_DUMP_DIR = runtime_output_path(r"reports\user_trash_alert_test_dump")

MY_WORK = next(box for box in WORKBOXES if box["value"] == "u")

# wait_for_delete_notice_forever와 동일한 선택자/패턴이지만, 무한 루프 없이 "현재
# 시점에 매칭되는 게 있는가"만 1회 확인한다 - 캡처 루프에서 매 라운드 호출해서
# "몇 번째 라운드에 처음 걸렸는지"를 남기기 위함이다.
CHECK_NOTICE_ONCE_SCRIPT = """() => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const noticeSelectors = [
        ".toast", ".toast-message", ".alert", ".swal2-popup", ".modal", ".bootbox",
        "[role='alert']", "[aria-live]", "[class*='toast']", "[class*='alert']",
        "[class*='notification']", "[class*='message']"
    ];
    const cancelButtonText = /Cancel|취소|아니오|No/i;
    const notices = Array.from(document.querySelectorAll(noticeSelectors.join(","))).filter((element) => {
        if (!visible(element)) return false;
        const text = (element.innerText || element.textContent || "").replace(/\\s+/g, " ").trim();
        if (!text.length) return false;
        const hasVisibleCancelButton = Array.from(
            element.querySelectorAll("button, a, input[type='button'], input[type='submit']")
        ).some((button) => {
            if (!visible(button)) return false;
            const buttonText = (button.innerText || button.textContent || button.value || "").replace(/\\s+/g, " ").trim();
            return cancelButtonText.test(buttonText);
        });
        return !hasVisibleCancelButton;
    });
    return notices.map((el) => ({
        tag: el.tagName,
        id: el.id || "",
        className: (typeof el.className === "string") ? el.className : "",
        text: (el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim().slice(0, 500),
        outerHTML: el.outerHTML.slice(0, 3000),
    }));
}"""


async def capture_delete_evidence(
    page: Any,
    frame: Any,
    dump_dir: Path,
    capture_seconds: float,
    poll_interval: float,
    lines: list[str],
    log_path: Path | None,
) -> dict[str, Any]:
    """삭제 확인 클릭 이후 capture_seconds 동안 페이지 원본/네트워크/다이얼로그를 통째로 긁는다."""
    dump_dir.mkdir(parents=True, exist_ok=True)

    post_responses: list[dict[str, Any]] = []
    dialog_events: list[dict[str, Any]] = []

    async def handle_response(response: Any) -> None:
        try:
            if response.request.method != "POST":
                return
            content_type = response.headers.get("content-type", "")
            body_text = ""
            if "json" in content_type or "text" in content_type:
                try:
                    body_text = await response.text()
                except Exception:
                    body_text = "<본문 읽기 실패>"
            entry = {
                "url": response.url,
                "status": response.status,
                "contentType": content_type,
                "body": body_text[:4000],
                "capturedAt": datetime.now().isoformat(timespec="milliseconds"),
            }
            post_responses.append(entry)
            log_line(lines, f"[POST 캡처] {response.status} {response.url} body={body_text[:200]!r}", log_path)
        except Exception as exc:
            log_line(lines, f"[POST 캡처 실패] {exc}", log_path)

    async def handle_dialog(dialog: Any) -> None:
        dialog_events.append(
            {
                "type": dialog.type,
                "message": dialog.message,
                "capturedAt": datetime.now().isoformat(timespec="milliseconds"),
            }
        )
        log_line(lines, f"[네이티브 dialog 감지] type={dialog.type} message={dialog.message!r}", log_path)
        await dialog.accept()

    page.on("response", handle_response)
    page.on("dialog", handle_dialog)

    html_snapshots: list[dict[str, Any]] = []
    notice_hits: list[dict[str, Any]] = []
    last_html = ""
    started = time.monotonic()
    round_no = 0
    try:
        while time.monotonic() - started < capture_seconds:
            round_no += 1
            elapsed_ms = int((time.monotonic() - started) * 1000)

            try:
                html = await frame.content()
            except Exception:
                html = await page.content()
            if html != last_html:
                file_path = dump_dir / f"snapshot_round{round_no:03d}_{elapsed_ms}ms.html"
                file_path.write_text(html, encoding="utf-8")
                html_snapshots.append(
                    {
                        "round": round_no,
                        "elapsedMs": elapsed_ms,
                        "file": str(file_path),
                        "length": len(html),
                    }
                )
                log_line(lines, f"[HTML 변화 감지] round={round_no} elapsedMs={elapsed_ms} file={file_path.name}", log_path)
                last_html = html

            try:
                frame_hits = await frame.locator("body").evaluate(CHECK_NOTICE_ONCE_SCRIPT)
            except Exception:
                frame_hits = []
            try:
                page_hits = await page.locator("body").evaluate(CHECK_NOTICE_ONCE_SCRIPT)
            except Exception:
                page_hits = []
            hits = [{"scope": "frame", **hit} for hit in frame_hits] + [
                {"scope": "page-top", **hit} for hit in page_hits
            ]
            if hits:
                notice_hits.append({"round": round_no, "elapsedMs": elapsed_ms, "elements": hits})
                log_line(
                    lines,
                    f"[알림 후보 감지] round={round_no} elapsedMs={elapsed_ms} count={len(hits)} "
                    f"scope={hits[0].get('scope')} 첫번째 text={hits[0].get('text', '')!r}",
                    log_path,
                )

            if elapsed_ms <= 6000:
                shot_path = dump_dir / f"round{round_no:03d}_{elapsed_ms}ms.png"
                try:
                    await page.screenshot(path=str(shot_path))
                except Exception:
                    pass

            await asyncio.sleep(poll_interval)
    finally:
        page.remove_listener("response", handle_response)
        page.remove_listener("dialog", handle_dialog)

    final_screenshot = dump_dir / "final_screenshot.png"
    try:
        await page.screenshot(path=str(final_screenshot), full_page=True)
    except Exception:
        final_screenshot = None

    return {
        "htmlSnapshots": html_snapshots,
        "postResponses": post_responses,
        "dialogEvents": dialog_events,
        "noticeCandidateHits": notice_hits,
        "finalScreenshot": str(final_screenshot) if final_screenshot else "",
        "captureSeconds": capture_seconds,
        "rounds": round_no,
    }


async def run(args: argparse.Namespace) -> int:
    configure_playwright_browsers_path()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    account, password = read_account_from_user(args)
    args.dump_dir = args.dump_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
    lines: list[str] = []
    result: dict[str, Any] = {
        "mode": "USER_TRASH_ALERT_DETECT_TEST",
        "user_id": account.user_id,
        "workbox": MY_WORK["name"],
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

            log_line(lines, "유저 휴지통 이동 시작", args.log)
            result["trash_navigation"] = await open_user_trash(page)
            log_line(lines, "유저 휴지통 이동 성공", args.log)

            log_line(lines, f"{MY_WORK['name']} 선택", args.log)
            result["switch"] = await switch_workbox(page, MY_WORK)

            api_listing = await fetch_trash_items_via_api(
                page, box_gubun=str(MY_WORK["value"]).upper(), api_path=USER_TRASH_LIST_API_PATH
            )
            log_line(
                lines,
                f"목록 확인(API 기준): 전체 {api_listing['totalCount']}건 문서 {api_listing['documentCount']}건",
                args.log,
            )
            if api_listing["documentCount"] == 0:
                result["status"] = "NO_DOCUMENTS_TO_DELETE"
                log_line(lines, "삭제 대상 문서 없음 - 테스트를 진행할 수 없습니다.", args.log)
                return 0

            selection = await select_document_checkboxes(
                page, selection_limit=args.selection_limit, folder_titles=api_listing["folderTitles"]
            )
            result["document_selection"] = selection
            log_line(lines, f"문서 선택 완료: {selection['selectedCount']}건", args.log)
            if selection["selectedCount"] == 0:
                result["status"] = "NO_DOCUMENTS_SELECTED"
                return 0

            frame = await main_frame(page)
            context_menu = await open_context_menu_on_first_visible_selected_document(
                page, args.context_menu_timeout_ms
            )
            result["context_menu"] = context_menu
            log_line(lines, f"우클릭 메뉴: {context_menu['status']}", args.log)
            if context_menu["status"] != "CONTEXT_MENU_OPENED":
                raise RuntimeError(f"우클릭 메뉴가 열리지 않았습니다: {context_menu['status']}")

            log_line(lines, "Delete 클릭 + 확인 모달 처리 시작", args.log)
            click_result = await click_delete_menu_and_confirm(frame, page, args.context_menu_timeout_ms)
            result["click_result"] = click_result
            log_line(
                lines,
                f"클릭 결과: menu={click_result['menu_item'].get('status')} "
                f"confirm={click_result['confirm_result'].get('status')}",
                args.log,
            )

            log_line(
                lines,
                f"증거 캡처 시작: {args.capture_seconds}초 동안 HTML/POST/dialog 원본을 긁습니다 "
                f"(저장 위치: {args.dump_dir})",
                args.log,
            )
            evidence = await capture_delete_evidence(
                page, frame, args.dump_dir, args.capture_seconds, args.poll_interval, lines, args.log
            )
            result["evidence"] = evidence

            log_line(
                lines,
                (
                    f"캡처 종료: HTML 변화 {len(evidence['htmlSnapshots'])}회, "
                    f"POST 응답 {len(evidence['postResponses'])}건, "
                    f"dialog {len(evidence['dialogEvents'])}건, "
                    f"알림 후보 감지 {len(evidence['noticeCandidateHits'])}회"
                ),
                args.log,
            )
            if evidence["noticeCandidateHits"]:
                result["status"] = "NOTICE_CANDIDATE_FOUND"
            elif evidence["postResponses"]:
                result["status"] = "NO_NOTICE_BUT_POST_CAPTURED"
            else:
                result["status"] = "NO_EVIDENCE_CAPTURED"
            log_line(lines, f"최종 결과: {result['status']}", args.log)
            return 0
        except Exception as exc:
            result["status"] = "FAILED"
            result["message"] = str(exc)
            try:
                result["failure_snapshot"] = await snapshot_page(page)
            except Exception:
                pass
            log_line(lines, f"실패: {exc}", args.log)
            return 1
        finally:
            await context.close()
            await browser.close()
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    explorer.configure_console()
    configure_console_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--dump-dir", type=Path, default=DEFAULT_DUMP_DIR)
    parser.add_argument("--selection-limit", type=int, default=1, help="0=전체 선택, 기본 1건만(테스트용)")
    parser.add_argument("--context-menu-timeout-ms", type=int, default=5000)
    parser.add_argument("--capture-seconds", type=float, default=25.0)
    parser.add_argument("--poll-interval", type=float, default=0.15)
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as exc:
        line = f"{datetime.now().isoformat(timespec='seconds')} 치명 오류: {exc}"
        print(line, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
