# -*- coding: utf-8 -*-
"""skmr.ifns.work 휴지통(개인업무함/부서업무함/프로젝트업무함) 진입 후,
문서 목록 패널(행/체크박스/우클릭 메뉴) 구조를 실측하기 위한 조사용 probe.

md/skmr_기능_목록.md의 "11. 미확인/다음 단계 필요 - 문서 단위 기능"에 해당하는
부분을 채우기 위한 스크립트. 로그인 -> 사이드바 트리에서 휴지통 하위 노드 펼치기
-> 라벨 클릭으로 이동 -> 메인 패널 DOM 덤프 + 행 우클릭 컨텍스트 메뉴까지 확인한다.
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
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "skmr_trash_panel_probe.json"
DEFAULT_SCREENSHOT_DIR = PROJECT_ROOT / "reports" / "skmr_trash_panel_scan"

USERNAME_SELECTOR = "input[type='text']"
PASSWORD_SELECTOR = "input[type='password']"
SUBMIT_SELECTOR = "button[type='submit'].login-form__submit"

_OWN_ELEMENT_HELPER = """
    const ownElement = (li, selector) => {
        const candidates = Array.from(li.querySelectorAll(selector));
        return candidates.find((el) => el.closest("li.explorer-tree__item") === li) || null;
    };
