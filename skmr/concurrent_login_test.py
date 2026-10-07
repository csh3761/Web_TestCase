# -*- coding: utf-8 -*-
"""skmr.ifns.work 다중 계정 동시 로그인 테스트.

계정마다 독립된 브라우저 컨텍스트(쿠키/스토리지 분리)를 만들고, 로그인 폼 입력까지
끝낸 뒤 barrier에서 모두 대기했다가 같은 시점에 로그인 버튼을 누른다.

검증 항목
- 로그인 POST 응답 상태/소요시간
- 응답 body의 username이 요청한 계정과 일치하는지 (세션 섞임 확인)
- 로그인 직후 /auth/me가 본인 계정을 돌려주는지
- 버튼 클릭 시점 편차(skew) — 얼마나 "동시"였는지

기본은 로그인 + 확인까지만 한다. 업로드 등 후속 동작은 포함하지 않는다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, async_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://skmr.ifns.work/"
DEFAULT_ACCOUNTS = PROJECT_ROOT / "config" / "skmr_accounts.json"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "skmr_concurrent_login.json"

USERNAME_SELECTOR = "input[type='text']"
PASSWORD_SELECTOR = "input[type='password']"
SUBMIT_SELECTOR = "button[type='submit'].login-form__submit"

LOGIN_PATH = "/auth/login"
ME_PATH = "/auth/me"


def configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(line_buffering=True, write_through=True)
        except Exception:
            pass


def load_accounts(path: Path, limit: int) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"계정 설정 파일이 없습니다: {path} (config/skmr_accounts.example.json 참고)")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    accounts = [{"username": str(a["username"]), "password": str(a["password"])} for a in data["accounts"]]
    return accounts[:limit] if limit > 0 else accounts


def log(username: str, message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] [{username}] {message}", flush=True)


async def read_json_body(response: Any) -> Any:
    try:
        return json.loads(await response.text())
    except Exception:
        return None


async def login_one(
    context: BrowserContext,
    account: dict[str, str],
    url: str,
    barrier: asyncio.Barrier,
    me_timeout_ms: int,
) -> dict[str, Any]:
    username = account["username"]
    result: dict[str, Any] = {"username": username, "ok": False, "status": "UNKNOWN"}
    page = await context.new_page()

    captured: dict[str, Any] = {}

    async def on_response(response: Any) -> None:
        request = response.request
        path = response.url.split("?", 1)[0]
        if request.resource_type not in ("xhr", "fetch"):
            return
        if request.method == "POST" and path.endswith(LOGIN_PATH):
            ts = time.perf_counter()
            captured["login_body"] = await read_json_body(response)
            captured["login_ts"] = ts
            captured["login_status"] = response.status  # 마지막에 기록: 대기 루프가 이 키로 완료를 판단
        elif request.method == "GET" and path.endswith(ME_PATH):
            body = await read_json_body(response)
            captured["me_body"] = body
            captured.setdefault("me_calls", []).append(
                {"status": response.status, "login_seen": "login_ts" in captured, "body": body}
            )
            captured["me_status"] = response.status  # 마지막에 기록: 대기 루프가 이 키로 완료를 판단

    page.on("response", lambda response: asyncio.ensure_future(on_response(response)))

    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.locator(USERNAME_SELECTOR).first.fill(username)
        await page.locator(PASSWORD_SELECTOR).first.fill(account["password"])
        log(username, "폼 입력 완료 - 동시 시작 대기")

        await barrier.wait()
        click_ts = time.perf_counter()
        result["_click_ts"] = click_ts
        await page.locator(SUBMIT_SELECTOR).first.click()

        deadline = time.perf_counter() + me_timeout_ms / 1000
        while time.perf_counter() < deadline and ("login_status" not in captured or "me_status" not in captured):
            await page.wait_for_timeout(100)

        result["login_http_status"] = captured.get("login_status")
        if "login_ts" in captured:
            result["login_elapsed_ms"] = round((captured["login_ts"] - click_ts) * 1000)
        body = captured.get("login_body")
        result["login_response_username"] = body.get("username") if isinstance(body, dict) else None
        result["login_message"] = body.get("message") if isinstance(body, dict) else None

        me_body = captured.get("me_body")
        result["me_http_status"] = captured.get("me_status")
        result["me_username"] = me_body.get("username") if isinstance(me_body, dict) else None
        result["final_url"] = page.url
        result["me_calls"] = captured.get("me_calls", [])

        login_ok = captured.get("login_status") == 200 and result["login_response_username"] == username
        me_ok = captured.get("me_status") == 200 and result["me_username"] == username
        result["login_ok"] = login_ok
        result["me_ok"] = me_ok
        result["ok"] = login_ok and me_ok
        result["status"] = "OK" if result["ok"] else "FAILED"
        log(
            username,
            f"login={result['login_http_status']} ({result.get('login_elapsed_ms')}ms) "
            f"me={result['me_http_status']} me_user={result['me_username']} -> {result['status']}",
        )
    except Exception as exc:
        result["status"] = "ERROR"
        result["message"] = str(exc)
        log(username, f"오류: {exc}")
        try:
            await barrier.abort()
        except Exception:
            pass
    finally:
        result["_page"] = page
    return result


async def run_round(browser: Any, accounts: list[dict[str, str]], args: argparse.Namespace, index: int) -> dict[str, Any]:
    print(f"\n=== Round {index} : {len(accounts)}계정 동시 로그인 ===", flush=True)
    contexts = [await browser.new_context(ignore_https_errors=True) for _ in accounts]
    barrier = asyncio.Barrier(len(accounts))
    try:
        results = await asyncio.gather(
            *(login_one(ctx, acc, args.url, barrier, args.me_timeout_ms) for ctx, acc in zip(contexts, accounts))
        )
        clicks = [r["_click_ts"] for r in results if "_click_ts" in r]
        skew_ms = round((max(clicks) - min(clicks)) * 1000, 1) if clicks else None
        if args.hold_ms > 0:
            await asyncio.sleep(args.hold_ms / 1000)
        for r in results:
            r.pop("_click_ts", None)
            r.pop("_page", None)
        usernames_seen = [r.get("me_username") for r in results]
        isolated = len(set(usernames_seen)) == len(usernames_seen) and None not in usernames_seen
        summary = {
            "round": index,
            "all_ok": all(r["ok"] for r in results),
            "click_skew_ms": skew_ms,
            "sessions_isolated": isolated,
            "results": results,
        }
        print(
            f"Round {index} 결과: all_ok={summary['all_ok']} skew={skew_ms}ms isolated={isolated}",
            flush=True,
        )
        return summary
    finally:
        for ctx in contexts:
            await ctx.close()


async def run(args: argparse.Namespace) -> int:
    accounts = load_accounts(args.accounts, args.max_users)
    report: dict[str, Any] = {
        "mode": "SKMR_CONCURRENT_LOGIN",
        "url": args.url,
        "users": [a["username"] for a in accounts],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "rounds": [],
    }
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=args.headless)
        try:
            for i in range(1, args.rounds + 1):
                report["rounds"].append(await run_round(browser, accounts, args, i))
        finally:
            await browser.close()

    report["all_ok"] = all(r["all_ok"] for r in report["rounds"])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport: {args.report}", flush=True)
    return 0 if report["all_ok"] else 1


def main() -> int:
    configure_console_output()
    parser = argparse.ArgumentParser(description="skmr 다중 계정 동시 로그인 테스트")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--accounts", type=Path, default=DEFAULT_ACCOUNTS)
    parser.add_argument("--max-users", type=int, default=0, help="앞에서 N개 계정만 사용 (0=전체)")
    parser.add_argument("--rounds", type=int, default=1, help="반복 횟수 (매 라운드 새 컨텍스트로 재로그인)")
    parser.add_argument("--me-timeout-ms", type=int, default=15000)
    parser.add_argument("--hold-ms", type=int, default=2000, help="결과 확인용으로 로그인 상태를 유지하는 시간")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
