# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from re_user_trash import configure_console_output, load_json, DEFAULT_CONFIG  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "react01_login_dom_probe.json"

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
    return { inputs, buttons };
}"""


async def run(args: argparse.Namespace) -> int:
    config = load_json(args.config)
    result: dict[str, Any] = {
        "mode": "REACT01_LOGIN_DOM_PROBE",
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
        context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
        page = await context.new_page()
        try:
            await page.goto(config["login_url"], wait_until="domcontentloaded")
            await page.wait_for_timeout(800)
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
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