"""

SIDEBAR_TREE_SCAN_SCRIPT = (
    """() => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();"""
    + _OWN_ELEMENT_HELPER
    + """
    const items = Array.from(document.querySelectorAll(".explorer-sidebar li.explorer-tree__item")).filter(visible);
    return items.map((li, idx) => {
        const chevron = ownElement(li, "button.explorer-tree__chevron");
        const label = ownElement(li, "button.explorer-tree__label");
        return {
            index: idx,
            text: cleanText(li.innerText || li.textContent || "").slice(0, 80),
            hasChevron: Boolean(chevron),
            chevronOpen: chevron ? chevron.className.includes("is-open") : false,
            labelText: label ? cleanText(label.innerText || label.textContent || "") : "",
        };
    });
}"""
)

EXPAND_CHEVRON_SCRIPT = (
    """(index) => {"""
    + _OWN_ELEMENT_HELPER
    + """
    const items = Array.from(document.querySelectorAll(".explorer-sidebar li.explorer-tree__item"));
    const li = items[index];
    if (!li) return { status: "ITEM_NOT_FOUND" };
    const chevron = ownElement(li, "button.explorer-tree__chevron");
    if (!chevron) return { status: "CHEVRON_NOT_FOUND" };
    chevron.click();
    return { status: "CLICKED" };
}"""
)

CLICK_LABEL_SCRIPT = (
    """(index) => {"""
    + _OWN_ELEMENT_HELPER
    + """
    const items = Array.from(document.querySelectorAll(".explorer-sidebar li.explorer-tree__item"));
    const li = items[index];
    if (!li) return { status: "ITEM_NOT_FOUND" };
    const label = ownElement(li, "button.explorer-tree__label");
    if (!label) return { status: "LABEL_NOT_FOUND" };
    label.click();
    return { status: "CLICKED" };
}"""
)

# 메인 패널(문서 목록) 구조를 폭넓게 덤프 - 테이블/그리드/체크박스/행 후보를 모두 수집
MAIN_PANEL_DUMP_SCRIPT = """() => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();

    const tables = Array.from(document.querySelectorAll("table, [role='table'], [role='grid']")).filter(visible);
    const checkboxes = Array.from(document.querySelectorAll("input[type='checkbox'], [role='checkbox']")).filter(visible);
    const rows = Array.from(document.querySelectorAll("tr, [role='row'], [class*='row' i]")).filter(visible);
    const toolbarButtons = Array.from(document.querySelectorAll("button")).filter(visible).map((node) => ({
        text: cleanText(node.innerText || node.textContent || ""),
        ariaLabel: node.getAttribute("aria-label") || "",
        className: node.getAttribute("class") || "",
    })).filter((b) => b.text || b.ariaLabel);

    return {
        tableLikeCount: tables.length,
        tableLikeSample: tables.slice(0, 2).map((node) => ({
            tag: node.tagName,
            className: node.getAttribute("class") || "",
            outerHTMLSample: (node.outerHTML || "").slice(0, 3000),
        })),
        checkboxCount: checkboxes.length,
        checkboxSample: checkboxes.slice(0, 10).map((node) => ({
            tag: node.tagName,
            className: node.getAttribute("class") || "",
            ariaLabel: node.getAttribute("aria-label") || "",
            parentText: cleanText(node.closest("tr, [role='row'], li")?.innerText || "").slice(0, 200),
        })),
        rowCount: rows.length,
        rowSample: rows.slice(0, 15).map((node) => ({
            tag: node.tagName,
            className: node.getAttribute("class") || "",
            text: cleanText(node.innerText || node.textContent || "").slice(0, 200),
        })),
        toolbarButtons: toolbarButtons.slice(0, 40),
        bodyTextSample: cleanText(document.body.innerText || "").slice(0, 1500),
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


async def login(page: Any, username: str, password: str, login_url: str) -> dict[str, Any]:
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
    return {"login_response_status": response_status, "before_url": before_url, "page_url": page.url}


async def find_index_by_label(page: Any, label: str) -> int | None:
    tree = await page.evaluate(SIDEBAR_TREE_SCAN_SCRIPT)
    for item in tree:
        if item["labelText"] == label:
            return item["index"]
    return None


async def run(args: argparse.Namespace) -> int:
    result: dict[str, Any] = {
        "mode": "SKMR_TRASH_PANEL_PROBE",
        "username": args.username,
        "target_label": args.target_label,
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    args.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=args.headless)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        try:
            login_result = await login(page, args.username, args.password, args.url)
            result["login"] = login_result
            print(f"로그인: {login_result['login_response_status']}", flush=True)

            await page.wait_for_timeout(1500)
            await page.screenshot(path=str(args.screenshot_dir / "01_after_login.png"), full_page=True)

            # 바로가기 -> 휴지통 -> 개인업무함까지 순서대로 펼치기 (부모가 접혀 있으면 자식이 안 보임)
            for label in ("바로가기", "휴지통", "개인업무함"):
                idx = await find_index_by_label(page, label)
                result[f"index_{label}"] = idx
                if idx is None:
                    print(f"[경고] '{label}' 노드를 찾지 못함", flush=True)
                    continue
                expand = await page.evaluate(EXPAND_CHEVRON_SCRIPT, idx)
                print(f"'{label}' 펼치기: {expand}", flush=True)
                await page.wait_for_timeout(600)

            await page.screenshot(path=str(args.screenshot_dir / "02_tree_expanded.png"), full_page=True)
            result["tree_after_expand"] = await page.evaluate(SIDEBAR_TREE_SCAN_SCRIPT)

            # 목표 라벨(기본: user_1) 클릭 -> 메인 패널에 문서 목록 로드
            idx = await find_index_by_label(page, args.target_label)
            result["target_index"] = idx
            if idx is None:
                result["status"] = "TARGET_LABEL_NOT_FOUND"
                print(f"[실패] 대상 라벨 '{args.target_label}'을 찾지 못함", flush=True)
                return 1

            click_result = await page.evaluate(CLICK_LABEL_SCRIPT, idx)
            result["click_target"] = click_result
            print(f"'{args.target_label}' 클릭: {click_result}", flush=True)

            await page.wait_for_timeout(1500)
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass

            await page.screenshot(path=str(args.screenshot_dir / "03_main_panel.png"), full_page=True)
            result["main_panel_dump"] = await page.evaluate(MAIN_PANEL_DUMP_SCRIPT)

            # 행이 있으면 우클릭해서 컨텍스트 메뉴까지 확인
            row_count = result["main_panel_dump"].get("rowCount", 0)
            if row_count:
                try:
                    first_row = page.locator("tr, [role='row'], [class*='row' i]").filter(has_text="").first
                    await first_row.click(button="right", timeout=3000)
                    await page.wait_for_timeout(800)
                    await page.screenshot(path=str(args.screenshot_dir / "04_context_menu.png"), full_page=True)
                    result["context_menu_dump"] = await page.evaluate(MAIN_PANEL_DUMP_SCRIPT)
                except Exception as exc:
                    result["context_menu_error"] = str(exc)

            result["status"] = "DONE"
            return 0
        except Exception as exc:
            result["status"] = "FAILED"
            result["message"] = str(exc)
            try:
                await page.screenshot(path=str(args.screenshot_dir / "99_failure.png"), full_page=True)
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
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--target-label", default="user_1")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--screenshot-dir", type=Path, default=DEFAULT_SCREENSHOT_DIR)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
