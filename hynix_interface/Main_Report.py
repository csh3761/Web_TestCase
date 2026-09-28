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
sys.path.insert(0, str(PROJECT_ROOT / "HYNIX"))

import explorer_path_test as explorer  # noqa: E402
import login_session_check as login  # noqa: E402

DEFAULT_REPORT = PROJECT_ROOT / "reports" / "Main_Report.json"
DEFAULT_LOG = PROJECT_ROOT / "reports" / "Main_Report.log"


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


def local_file_names(csv_path: Path, root: Path, user_id: str) -> tuple[Path, list[str]]:
    documents = explorer.load_user_documents(csv_path, user_id)
    folder = explorer.resolve_user_folder(root, documents[0])
    if not folder.exists():
        raise FileNotFoundError(f"사용자 ID 폴더가 없습니다: {folder}")
    return folder, [path.name for path in explorer.folder_files(folder)]


async def login_and_capture_auth(page: Any, account: login.Account, password: str, config: dict[str, Any]) -> dict[str, Any]:
    captured_auth_header = ""

    def capture_auth_header(request: Any) -> None:
        nonlocal captured_auth_header
        auth_header = request.headers.get("authorization", "")
        if "/api/v1/" in request.url and auth_header:
            captured_auth_header = auth_header

    page.on("request", capture_auth_header)
    selectors = config["selectors"]
    await page.goto(config["login_url"], wait_until="domcontentloaded")
    await login.fill_first_visible(page, selectors["username"], account.user_id)
    await login.fill_first_visible(page, selectors["password"], password)
    login_submit_status, auth_header = await login.submit_login_and_wait_response(page, selectors["submit"])

    login_wait_status = await login.wait_after_login(page, config)
    if not auth_header and not captured_auth_header:
        frontend_auth_wait_status = await login.wait_for_frontend_auth_settle(page)
    else:
        frontend_auth_wait_status = "SKIPPED_AUTH_HEADER_ALREADY_CAPTURED"

    auth_header = auth_header or captured_auth_header
    auth_wait_status = await login.wait_for_authenticated_session(page, config, auth_header)

    return {
        "auth_header": auth_header,
        "login_submit_status": login_submit_status,
        "login_wait_status": login_wait_status,
        "frontend_auth_wait_status": frontend_auth_wait_status,
        "auth_header_status": "CAPTURED" if auth_header else "NOT_FOUND",
        "auth_wait_status": auth_wait_status,
    }


