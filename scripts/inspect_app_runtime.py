from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "HYNIX"))

import login_session_check as login


DEFAULT_REPORT = PROJECT_ROOT / "reports" / "runtime_inspection.json"


async def inject_dom_observer(page: Any) -> None:
    await page.evaluate(
        """() => {
            window.__codexDomEvents = [];
            const observer = new MutationObserver((mutations) => {
                for (const mutation of mutations) {
                    for (const node of mutation.addedNodes) {
                        if (!(node instanceof HTMLElement)) continue;
                        const text = node.textContent?.trim()?.slice(0, 120) || "";
                        const className = node.getAttribute("class") || "";
                        const ariaLabel = node.getAttribute("aria-label") || "";
                        const role = node.getAttribute("role") || "";
                        if (className || ariaLabel || role || text) {
                            window.__codexDomEvents.push({
                                tag: node.tagName.toLowerCase(),
                                className,
                                ariaLabel,
                                role,
                                text
                            });
                        }
                    }
                }
                window.__codexDomEvents = window.__codexDomEvents.slice(-200);
            });
            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ["class", "aria-expanded", "aria-label", "role"]
            });
        }"""
    )


async def collect_dom_snapshot(page: Any) -> dict[str, Any]:
    return await page.evaluate(
        """() => ({
            url: location.href,
            title: document.title,
            buttons: Array.from(document.querySelectorAll("button")).map((button) => ({
                className: button.getAttribute("class"),
                text: button.textContent?.trim(),
                ariaLabel: button.getAttribute("aria-label"),
                title: button.getAttribute("title"),
                ariaExpanded: button.getAttribute("aria-expanded"),
                role: button.getAttribute("role")
            })),
            treeRows: Array.from(document.querySelectorAll(".explorer-tree__row")).map((row) => ({
                text: row.textContent?.trim(),
                key: row.getAttribute("data-tree-key"),
                depth: row.getAttribute("style")
            })),
            domEvents: window.__codexDomEvents || []
        })"""
    )


async def run(args: argparse.Namespace) -> int:
    from playwright.async_api import async_playwright

    config = login.load_json(args.config)
    account = login.load_first_accounts(args.csv, args.limit)[0]
    password = login.get_common_password(args.password_file)

    requests: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
        context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
        page = await context.new_page()

        def capture_request(request: Any) -> None:
            if "/api/v1/" not in request.url:
                return
            requests.append(
                {
                    "method": request.method,
                    "url": request.url,
                    "hasAuthorization": bool(request.headers.get("authorization")),
                    "contentType": request.headers.get("content-type"),
                }
            )

        async def capture_response(response: Any) -> None:
            if "/api/v1/" not in response.url:
                return
            responses.append(
                {
                    "status": response.status,
                    "url": response.url,
                    "contentType": response.headers.get("content-type"),
                }
            )

        page.on("request", capture_request)
        page.on("response", capture_response)

        selectors = config["selectors"]
        await page.goto(config["login_url"], wait_until="domcontentloaded")
        await login.fill_first_visible(page, selectors["username"], account.user_id)
        await login.fill_first_visible(page, selectors["password"], password)
        login_submit_status, auth_header = await login.submit_login_and_wait_response(page, selectors["submit"])
        await login.wait_after_login(page, config)
        await inject_dom_observer(page)
        await login.wait_for_frontend_auth_settle(page)
        navigation = await login.move_to_default_folder(page, config, account)
        await login.logout(page, config)
        await page.wait_for_timeout(500)

        report = {
            "account": {
                "user_id": account.user_id,
                "user_name": account.user_name,
                "department_path": account.department_path,
            },
            "login_submit_status": login_submit_status,
            "auth_header_captured_from_login_response": bool(auth_header),
            "navigation": navigation,
            "requests": requests,
            "responses": responses,
            "dom": await collect_dom_snapshot(page),
        }

        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))

        await context.close()
        await browser.close()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=login.DEFAULT_CSV)
    parser.add_argument("--config", type=Path, default=login.DEFAULT_CONFIG)
    parser.add_argument("--password-file", type=Path, default=login.DEFAULT_PASSWORD_FILE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
