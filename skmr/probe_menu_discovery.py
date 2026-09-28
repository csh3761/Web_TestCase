# -*- coding: utf-8 -*-
"""skmr.ifns.work 로그인 후 전체 메뉴/기능 구조를 DOM으로 훑는 probe.

react01 폴더에서 썼던 방식과 동일하게, 네트워크 트래픽이 아니라 로그인 후 렌더링된
DOM(nav/링크/메뉴 텍스트)을 직접 스캔해서 이 앱에 어떤 기능(메뉴)들이 있는지
목록화한다. 이후 단위 테스트 케이스 작성의 기초 자료로 쓴다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://skmr.ifns.work/"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "skmr_menu_discovery.json"
DEFAULT_SCREENSHOT = PROJECT_ROOT / "reports" / "skmr_after_login.png"

USERNAME_SELECTOR = "input[type='text']"
PASSWORD_SELECTOR = "input[type='password']"
SUBMIT_SELECTOR = "button[type='submit'].login-form__submit"

# 메뉴/네비게이션으로 보이는 모든 클릭 가능 요소를 폭넓게 수집한다.
MENU_SCAN_SCRIPT = """() => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();

    const links = Array.from(document.querySelectorAll("a[href]")).filter(visible).map((node) => ({
        tag: "A",
        text: cleanText(node.innerText || node.textContent || ""),
        href: node.getAttribute("href") || "",
        className: node.getAttribute("class") || "",
    }));

    const menuItems = Array.from(document.querySelectorAll(
        "[role='menuitem'], [class*='menu-item'], [class*='menuitem'], [class*='nav-item'], [class*='sidebar']"
    )).filter(visible).map((node) => ({
        tag: node.tagName,
        text: cleanText(node.innerText || node.textContent || "").slice(0, 80),
        className: node.getAttribute("class") || "",
        role: node.getAttribute("role") || "",
    }));

    const buttons = Array.from(document.querySelectorAll("button")).filter(visible).map((node) => ({
        tag: "BUTTON",
        text: cleanText(node.innerText || node.textContent || node.getAttribute("aria-label") || "").slice(0, 80),
        className: node.getAttribute("class") || "",
    }));

    return {
        pageTitle: document.title,
        pageUrl: location.href,
        linkCount: links.length,
        links,
        menuItemCount: menuItems.length,
        menuItems,
        buttonCount: buttons.length,
        buttons,
        bodyTextSample: cleanText(document.body.innerText || "").slice(0, 4000),
    };
}"""


def configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(line_buffering=True, write_through=True)
        except Exception:
            pass


async def fill_and_login(page: Any, username: str, password: str, login_url: str) -> dict[str, Any]:
    before_url = page.url
    await page.goto(login_url, wait_until="domcontentloaded")
    await page.locator(USERNAME_SELECTOR).first.fill(username)
    await page.locator(PASSWORD_SELECTOR).first.fill(password)

    response_status = "LOGIN_RESPONSE_NOT_CAPTURED"
    try:
        async with page.expect_response(
            lambda response: "login" in response.url.lower() and response.request.method == "POST",
            timeout=8000,
        ) as response_info:
            await page.locator(SUBMIT_SELECTOR).first.click()
        response = await response_info.value
        response_status = f"LOGIN_RESPONSE:{response.status}"
    except Exception:
        try:
            await page.locator(PASSWORD_SELECTOR).first.press("Enter")
        except Exception:
            pass

    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    await page.wait_for_timeout(2000)

    return {
        "login_response_status": response_status,
        "before_url": before_url,
        "page_url": page.url,
        "navigated": page.url != before_url,
    }


async def run(args: argparse.Namespace) -> int:
    result: dict[str, Any] = {
        "mode": "SKMR_MENU_DISCOVERY_PROBE",
        "username": args.username,
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=args.headless)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        try:
            print(f"로그인 시작: {args.username}", flush=True)
            login_result = await fill_and_login(page, args.username, args.password, args.url)
            result["login"] = login_result
            print(f"로그인 결과: {login_result['login_response_status']} -> {login_result['page_url']}", flush=True)

            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(args.screenshot), full_page=True)
            result["after_login_screenshot"] = str(args.screenshot)

            scan = await page.evaluate(MENU_SCAN_SCRIPT)
            result["menu_scan"] = scan
            print(
                f"메뉴 스캔: 링크 {scan['linkCount']}개, 메뉴류 요소 {scan['menuItemCount']}개, "
                f"버튼 {scan['buttonCount']}개",
                flush=True,
            )
            result["status"] = "PROBE_DONE"
            return 0
        except Exception as exc:
            result["status"] = "FAILED"
            result["message"] = str(exc)
            print(f"실패: {exc}", flush=True)
            return 1
        finally:
            await context.close()
            await browser.close()
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Report: {args.report}", flush=True)


def main() -> int:
    configure_console_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--screenshot", type=Path, default=DEFAULT_SCREENSHOT)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