async def verify_one_account(playwright: Any, account: login.Account, password: str, config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
    context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
    page = await context.new_page()
    log_lines: list[str] = []

    result: dict[str, Any] = {
        "user_id": account.user_id,
        "user_name": account.user_name,
        "department_path": account.department_path,
        "status": "UNKNOWN",
        "log": log_lines,
    }

    def log_line(message: str) -> None:
        line = f"[{account.user_id} {account.user_name}] {message}"
        log_lines.append(line)
        print(line, flush=True)

    try:
        log_line("LOGIN_START")
        login_result = await login_and_capture_auth(page, account, password, config)
        auth_header = login_result.pop("auth_header")
        result.update(login_result)
        log_line(f"LOGIN_OK: {result['login_submit_status']} / {result['auth_wait_status']}")

        log_line("WEB_FOLDER_NAVIGATION_START")
        navigation = await login.move_to_default_folder(page, config, account)
        result.update(navigation)
        folder_id = navigation["selected_folder_id"]
        log_line(f"WEB_FOLDER_NAVIGATION_OK: folderId={folder_id}, path={navigation.get('upload_subfolder_path')}")

        local_folder, expected_files = local_file_names(args.csv, args.root, account.user_id)
        result["local_folder"] = str(local_folder)
        result["expected_file_count"] = len(expected_files)
        result["expected_files"] = expected_files
        log_line(f"LOCAL_FILE_SCAN_OK: count={len(expected_files)}")

        status_code, payload = await login.check_session(page, config, folder_id, auth_header)
        web_names = sorted(login.collect_document_names(payload))
        result["document_list_status"] = status_code
        result["web_file_count"] = len(web_names)
        result["web_files"] = web_names
        result["web_files_sample"] = web_names[:20]
        log_line(f"WEB_DOCUMENT_LIST_OK: http={status_code}, name_count={len(web_names)}")

        expected_set = set(expected_files)
        web_set = set(web_names)
        verified_files = sorted(expected_set & web_set)
        missing_files = sorted(expected_set - web_set)
        extra_web_files = sorted(web_set - expected_set)

        result["verified_file_count"] = len(verified_files)
        result["verified_files"] = verified_files
        result["missing_file_count"] = len(missing_files)
        result["missing_files"] = missing_files
        result["extra_web_file_count"] = len(extra_web_files)
        result["extra_web_files_sample"] = extra_web_files[:20]

        if not expected_files:
            result["status"] = "NO_LOCAL_FILES"
            log_line("VERIFY_NO_LOCAL_FILES")
        elif missing_files:
            result["status"] = "VERIFY_MISSING"
            log_line(f"VERIFY_MISSING: missing={len(missing_files)}, verified={len(verified_files)}")
        else:
            result["status"] = "VERIFY_OK"
            log_line(f"VERIFY_OK: verified={len(verified_files)}")

        if args.logout:
            result["logout"] = await login.logout(page, config)
            log_line(f"LOGOUT: {result['logout']}")
        else:
            result["logout"] = "SKIPPED_BY_OPTION"
    except Exception as exc:
        result["status"] = "FAILED"
        result["message"] = str(exc)
        log_line(f"VERIFY_FAILED: {exc}")
    finally:
        await context.close()
        await browser.close()

    return result


def select_accounts(args: argparse.Namespace) -> list[login.Account]:
    accounts = login.load_all_accounts(args.csv, args.limit)
    if args.user_id:
        accounts = [account for account in accounts if account.user_id == args.user_id]
        if not accounts:
            raise ValueError(f"CSV에서 사용자 ID를 찾지 못했습니다: {args.user_id}")
    return accounts


def build_report(results: list[dict[str, Any]], total_users: int) -> dict[str, Any]:
    ok_statuses = {"VERIFY_OK"}
    failed_results = [item for item in results if item.get("status") not in ok_statuses]
    return {
        "mode": "MAIN_UPLOAD_VERIFICATION_REPORT",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "total_users": total_users,
        "processed_count": len(results),
        "pending_count": max(total_users - len(results), 0),
        "ok_count": len(results) - len(failed_results),
        "failed_count": len(failed_results),
        "ok_ids": [item["user_id"] for item in results if item.get("status") in ok_statuses],
        "failed_ids": [item["user_id"] for item in failed_results],
        "results": results,
    }


def write_report_files(args: argparse.Namespace, report: dict[str, Any]) -> None:
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    args.log.parent.mkdir(parents=True, exist_ok=True)
    log_text = "\n".join(line for item in report["results"] for line in item.get("log", []))
    args.log.write_text(log_text + ("\n" if log_text else ""), encoding="utf-8")


async def run(args: argparse.Namespace) -> int:
    configure_playwright_browsers_path()
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright가 설치되어 있지 않습니다. "
            f"{PROJECT_ROOT}\\.venv\\Scripts\\python.exe -m pip install playwright 후 "
            f"{PROJECT_ROOT}\\.venv\\Scripts\\python.exe -m playwright install chromium 을 실행하세요."
        ) from exc

    config = login.load_json(args.config)
    password = login.get_common_password(args.password_file)
    accounts = select_accounts(args)
    results: list[dict[str, Any]] = []

    async with async_playwright() as playwright:
        for account in accounts:
            results.append(await verify_one_account(playwright, account, password, config, args))
            write_report_files(args, build_report(results, len(accounts)))

    report = build_report(results, len(accounts))
    write_report_files(args, report)

    print(json.dumps({key: report[key] for key in ["mode", "total_users", "ok_count", "failed_count", "ok_ids", "failed_ids"]}, ensure_ascii=False, indent=2))
    print(f"Report: {args.report}")
    print(f"Log: {args.log}")
    return 0 if not report["failed_count"] else 1


def pause_before_exit(enabled: bool) -> None:
    if not enabled:
        return
    try:
        input("\n완료되었습니다. 로그 확인 후 Enter 키를 누르면 창을 닫습니다.")
    except EOFError:
        pass


def main() -> int:
    explorer.configure_console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=login.DEFAULT_CSV)
    parser.add_argument("--config", type=Path, default=login.DEFAULT_CONFIG)
    parser.add_argument("--password-file", type=Path, default=login.DEFAULT_PASSWORD_FILE)
    parser.add_argument("--root", type=Path, default=explorer.DEFAULT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--user-id", default="")
    parser.add_argument("--logout", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--pause-on-exit", action=argparse.BooleanOptionalAction, default=bool(getattr(sys, "frozen", False)))
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    finally:
        pause_before_exit(args.pause_on_exit)


if __name__ == "__main__":
    raise SystemExit(main())
