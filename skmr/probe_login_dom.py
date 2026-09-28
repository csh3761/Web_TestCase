# -*- coding: utf-8 -*-
"""skmr.ifns.work 로그인 페이지 DOM 구조 확인용 1회성 probe.

react01/probe_login_dom.py와 동일한 방식: 로그인 페이지를 열고 input/button
요소들의 실제 속성(type/name/id/class/placeholder)을 덤프해서, 로그인 폼
selector를 추정이 아니라 실측으로 확정하기 위한 것이다.
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
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "skmr_login_dom_probe.json"

DUMP_SCRIPT = """() => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const describe = (node) => ({
        tag: node.tagName,
        type: node.getAttribute("type") || "",
        name: node.getAttribute("name") || "",
        id: node.getAttribute("id") || "",
        className: node.getAttribute("class") || "",
        placeholder: node.getAttribute("placeholder") || "",
        text: (node.innerText || node.textContent || "").trim().slice(0, 60),
        visible: visible(node),
    });
    const inputs = Array.from(document.querySelectorAll("input")).map(describe);
    const buttons = Array.from(document.querySelectorAll("button, input[type='submit'], input[type='button']")).map(describe);
    const forms = Array.from(document.querySelectorAll("form")).map((node) => ({
        action: node.getAttribute("action") || "",
        method: node.getAttribute("method") || "",
    }));
    return {
        pageTitle: document.title,
        inputs,
        buttons,
        forms,
        bodyTextSample: (document.body.innerText || "").replace(/\\s+/g, " ").trim().slice(0, 500),
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


async def run(args: argparse.Namespace) -> int:
    result: dict[str, Any] = {
        "mode": "SKMR_LOGIN_DOM_PROBE",
        "url": args.url,
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=args.headless)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        try:
            await page.goto(args.url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)
            result["final_url"] = page.url
            dump = await page.evaluate(DUMP_SCRIPT)
            result["dump"] = dump
            result["status"] = "PROBE_DONE"
            print(json.dumps(dump, ensure_ascii=False, indent=2), flush=True)
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
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
