# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import login_session_check as login


PROJECT_ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    from playwright.async_api import async_playwright

    config = login.load_json(PROJECT_ROOT / "config" / "login_config.json")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
        context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
        page = await context.new_page()
        requests: list[dict[str, object]] = []
        console_messages: list[str] = []
        page_errors: list[str] = []

        page.on("console", lambda message: console_messages.append(f"{message.type}: {message.text}"))
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "response",
            lambda response: requests.append(
                {
                    "status": response.status,
                    "url": response.url,
                    "resource_type": response.request.resource_type,
                }
            ),
        )

        await page.goto(config["login_url"], wait_until="domcontentloaded")
        await page.wait_for_timeout(15000)
        data = {
            "url": page.url,
            "title": await page.title(),
            "request_count": len(requests),
            "responses_sample": requests[:50],
            "bad_responses": [item for item in requests if int(item["status"]) >= 400][:50],
            "console_messages": console_messages[:50],
            "page_errors": page_errors[:20],
            "inputs": await page.locator("input").evaluate_all(
                """(nodes) => nodes.map((node) => ({
                    type: node.type,
                    name: node.name,
                    id: node.id,
                    placeholder: node.placeholder,
                    value: node.value,
                    visible: Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length)
                }))"""
            ),
            "buttons": await page.locator("button").evaluate_all(
                """(nodes) => nodes.slice(0, 20).map((node) => ({
                    text: node.innerText,
                    aria: node.getAttribute("aria-label"),
                    visible: Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length)
                }))"""
            ),
            "body": (await page.locator("body").inner_text(timeout=3000))[:1000],
        }
        report = PROJECT_ROOT / "reports" / "page_login_dom_probe.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"Report: {report}")
        await context.close()
        await browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
