# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import login_session_check as login


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REPORT = PROJECT_ROOT / "reports" / "connection_test_first_user.json"


async def run(args: argparse.Namespace) -> int:
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"Playwright is not installed. Use {PROJECT_ROOT}\\.venv\\Scripts\\python.exe -m pip install playwright "
            f"and {PROJECT_ROOT}\\.venv\\Scripts\\python.exe -m playwright install chromium."
        ) from exc

    config = login.load_json(args.config)
    account = login.load_all_accounts(args.csv, 1)[0]
    password = login.get_common_password(args.password_file)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
        context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
        page = await context.new_page()
        captured_auth_header = ""

        def capture_auth_header(request: Any) -> None:
            nonlocal captured_auth_header
            auth_header = request.headers.get("authorization", "")
            if "/api/v1/" in request.url and auth_header:
                captured_auth_header = auth_header

        page.on("request", capture_auth_header)

        result: dict[str, Any] = {
            "mode": "CONNECTION_TEST_FIRST_USER",
            "site_url": config["site_url"],
            "login_url": config["login_url"],
            "user_id": account.user_id,
            "user_name": account.user_name,
            "department_path": account.department_path,
            "status": "UNKNOWN",
        }

        try:
            selectors = config["selectors"]
            await page.goto(config["login_url"], wait_until="domcontentloaded")
            result["goto_status"] = "OK"

            await login.fill_first_visible(page, selectors["username"], account.user_id)
            await login.fill_first_visible(page, selectors["password"], password)
            login_submit_status, auth_header = await login.submit_login_and_wait_response(page, selectors["submit"])
            result["login_submit_status"] = login_submit_status
            result["login_wait_status"] = await login.wait_after_login(page, config)

            if not auth_header and not captured_auth_header:
                result["frontend_auth_wait_status"] = await login.wait_for_frontend_auth_settle(page)
            else:
                result["frontend_auth_wait_status"] = "SKIPPED_AUTH_HEADER_ALREADY_CAPTURED"

            auth_header = auth_header or captured_auth_header
            result["auth_header_status"] = "CAPTURED" if auth_header else "NOT_FOUND"
            result["auth_wait_status"] = await login.wait_for_authenticated_session(page, config, auth_header)
            result["status"] = "CONNECTION_AND_LOGIN_OK"
        except Exception as exc:
            result["status"] = "FAILED"
            result["message"] = str(exc)
        finally:
            await context.close()
            await browser.close()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Report: {args.report}")
    return 0 if result["status"] == "CONNECTION_AND_LOGIN_OK" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=login.DEFAULT_CSV)
    parser.add_argument("--config", type=Path, default=login.DEFAULT_CONFIG)
    parser.add_argument("--password-file", type=Path, default=login.DEFAULT_PASSWORD_FILE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
