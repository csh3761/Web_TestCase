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
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "react01_enterprise_trash_dom_probe.json"
DEFAULT_SCREENSHOT = PROJECT_ROOT / "reports" / "react01_enterprise_trash_before_select.png"
DEFAULT_SELECTION_SCREENSHOT = PROJECT_ROOT / "reports" / "react01_enterprise_trash_after_select.png"
DEFAULT_CONTEXT_MENU_SCREENSHOT = PROJECT_ROOT / "reports" / "react01_enterprise_trash_context_menu.png"

# 목록/체크박스/페이징 구조를 넓게 훑는 스크립트. 아직 정확한 마크업을 모르므로
# table/grid/role 기반, 클래스 이름 힌트, aria 속성 등 여러 후보를 동시에 수집한다.
STRUCTURE_SCRIPT = """() => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();

    const tables = Array.from(document.querySelectorAll("table, [role='table'], [role='grid']")).filter(visible);
    const checkboxes = Array.from(document.querySelectorAll("input[type='checkbox'], [role='checkbox']")).filter(visible);
    const headerCheckbox = checkboxes.find((node) => {
        const th = node.closest("th, thead, [role='columnheader']");
        return Boolean(th);
    });

    const paginationCandidates = Array.from(document.querySelectorAll(
        "[class*='pagination'], [class*='Pagination'], nav[aria-label*='pag' i], nav[aria-label*='페이지' i]"
    )).filter(visible);

    const rowCandidates = Array.from(document.querySelectorAll("tr, [role='row'], [class*='row']")).filter(visible);

    return {
        tableLikeCount: tables.length,
        tableLikeSample: tables.slice(0, 3).map((node) => ({
            tag: node.tagName,
            className: node.getAttribute("class") || "",
            role: node.getAttribute("role") || "",
            outerHTMLSample: (node.outerHTML || "").slice(0, 600),
        })),
        checkboxCount: checkboxes.length,
        checkboxSample: checkboxes.slice(0, 10).map((node) => ({
            tag: node.tagName,
            id: node.getAttribute("id") || "",
            className: node.getAttribute("class") || "",
            ariaLabel: node.getAttribute("aria-label") || "",
            checked: node.matches("input") ? Boolean(node.checked) : node.getAttribute("aria-checked"),
            closestRowOuterHTML: (node.closest("tr, [role='row'], [class*='row']")?.outerHTML || "").slice(0, 400),
        })),
        headerCheckboxFound: Boolean(headerCheckbox),
        headerCheckboxSample: headerCheckbox
            ? {
                  tag: headerCheckbox.tagName,
                  id: headerCheckbox.getAttribute("id") || "",
                  className: headerCheckbox.getAttribute("class") || "",
                  ariaLabel: headerCheckbox.getAttribute("aria-label") || "",
              }
            : null,
        paginationCount: paginationCandidates.length,
        paginationSample: paginationCandidates.slice(0, 3).map((node) => ({
            tag: node.tagName,
            className: node.getAttribute("class") || "",
            text: cleanText(node.innerText || node.textContent || "").slice(0, 300),
            outerHTMLSample: (node.outerHTML || "").slice(0, 600),
        })),
        rowLikeCount: rowCandidates.length,
        bodyTextSample: cleanText(document.body.innerText || "").slice(0, 3000),
    };
}"""

DETECT_CONTEXT_MENU_SCRIPT = """async (timeoutMs) => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
    const menuSelectors = [
        "[role='menu']",
        ".context-menu",
        ".dropdown-menu",
        "[data-radix-menu-content]",
        "[data-state='open']",
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
            const menu = menus[0];
            const items = Array.from(menu.querySelectorAll("button, a, li, [role='menuitem']")).filter(visible);
            return {
                status: "CONTEXT_MENU_DETECTED",
                menuTag: menu.tagName,
                menuClassName: menu.className || "",
                menuOuterHTMLSample: (menu.outerHTML || "").slice(0, 1500),
                items: items.map((item) => ({
                    tag: item.tagName,
                    text: cleanText(item.innerText || item.textContent || "").slice(0, 100),
                    className: item.getAttribute("class") || "",
                    role: item.getAttribute("role") || "",
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
        "mode": "REACT01_ENTERPRISE_TRASH_DOM_PROBE",
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
            print(f"로그인 완료: {login_result['login_response_status']}", flush=True)

            nav_result = await open_enterprise_trash(page, config)
            result["navigation"] = nav_result
            print(f"전사휴지통 이동: {nav_result['status']} ({nav_result['page_url']})", flush=True)

            await page.wait_for_timeout(1500)

            DEFAULT_SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(DEFAULT_SCREENSHOT), full_page=True)
            result["before_select_screenshot"] = str(DEFAULT_SCREENSHOT)

            structure = await page.evaluate(STRUCTURE_SCRIPT)
            result["structure"] = structure
            print(
                f"구조 스캔: table류 {structure['tableLikeCount']}개, "
                f"checkbox {structure['checkboxCount']}개, "
                f"pagination류 {structure['paginationCount']}개, "
                f"row류 {structure['rowLikeCount']}개",
                flush=True,
            )

            # 안전한 선택 동작: 보이는 체크박스를 전부 클릭해본다 (삭제 아님, 되돌리기 쉬움).
            checkbox_locators = page.locator("input[type='checkbox']:visible, [role='checkbox']:visible")
            checkbox_count = await checkbox_locators.count()
            clicked = 0
            click_errors: list[str] = []
            for index in range(checkbox_count):
                try:
                    await checkbox_locators.nth(index).click(timeout=2000)
                    clicked += 1
                except Exception as exc:
                    click_errors.append(f"index={index}: {exc}")
            result["checkbox_click_attempted"] = checkbox_count
            result["checkbox_click_succeeded"] = clicked
            result["checkbox_click_errors"] = click_errors[:10]
            print(f"체크박스 클릭 시도 {checkbox_count}개 중 {clicked}개 성공", flush=True)

            await page.wait_for_timeout(500)
            DEFAULT_SELECTION_SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(DEFAULT_SELECTION_SCREENSHOT), full_page=True)
            result["after_select_screenshot"] = str(DEFAULT_SELECTION_SCREENSHOT)

            after_select_structure = await page.evaluate(STRUCTURE_SCRIPT)
            result["after_select_body_sample"] = after_select_structure["bodyTextSample"]

            # 우클릭으로 컨텍스트 메뉴 확인 (메뉴 항목 텍스트만 읽고, 클릭은 하지 않음)
            context_menu_result: dict[str, Any] = {"status": "SKIPPED_NO_ROW"}
            if checkbox_count > 0:
                try:
                    row_target = checkbox_locators.first
                    box = await row_target.bounding_box()
                    if box:
                        await page.mouse.click(
                            box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, button="right"
                        )
                        context_menu_result = await page.evaluate(DETECT_CONTEXT_MENU_SCRIPT, 4000)
                except Exception as exc:
                    context_menu_result = {"status": "CONTEXT_MENU_PROBE_FAILED", "message": str(exc)}
            result["context_menu"] = context_menu_result
            print(f"우클릭 메뉴 탐지: {context_menu_result.get('status')}", flush=True)
            if context_menu_result.get("items"):
                for item in context_menu_result["items"]:
                    print(f"  메뉴 항목: {item['text']}", flush=True)

            DEFAULT_CONTEXT_MENU_SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(DEFAULT_CONTEXT_MENU_SCREENSHOT), full_page=True)
            result["context_menu_screenshot"] = str(DEFAULT_CONTEXT_MENU_SCREENSHOT)

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
