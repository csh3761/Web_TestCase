# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import login_session_check as login


PROJECT_ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    from playwright.async_api import async_playwright

    config = login.load_json(PROJECT_ROOT / "config" / "trash_login_config.json")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
        context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
        page = await context.new_page()
        responses: list[dict[str, object]] = []
        page.on(
            "response",
            lambda response: responses.append(
                {
                    "status": response.status,
                    "url": response.url,
                    "resource_type": response.request.resource_type,
                }
            ),
        )
        await page.goto(config["login_url"], wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)
        frames = []
        for frame in page.frames:
            frames.append(
                {
                    "url": frame.url,
                    "name": frame.name,
                    "inputs": await frame.locator("input, textarea").evaluate_all(
                        """(nodes) => nodes.map((node) => ({
                            tag: node.tagName,
                            type: node.getAttribute("type"),
                            name: node.getAttribute("name"),
                            id: node.getAttribute("id"),
                            placeholder: node.getAttribute("placeholder"),
                            aria: node.getAttribute("aria-label"),
                            autocomplete: node.getAttribute("autocomplete"),
                            visible: Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length)
                        }))"""
                    ),
            "buttons": await frame.locator("button, input[type='submit'], [role='button']").evaluate_all(
                        """(nodes) => nodes.slice(0, 50).map((node) => ({
                            tag: node.tagName,
                            type: node.getAttribute("type"),
                            text: node.innerText || node.getAttribute("value"),
                            aria: node.getAttribute("aria-label"),
                            id: node.getAttribute("id"),
                            name: node.getAttribute("name"),
                            visible: Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length)
                        }))"""
                    ),
                    "body": (await frame.locator("body").inner_text(timeout=3000))[:1500],
                }
            )

        data = {
            "url": page.url,
            "title": await page.title(),
            "responses_sample": responses[:80],
            "frames": frames,
            "inputs": await page.locator("input, textarea").evaluate_all(
                """(nodes) => nodes.map((node) => ({
                    tag: node.tagName,
                    type: node.getAttribute("type"),
                    name: node.getAttribute("name"),
                    id: node.getAttribute("id"),
                    placeholder: node.getAttribute("placeholder"),
                    aria: node.getAttribute("aria-label"),
                    autocomplete: node.getAttribute("autocomplete"),
                    visible: Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length)
                }))"""
            ),
            "forms": await frame.locator("form").evaluate_all(
                """(nodes) => nodes.map((node) => ({
                    id: node.getAttribute("id"),
                    name: node.getAttribute("name"),
                    action: node.getAttribute("action"),
                    method: node.getAttribute("method"),
                    text: node.innerText
                }))"""
            ),
            "links": await frame.locator("a, [onclick]").evaluate_all(
                """(nodes) => nodes.slice(0, 80).map((node) => ({
                    tag: node.tagName,
                    text: node.innerText || node.textContent || "",
                    title: node.getAttribute("title"),
                    href: node.getAttribute("href"),
                    onclick: node.getAttribute("onclick"),
                    id: node.getAttribute("id"),
                    className: node.getAttribute("class"),
                    visible: Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length)
                }))"""
            ),
            "buttons": await page.locator("button, input[type='submit'], [role='button']").evaluate_all(
                """(nodes) => nodes.slice(0, 50).map((node) => ({
                    tag: node.tagName,
                    type: node.getAttribute("type"),
                    text: node.innerText || node.getAttribute("value"),
                    aria: node.getAttribute("aria-label"),
                    id: node.getAttribute("id"),
                    name: node.getAttribute("name"),
                    visible: Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length)
                }))"""
            ),
            "body": (await page.locator("body").inner_text(timeout=3000))[:1500],
        }
        report = PROJECT_ROOT / "reports" / "otcs_login_dom_probe.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(data, ensure_ascii=True, indent=2))
        print(f"Report: {report}")
        await context.close()
        await browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
