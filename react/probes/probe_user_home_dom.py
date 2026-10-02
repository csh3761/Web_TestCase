# -*- coding: utf-8 -*-
"""일반 사용자 계정으로 react01에 로그인한 뒤, 홈 화면/메뉴에서
개인 업무함·휴지통 관련 요소를 폭넓게 훑어 report로 남기는 조사용 스크립트.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "react01_interface"))
from re_user_trash import (  # noqa: E402
    Account,
    DEFAULT_CONFIG,
    configure_console_output,
    load_json,
    login_react01,
    save_screenshot,
    snapshot_page,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "react01_user_home_probe.json"
DEFAULT_SCREENSHOT = PROJECT_ROOT / "reports" / "react01_user_home.png"

# 업무함/휴지통 관련 폭넓은 키워드 후보
TARGET_KEYWORDS = (
    "업무함", "휴지통", "휴지함", "삭제함", "복원함", "trash", "recycle",
    "내 업무함", "부서 업무함", "프로젝트 업무함", "문서함",
)

FIND_MENU_SCRIPT = """(targets) => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
    const norm = (value) => cleanText(value).toLowerCase().replace(/\\s+/g, "");
    const targetSet = targets.map((item) => norm(item));

    const candidates = Array.from(document.querySelectorAll(
        "button, a, li, [role='menuitem'], [role='button'], [role='tab'], [role='treeitem'], span, div"
    ));

    const matches = [];
    const seen = new Set();
    for (const node of candidates) {
        const ownText = cleanText(node.innerText || node.textContent || "");
        if (!ownText || ownText.length > 60) {
            continue;
        }
        const ariaLabel = cleanText(node.getAttribute("aria-label") || "");
        const title = cleanText(node.getAttribute("title") || "");
        const href = node.getAttribute("href") || "";
        const combined = [ownText, ariaLabel, title, href];
        const isMatch = combined.some((text) => targetSet.some((target) => norm(text).includes(target)));
        if (!isMatch) {
            continue;
        }
        const box = node.getBoundingClientRect();
        const key = node.tagName + "|" + ownText.slice(0, 80) + "|" + href;
        if (seen.has(key)) {
            continue;
        }
        seen.add(key);
        matches.push({
            tag: node.tagName,
            id: node.getAttribute("id") || "",
            className: node.getAttribute("class") || "",
            role: node.getAttribute("role") || "",
            text: ownText,
            ariaLabel,
            title,
            href,
            visible: visible(node),
            box: { left: box.left, top: box.top, width: box.width, height: box.height },
        });
    }
    return matches;
}"""

# 화면 전반의 nav/sidebar 텍스트를 통째로 덤프 (키워드 매치 실패 대비 원문 확보용)
DUMP_NAV_SCRIPT = """() => {
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
    const navLike = Array.from(document.querySelectorAll(
        "nav, aside, [class*='sidebar' i], [class*='menu' i], [role='navigation']"
    ));
    return navLike.slice(0, 10).map((node) => ({
        tag: node.tagName,
        className: node.getAttribute("class") || "",
        textSample: cleanText(node.innerText || node.textContent || "").slice(0, 2000),
    }));
}"""


async def find_target_in_frame(frame: Any, targets: tuple[str, ...]) -> list[dict[str, Any]]:
    try:
        return await frame.evaluate(FIND_MENU_SCRIPT, list(targets))
    except Exception as exc:
        return [{"error": str(exc)}]


async def dump_nav_in_frame(frame: Any) -> list[dict[str, Any]]:
    try:
        return await frame.evaluate(DUMP_NAV_SCRIPT)
    except Exception as exc:
        return [{"error": str(exc)}]


async def run(args: argparse.Namespace) -> int:
    config = load_json(args.config)
    account = Account(user_id=args.username, user_name=args.username)
    password = args.password
    result: dict[str, Any] = {
        "mode": "REACT01_USER_HOME_PROBE",
        "target_keywords": TARGET_KEYWORDS,
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
            print(f"로그인 완료: {login_result['login_response_status']} / {login_result['page_url']}", flush=True)

            await page.wait_for_timeout(2500)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            result["after_login_snapshot"] = await snapshot_page(page)
            result["screenshot"] = await save_screenshot(page, args.screenshot)

            frame_results: list[dict[str, Any]] = []
            all_matches: list[dict[str, Any]] = []
            all_nav_dumps: list[dict[str, Any]] = []
            for frame in page.frames:
                matches = await find_target_in_frame(frame, TARGET_KEYWORDS)
                for match in matches:
                    match["frameName"] = frame.name
                    match["frameUrl"] = frame.url
                all_matches.extend(matches)

                nav_dump = await dump_nav_in_frame(frame)
                for item in nav_dump:
                    item["frameName"] = frame.name
                    item["frameUrl"] = frame.url
                all_nav_dumps.extend(nav_dump)

                frame_results.append({"frameName": frame.name, "frameUrl": frame.url, "matchCount": len(matches)})

            result["frames_scanned"] = frame_results
            result["matches"] = all_matches
            result["match_count"] = len(all_matches)
            result["nav_dumps"] = all_nav_dumps
            result["status"] = "MENU_FOUND" if all_matches else "MENU_NOT_FOUND"

            print(f"프레임 {len(frame_results)}개 스캔, 키워드 매치 {len(all_matches)}건", flush=True)
            for match in all_matches:
                print(json.dumps(match, ensure_ascii=False), flush=True)

            await page.wait_for_timeout(500)
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
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--screenshot", type=Path, default=DEFAULT_SCREENSHOT)
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
