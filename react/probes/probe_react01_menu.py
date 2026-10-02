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
    DEFAULT_CONFIG,
    Account,
    configure_console_output,
    load_json,
    login_react01,
    snapshot_page,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "react01_menu_probe.json"

# 검색할 텍스트 후보 (표기 변형 대비)
TARGET_TEXTS = ("전사휴지통", "전사 휴지통", "전사휴지함", "전사 휴지함")

FIND_MENU_SCRIPT = """(targets) => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
    const norm = (value) => cleanText(value).replace(/\\s+/g, "");
    const targetSet = targets.map((item) => norm(item));

    const candidates = Array.from(document.querySelectorAll(
        "button, a, li, [role='menuitem'], [role='button'], [role='tab'], span, div"
    ));

    const matches = [];
    const seen = new Set();
    for (const node of candidates) {
        const ownText = cleanText(node.innerText || node.textContent || "");
        const ariaLabel = cleanText(node.getAttribute("aria-label") || "");
        const title = cleanText(node.getAttribute("title") || "");
        const combined = [ownText, ariaLabel, title];
        const isMatch = combined.some((text) => targetSet.some((target) => norm(text).includes(target)));
        if (!isMatch) {
            continue;
        }
        // 텍스트를 포함하는 가장 안쪽(leaf에 가까운) 요소만 남기기 위해,
        // 이미 매치된 조상 요소가 있으면 스킵하지 않고 별도 표시만 한다.
        const box = node.getBoundingClientRect();
        const key = node.tagName + "|" + (node.id || "") + "|" + (node.className || "") + "|" + ownText.slice(0, 80);
        if (seen.has(key)) {
            continue;
        }
        seen.add(key);
        matches.push({
            tag: node.tagName,
            id: node.getAttribute("id") || "",
            className: node.getAttribute("class") || "",
            role: node.getAttribute("role") || "",
            text: ownText.slice(0, 200),
            ariaLabel,
            title,
            dataAttrs: Array.from(node.attributes)
                .filter((attr) => attr.name.startsWith("data-"))
                .map((attr) => ({ name: attr.name, value: attr.value })),
            href: node.getAttribute("href") || "",
            visible: visible(node),
            box: { left: box.left, top: box.top, width: box.width, height: box.height },
            outerHTMLSample: (node.outerHTML || "").slice(0, 400),
        });
    }
    return matches;
}"""


async def find_target_in_frame(frame: Any, targets: tuple[str, ...]) -> list[dict[str, Any]]:
    try:
        return await frame.evaluate(FIND_MENU_SCRIPT, list(targets))
    except Exception as exc:
        return [{"error": str(exc)}]


async def run(args: argparse.Namespace) -> int:
    config = load_json(args.config)
    account = Account(user_id=args.username, user_name=args.username)
    password = args.password
    lines: list[str] = []
    result: dict[str, Any] = {
        "mode": "REACT01_MENU_PROBE",
        "target_texts": TARGET_TEXTS,
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

            # 로그인 직후 화면이 자리잡을 시간을 준다 (SPA 렌더링 대기)
            await page.wait_for_timeout(2000)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            result["after_login_snapshot"] = await snapshot_page(page)

            frame_results: list[dict[str, Any]] = []
            all_matches: list[dict[str, Any]] = []
            for frame in page.frames:
                matches = await find_target_in_frame(frame, TARGET_TEXTS)
                frame_results.append({"frameName": frame.name, "frameUrl": frame.url, "matchCount": len(matches)})
                for match in matches:
                    match["frameName"] = frame.name
                    match["frameUrl"] = frame.url
                all_matches.extend(matches)

            result["frames_scanned"] = frame_results
            result["matches"] = all_matches
            result["match_count"] = len(all_matches)
            result["status"] = "MENU_FOUND" if all_matches else "MENU_NOT_FOUND"

            print(f"검색 대상: {TARGET_TEXTS}", flush=True)
            print(f"프레임 {len(frame_results)}개 스캔, 매치 {len(all_matches)}건", flush=True)
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
    parser.add_argument("--username", default="sysadmin")
    parser.add_argument("--password", default="1234")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
