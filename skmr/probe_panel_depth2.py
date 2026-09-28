# -*- coding: utf-8 -*-
"""skmr.ifns.work 대형 패널(2단계 심화) 스캔.

probe_deep_menu_discovery.py에서 "열기만" 했던 큰 패널들 — More options 안의
전사관리자/업무함 관리자/설정, 대시보드의 위젯 추가, 최근·최신 문서의 더보기,
권한 요청 패널의 조회 — 를 실제로 한 번 더 클릭해서 그 안의 최상위 버튼/링크까지
훑는다(각 패널이 자체적으로 또 다른 화면일 수 있음을 확인하기 위함).
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_deep_menu_discovery import login  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://skmr.ifns.work/"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "skmr_panel_depth2.json"
DEFAULT_SCREENSHOT_DIR = PROJECT_ROOT / "reports" / "skmr_deep_scan2"

WIDE_SCAN_SCRIPT = """() => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
    const collect = (selector) => Array.from(document.querySelectorAll(selector)).filter(visible).map((node) => ({
        tag: node.tagName,
        text: cleanText(node.innerText || node.textContent || node.getAttribute("aria-label") || "").slice(0, 60),
        className: node.getAttribute("class") || "",
        href: node.getAttribute("href") || "",
    }));
    return {
        pageTitle: document.title,
        pageUrl: location.href,
        buttons: collect("button"),
        links: collect("a[href]"),
        tabs: collect("[role='tab']"),
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


async def open_kebab_and_click(page: Any, item_text: str) -> bool:
    kebab = page.locator("button.explorer-kebab-btn").first
    await kebab.click(timeout=5000)
    await page.wait_for_timeout(400)
    item = page.locator("button, a, li, [role='menuitem']").filter(has_text=item_text).first
    if await item.count() == 0:
        return False
    await item.click(timeout=5000)
    await page.wait_for_timeout(1500)
    return True


async def explore_page(page: Any, label: str, screenshot_dir: Path) -> dict[str, Any]:
    entry: dict[str, Any] = {"label": label}
    scan = await page.evaluate(WIDE_SCAN_SCRIPT)
    entry["scan"] = scan
    entry["button_count"] = len(scan["buttons"])
    entry["link_count"] = len(scan["links"])
    screenshot_path = screenshot_dir / f"{label}.png"
    await page.screenshot(path=str(screenshot_path), full_page=True)
    entry["screenshot"] = str(screenshot_path)
    print(
        f"  [{label}] url={scan['pageUrl']} title={scan['pageTitle']} "
        f"버튼 {len(scan['buttons'])}개, 링크 {len(scan['links'])}개",
        flush=True,
    )
    return entry


async def run(args: argparse.Namespace) -> int:
    result: dict[str, Any] = {
        "mode": "SKMR_PANEL_DEPTH2_PROBE",
        "username": args.username,
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    args.screenshot_dir.mkdir(parents=True, exist_ok=True)
    panels: list[dict[str, Any]] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=args.headless)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        try:
            print(f"로그인 시작: {args.username}", flush=True)
            login_result = await login(page, args.username, args.password, args.url)
            result["login"] = login_result
            print(f"로그인 결과: {login_result['login_response_status']}", flush=True)
            base_url = page.url

            print("초기 부팅 대기 (약 20초)...", flush=True)
            await page.wait_for_timeout(20000)

            # 1) More options 하위: 전사관리자 / 업무함 관리자 / 설정 - 각각 클릭 후 스캔, 매번 원위치로 복귀
            for admin_item in ("전사관리자", "업무함 관리자", "설정"):
                print(f"More options > {admin_item} 진입 시도", flush=True)
                try:
                    await page.goto(base_url, wait_until="domcontentloaded")
                    await page.wait_for_timeout(20000)
                    opened = await open_kebab_and_click(page, admin_item)
                    if not opened:
                        panels.append({"label": f"More options>{admin_item}", "status": "ITEM_NOT_FOUND"})
                        print("    -> 메뉴 항목을 찾지 못함", flush=True)
                        continue
                    entry = await explore_page(page, f"more_{admin_item}", args.screenshot_dir)
                    entry["status"] = "OK"
                    panels.append(entry)
                except Exception as exc:
                    panels.append({"label": f"More options>{admin_item}", "status": "FAILED", "message": str(exc)})
                    print(f"    -> 실패: {exc}", flush=True)

            # 2) 대시보드 > 위젯 추가
            print("대시보드 > 위젯 추가 진입 시도", flush=True)
            try:
                await page.goto(base_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(20000)
                dash_btn = page.locator('button.explorer-toolbar__request-open-btn[aria-label="대시보드"]').first
                await dash_btn.click(timeout=5000)
                await page.wait_for_timeout(1000)
                widget_btn = page.locator("button, a").filter(has_text="위젯 추가").first
                if await widget_btn.count() > 0:
                    await widget_btn.click(timeout=5000)
                    await page.wait_for_timeout(800)
                entry = await explore_page(page, "dashboard_위젯추가", args.screenshot_dir)
                entry["status"] = "OK"
                panels.append(entry)
            except Exception as exc:
                panels.append({"label": "대시보드>위젯 추가", "status": "FAILED", "message": str(exc)})
                print(f"    -> 실패: {exc}", flush=True)

            # 3) 권한 요청 패널 > 조회
            print("권한 요청 패널 > 조회 진입 시도", flush=True)
            try:
                await page.goto(base_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(20000)
                perm_btn = page.locator('button.explorer-toolbar__request-open-btn[aria-label="권한 요청 패널"]').first
                await perm_btn.click(timeout=5000)
                await page.wait_for_timeout(1000)
                query_btn = page.locator("button").filter(has_text="조회").first
                if await query_btn.count() > 0:
                    await query_btn.click(timeout=5000)
                    await page.wait_for_timeout(800)
                entry = await explore_page(page, "permission_조회", args.screenshot_dir)
                entry["status"] = "OK"
                panels.append(entry)
            except Exception as exc:
                panels.append({"label": "권한 요청 패널>조회", "status": "FAILED", "message": str(exc)})
                print(f"    -> 실패: {exc}", flush=True)

            # 4) 최근·최신 문서 > 더보기
            print("최근·최신 문서 > 더보기 진입 시도", flush=True)
            try:
                await page.goto(base_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(20000)
                recent_btn = page.locator('button.explorer-toolbar__request-open-btn[aria-label="최근·최신 문서"]').first
                await recent_btn.click(timeout=5000)
                await page.wait_for_timeout(1000)
                more_btn = page.locator("button").filter(has_text="더보기").first
                if await more_btn.count() > 0:
                    await more_btn.click(timeout=5000)
                    await page.wait_for_timeout(800)
                entry = await explore_page(page, "recent_docs_더보기", args.screenshot_dir)
                entry["status"] = "OK"
                panels.append(entry)
            except Exception as exc:
                panels.append({"label": "최근·최신 문서>더보기", "status": "FAILED", "message": str(exc)})
                print(f"    -> 실패: {exc}", flush=True)

            result["panels"] = panels
            result["status"] = "PROBE_DONE"

            print("스캔 종료, 45초간 화면을 유지합니다...", flush=True)
            await page.wait_for_timeout(45000)
            return 0
        except Exception as exc:
            result["status"] = "FAILED"
            result["message"] = str(exc)
            result["panels"] = panels
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
    parser.add_argument("--screenshot-dir", type=Path, default=DEFAULT_SCREENSHOT_DIR)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
