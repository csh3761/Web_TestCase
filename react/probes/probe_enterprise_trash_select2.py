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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "react01_interface"))
from re_user_trash import (  # noqa: E402
    Account,
    DEFAULT_CONFIG,
    configure_console_output,
    load_json,
    login_react01,
    open_enterprise_trash,
    snapshot_page,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "react01_enterprise_trash_select_probe2.json"

COUNT_SELECTED_SCRIPT = """() => {
    const rows = Array.from(document.querySelectorAll(".explorer-file-table__row"));
    return {
        totalRows: rows.length,
        selectedRows: rows.filter((r) => r.className.includes("is-selected")).length,
    };
}"""

MENU_ITEM_ANCESTOR_SCRIPT = """(labelText) => {
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
    const spans = Array.from(document.querySelectorAll("span, li, button, a, div"));
    const target = spans.find((node) => cleanText(node.innerText || node.textContent || "") === labelText && node.children.length === 0);
    if (!target) {
        return { status: "NOT_FOUND" };
    }
    const chain = [];
    let node = target;
    for (let i = 0; i < 6 && node; i += 1) {
        chain.push({
            tag: node.tagName,
            id: node.getAttribute?.("id") || "",
            className: node.getAttribute?.("class") || "",
            role: node.getAttribute?.("role") || "",
            dataAttrs: node.attributes
                ? Array.from(node.attributes).filter((a) => a.name.startsWith("data-")).map((a) => `${a.name}=${a.value}`)
                : [],
        });
        node = node.parentElement;
    }
    return { status: "FOUND", chain };
}"""

FULL_MENU_DUMP_SCRIPT = """() => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
    const containers = Array.from(document.querySelectorAll("[class*='explorer-context']")).filter(visible);
    return containers.map((node) => ({
        tag: node.tagName,
        className: node.getAttribute("class") || "",
        text: cleanText(node.innerText || node.textContent || "").slice(0, 300),
    }));
}"""


async def run(args: argparse.Namespace) -> int:
    config = load_json(args.config)
    account = Account(user_id=args.username, user_name=args.username)
    password = args.password
    result: dict[str, Any] = {
        "mode": "REACT01_ENTERPRISE_TRASH_SELECT_PROBE_2",
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
        context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
        page = await context.new_page()
        try:
            print(f"로그인 시작: {account.user_id}", flush=True)
            await login_react01(page, account, password, config)
            nav_result = await open_enterprise_trash(page, config)
            print(f"전사휴지통 이동: {nav_result['status']}", flush=True)
            await page.wait_for_timeout(1500)

            first_name = "엑셀문서 - 복사본.xlsx"
            second_name = "저장테스트 - 복사본 (2) - 복사본 - 복사본.txt"

            first_locator = page.get_by_text(first_name, exact=True).first
            second_locator = page.get_by_text(second_name, exact=True).first

            # 1) 일반 클릭 vs Ctrl+클릭 다중 선택 확인
            await first_locator.click(timeout=5000)
            await page.wait_for_timeout(300)
            after_first = await page.evaluate(COUNT_SELECTED_SCRIPT)

            await second_locator.click(modifiers=["Control"], timeout=5000)
            await page.wait_for_timeout(300)
            after_ctrl_click = await page.evaluate(COUNT_SELECTED_SCRIPT)

            result["selection_after_first_click"] = after_first
            result["selection_after_ctrl_click"] = after_ctrl_click
            print(f"단일 클릭 후 선택 수: {after_first}", flush=True)
            print(f"Ctrl+클릭 후 선택 수: {after_ctrl_click}", flush=True)

            # 2) Shift+클릭 범위 선택 확인 (첫 행 클릭 후 화면에 보이는 마지막 행까지 shift+클릭)
            await first_locator.click(timeout=5000)
            await page.wait_for_timeout(300)
            last_visible_name_locator = page.locator(".explorer-file-table__row").last
            await last_visible_name_locator.click(modifiers=["Shift"], timeout=5000)
            await page.wait_for_timeout(300)
            after_shift_click = await page.evaluate(COUNT_SELECTED_SCRIPT)
            result["selection_after_shift_click"] = after_shift_click
            print(f"Shift+클릭(첫~마지막 보이는 행) 후 선택 수: {after_shift_click}", flush=True)

            screenshot_path = PROJECT_ROOT / "reports" / "react01_enterprise_trash_shift_select.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            result["after_shift_select_screenshot"] = str(screenshot_path)

            # 3) 우클릭 컨텍스트 메뉴 전체 구조 덤프 + "완전삭제(엔진 삭제)" 클릭 가능 요소 조상 체인
            row_box = await first_locator.bounding_box()
            if row_box:
                await page.mouse.click(row_box["x"] + row_box["width"] / 2, row_box["y"] + row_box["height"] / 2, button="right")
                await page.wait_for_timeout(500)

            menu_dump = await page.evaluate(FULL_MENU_DUMP_SCRIPT)
            result["context_menu_containers"] = menu_dump
            for item in menu_dump:
                print(f"  메뉴 컨테이너: {item['className']} | {item['text'][:80]}", flush=True)

            ancestor = await page.evaluate(MENU_ITEM_ANCESTOR_SCRIPT, "완전삭제(엔진 삭제)")
            result["delete_menu_item_ancestor"] = ancestor
            print(f"삭제 메뉴 항목 조상 체인: {ancestor.get('status')}", flush=True)

            context_menu_screenshot = PROJECT_ROOT / "reports" / "react01_enterprise_trash_context_menu3.png"
            await page.screenshot(path=str(context_menu_screenshot), full_page=True)
            result["context_menu_screenshot"] = str(context_menu_screenshot)

            result["status"] = "PROBE_DONE"
            return 0
        except Exception as exc:
            result["status"] = "FAILED"
            result["message"] = str(exc)
            try:
                result["failure_snapshot"] = await snapshot_page(page)
            except Exception:
                pass
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
    parser.add_argument("--username", default="sysadmin")
    parser.add_argument("--password", default="1234")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
