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
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "react01_enterprise_trash_select_probe.json"

ROW_ANCESTOR_SCRIPT = """(fileName) => {
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
    const all = Array.from(document.querySelectorAll("*"));
    const target = all.find((node) => {
        if (node.children.length > 0) return false;
        return cleanText(node.innerText || node.textContent || "") === fileName;
    });
    if (!target) {
        return { status: "TEXT_NODE_NOT_FOUND" };
    }
    const chain = [];
    let node = target;
    for (let i = 0; i < 8 && node; i += 1) {
        chain.push({
            tag: node.tagName,
            id: node.getAttribute?.("id") || "",
            className: node.getAttribute?.("class") || "",
            role: node.getAttribute?.("role") || "",
            ariaSelected: node.getAttribute?.("aria-selected") || "",
            dataAttrs: node.attributes
                ? Array.from(node.attributes).filter((a) => a.name.startsWith("data-")).map((a) => `${a.name}=${a.value}`)
                : [],
        });
        node = node.parentElement;
    }
    return { status: "FOUND", chain };
}"""

FIND_BUTTONS_WITH_TEXT_SCRIPT = """(keyword) => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
    const nodes = Array.from(document.querySelectorAll("button, a, [role='button'], [role='checkbox'], input"));
    return nodes
        .filter((node) => {
            const text = cleanText(node.innerText || node.textContent || node.getAttribute("aria-label") || "");
            return text.includes(keyword);
        })
        .map((node) => ({
            tag: node.tagName,
            className: node.getAttribute("class") || "",
            ariaLabel: node.getAttribute("aria-label") || "",
            text: cleanText(node.innerText || node.textContent || "").slice(0, 100),
            visible: visible(node),
        }));
}"""

DETECT_CONTEXT_MENU_SCRIPT = """async (timeoutMs) => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
    const menuSelectors = [
        "[role='menu']",
        "[data-radix-menu-content]",
        "[data-state='open']",
        ".context-menu",
        ".dropdown-menu",
        "[class*='context']",
        "[class*='Context']",
        "[class*='menu']",
    ];
    const startedAt = Date.now();
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    while (Date.now() - startedAt <= timeoutMs) {
        const menus = Array.from(document.querySelectorAll(menuSelectors.join(","))).filter((el) => {
            if (!visible(el)) return false;
            const box = el.getBoundingClientRect();
            return box.width > 20 && box.height > 10;
        });
        if (menus.length) {
            const menu = menus[menus.length - 1];
            const items = Array.from(menu.querySelectorAll("button, a, li, [role='menuitem']")).filter(visible);
            return {
                status: "CONTEXT_MENU_DETECTED",
                menuTag: menu.tagName,
                menuClassName: menu.className || "",
                menuOuterHTMLSample: (menu.outerHTML || "").slice(0, 2000),
                items: items.map((item) => ({
                    tag: item.tagName,
                    text: cleanText(item.innerText || item.textContent || "").slice(0, 100),
                    className: item.getAttribute("class") || "",
                    role: item.getAttribute("role") || "",
                    dataAttrs: Array.from(item.attributes || [])
                        .filter((a) => a.name.startsWith("data-"))
                        .map((a) => `${a.name}=${a.value}`),
                })),
            };
        }
        await sleep(150);
    }
    return { status: "CONTEXT_MENU_NOT_DETECTED" };
}"""


async def run(args: argparse.Namespace) -> int:
    config = load_json(args.config)
    account = Account(user_id=args.username, user_name=args.username)
    password = args.password
    result: dict[str, Any] = {
        "mode": "REACT01_ENTERPRISE_TRASH_SELECT_PROBE",
        "user_id": account.user_id,
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
        context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
        page = await context.new_page()
        try:
            print(f"로그인 시작: {account.user_id}", flush=True)
            login_result = await login_react01(page, account, password, config)
            result["login"] = login_result

            nav_result = await open_enterprise_trash(page, config)
            result["navigation"] = nav_result
            print(f"전사휴지통 이동: {nav_result['status']}", flush=True)
            await page.wait_for_timeout(1500)

            # 첫 행 파일명 텍스트 취득 (문서명 컬럼의 첫 번째 셀 텍스트)
            first_name_locator = page.locator("table, [role='table']").first
            # 화면에서 확인된 첫 문서명을 직접 지정 (probe1 결과 기준)
            file_name = "엑셀문서 - 복사본.xlsx"

            ancestor_info = await page.evaluate(ROW_ANCESTOR_SCRIPT, file_name)
            result["row_ancestor_chain"] = ancestor_info
            print(f"행 조상 체인 조회: {ancestor_info.get('status')}", flush=True)

            # 전체선택 관련 버튼/체크박스 탐색
            select_all_candidates = await page.evaluate(FIND_BUTTONS_WITH_TEXT_SCRIPT, "전체")
            result["select_all_candidates"] = select_all_candidates
            print(f"'전체' 텍스트 포함 버튼 {len(select_all_candidates)}개", flush=True)

            # 첫 번째 문서명 텍스트를 클릭해서 행 선택 시도
            name_locator = page.get_by_text(file_name, exact=True).first
            await name_locator.click(timeout=5000)
            await page.wait_for_timeout(500)
            after_click_chain = await page.evaluate(ROW_ANCESTOR_SCRIPT, file_name)
            result["row_ancestor_chain_after_click"] = after_click_chain

            screenshot_path = PROJECT_ROOT / "reports" / "react01_enterprise_trash_row_click.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            result["after_row_click_screenshot"] = str(screenshot_path)

            # Ctrl+클릭으로 두 번째 문서 추가 선택 시도
            second_file_name = "저장테스트 - 복사본 (2) - 복사본 - 복사본.txt"
            try:
                second_locator = page.get_by_text(second_file_name, exact=True).first
                await second_locator.click(modifiers=["Control"], timeout=5000)
                await page.wait_for_timeout(500)
            except Exception as exc:
                result["ctrl_click_error"] = str(exc)

            screenshot_multi_path = PROJECT_ROOT / "reports" / "react01_enterprise_trash_multi_select.png"
            await page.screenshot(path=str(screenshot_multi_path), full_page=True)
            result["after_multi_select_screenshot"] = str(screenshot_multi_path)

            body_after_select = await page.evaluate(
                "() => document.body.innerText.replace(/\\s+/g, ' ').trim().slice(0, 800)"
            )
            result["body_after_select_sample"] = body_after_select

            # 선택된 행 위에서 우클릭 -> 컨텍스트 메뉴 탐지
            try:
                row_box = await name_locator.bounding_box()
                if row_box:
                    await page.mouse.click(
                        row_box["x"] + row_box["width"] / 2, row_box["y"] + row_box["height"] / 2, button="right"
                    )
                    context_menu_result = await page.evaluate(DETECT_CONTEXT_MENU_SCRIPT, 4000)
                else:
                    context_menu_result = {"status": "NO_BOUNDING_BOX"}
            except Exception as exc:
                context_menu_result = {"status": "CONTEXT_MENU_PROBE_FAILED", "message": str(exc)}
            result["context_menu"] = context_menu_result
            print(f"우클릭 메뉴: {context_menu_result.get('status')}", flush=True)
            for item in context_menu_result.get("items", []):
                print(f"  메뉴 항목: {item['text']}", flush=True)

            context_menu_screenshot = PROJECT_ROOT / "reports" / "react01_enterprise_trash_context_menu2.png"
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
