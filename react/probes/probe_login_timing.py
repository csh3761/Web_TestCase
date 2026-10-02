# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from re_user_trash import configure_console_output, load_json, DEFAULT_CONFIG  # noqa: E402


def mark(label: str, t0: float) -> float:
    now = time.monotonic()
    print(f"{label}: {now - t0:.2f}s", flush=True)
    return now


async def run() -> int:
    config = load_json(DEFAULT_CONFIG)
    selectors = config["selectors"]

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
        context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
        page = await context.new_page()

        t0 = time.monotonic()
        await page.goto(config["login_url"], wait_until="domcontentloaded")
        t1 = mark("[1] goto(domcontentloaded)", t0)

        await page.locator(selectors["username"]).first.wait_for(state="visible", timeout=5000)
        await page.locator(selectors["username"]).first.fill("sysadmin")
        t2 = mark("[2] username fill", t1)

        await page.locator(selectors["password"]).first.fill("1234")
        t3 = mark("[3] password fill", t2)

        try:
            async with page.expect_response(
                lambda response: "login" in response.url.lower() and response.request.method == "POST",
                timeout=8000,
            ) as response_info:
                await page.locator(selectors["submit"]).first.click()
            response = await response_info.value
            print(f"    response status={response.status}", flush=True)
        except Exception as exc:
            print(f"    expect_response failed: {exc}", flush=True)
        t4 = mark("[4] submit + expect_response", t3)

        try:
            await page.locator(selectors.get("enterprise_trash", "a[href='/enterprise-trash']")).first.wait_for(
                state="visible", timeout=8000
            )
        except Exception as exc:
            print(f"    enterprise_trash wait failed: {exc}", flush=True)
        t5 = mark("[5] wait enterprise_trash link visible", t4)

        mark("[TOTAL]", t0)

        await context.close()
        await browser.close()
        return 0


if __name__ == "__main__":
    configure_console_output()
    raise SystemExit(asyncio.run(run()))
