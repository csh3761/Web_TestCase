# -*- coding: utf-8 -*-
"""skmr.ifns.work 심층 기능 스캔 probe.

1차 스캔(probe_menu_discovery.py)에서 찾은 최상위 버튼들을 하나씩 실제로 클릭해보고,
그 결과로 열리는 모달/드롭다운/패널 안의 버튼·링크·텍스트까지 재귀적으로(1단계) 수집한다.
매 클릭 전에 항상 동일한 기준 화면(base_url)으로 되돌아가서 시작하기 때문에, 이전 클릭의
부작용(열린 패널이 안 닫히는 등)이 다음 시도에 영향을 주지 않는다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, parse_qs

from playwright.async_api import async_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://skmr.ifns.work/"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "skmr_deep_menu_discovery.json"
DEFAULT_SCREENSHOT_DIR = PROJECT_ROOT / "reports" / "skmr_deep_scan"

USERNAME_SELECTOR = "input[type='text']"
PASSWORD_SELECTOR = "input[type='password']"
SUBMIT_SELECTOR = "button[type='submit'].login-form__submit"

# li.explorer-tree__item는 형제가 아니라 중첩(자식 li가 부모 li 안에 포함) 구조라서,
# querySelector로 바로 찾으면 자기 자신이 아니라 중첩된 자식의 체브론/라벨을 잘못 잡을 수
# 있다. closest()로 "가장 가까운 explorer-tree__item 조상이 자기 자신인" 요소만 골라서
# 진짜 자기 소유의 체브론/라벨을 찾는다.
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

# Playwright의 synthetic click은 시각적으로 겹치는(장식용 aria-hidden 레일 등) 요소가
# 있으면 "가로챔"으로 판단해 재시도만 반복하다 타임아웃난다. 실제 사용자 클릭이라면
# 문제없을 장식 요소이므로, DOM에서 직접 element.click()을 호출해 우회한다 - 동시에
# 위의 중첩 체브론 오매칭 문제도 함께 해결된다(같은 closest() 로직으로 자기 것만 클릭).
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

TOP_LEVEL_SCAN_SCRIPT = """() => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
    const buttons = Array.from(document.querySelectorAll("button")).filter(visible).map((node) => ({
        visibleText: cleanText(node.innerText || node.textContent || ""),
        ariaLabel: node.getAttribute("aria-label") || "",
        title: node.getAttribute("title") || "",
        className: node.getAttribute("class") || "",
    }));
    return buttons;
}"""

# is-active / is-open 처럼 클릭 시점의 상태에 따라 붙었다 떨어졌다 하는 클래스는
# 새로고침 직후 selector 매칭에 방해가 되므로 제외하고 기본(base) 클래스만 남긴다.
STATE_CLASS_TOKENS = {
    "is-active", "is-open", "is-pinned", "is-current", "is-selected", "is-expanded",
}

OVERLAY_SCAN_SCRIPT = """() => {
    const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
    const cleanText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
    const overlaySelectors = [
        "[role='dialog']", "[role='alertdialog']", "[role='menu']", "[role='listbox']",
        "[data-state='open']", "[class*='modal']", "[class*='Modal']",
        "[class*='dropdown']", "[class*='Dropdown']", "[class*='popover']", "[class*='Popover']",
        "[class*='panel']", "[class*='Panel']", "[class*='dialog']", "[class*='Dialog']",
        "[class*='tooltip']",
    ];
    const overlays = Array.from(document.querySelectorAll(overlaySelectors.join(","))).filter((el) => {
        if (!visible(el)) return false;
        const box = el.getBoundingClientRect();
        return box.width > 10 && box.height > 10;
    });
    // 상위 요소가 이미 포함된 하위 요소는 중복이므로 최상위 컨테이너 위주로 정리
    const top = overlays.filter((el) => !overlays.some((other) => other !== el && other.contains(el)));
    return top.slice(0, 8).map((node) => {
        const items = Array.from(node.querySelectorAll("button, a, li, [role='menuitem'], [role='option'], input"))
            .filter(visible)
            .slice(0, 40)
            .map((item) => ({
                tag: item.tagName,
                text: cleanText(item.innerText || item.textContent || item.getAttribute("placeholder") || item.getAttribute("aria-label") || "").slice(0, 80),
                className: item.getAttribute("class") || "",
            }));
        return {
            tag: node.tagName,
            className: node.getAttribute("class") || "",
            role: node.getAttribute("role") || "",
            textSample: cleanText(node.innerText || node.textContent || "").slice(0, 500),
            itemCount: items.length,
            items,
        };
    });
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


# API 정의서 작성을 위해 요청/응답 바디도 캡처하지만, 로그인 요청의 비밀번호처럼
# 민감한 값은 그대로 저장하지 않고 이 토큰이 키 이름에 포함되면 값을 마스킹한다.
SENSITIVE_KEY_TOKENS = ("password", "pwd", "token", "secret", "authorization")

# 응답 바디는 문서 목록처럼 수십 건짜리 배열이 올 수 있어, 스펙 작성에 필요한 "형태"만
# 보이도록 배열은 앞의 몇 개만, 문자열은 일정 길이까지만 남기고 잘라낸다.
BODY_ARRAY_SAMPLE_LIMIT = 2
BODY_STRING_TRUNCATE_LIMIT = 300


def sanitize_body(value: Any, _depth: int = 0) -> Any:
    if _depth > 6:
        return "...(truncated depth)"
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if any(token in str(key).lower() for token in SENSITIVE_KEY_TOKENS):
                sanitized[key] = "***MASKED***"
            else:
                sanitized[key] = sanitize_body(item, _depth + 1)
        return sanitized
    if isinstance(value, list):
        sample = [sanitize_body(item, _depth + 1) for item in value[:BODY_ARRAY_SAMPLE_LIMIT]]
        if len(value) > BODY_ARRAY_SAMPLE_LIMIT:
            sample.append(f"...(총 {len(value)}건 중 {BODY_ARRAY_SAMPLE_LIMIT}건만 표시)")
        return sample
    if isinstance(value, str) and len(value) > BODY_STRING_TRUNCATE_LIMIT:
        return value[:BODY_STRING_TRUNCATE_LIMIT] + "...(truncated)"
    return value


def attach_api_capture(page: Any) -> list[dict[str, Any]]:
    """page의 실제 REST API 호출(XHR/fetch)만 골라서 기록하는 리스너를 붙인다.

    resource_type이 xhr/fetch인 요청만 REST API로 간주한다 - 정적 리소스(js/css/이미지 등)나
    문서 네비게이션은 여기서 자동으로 제외되므로 확장자 기반 필터보다 훨씬 정확하다.
    호출 시점(자동 클릭 루프의 각 액션) 전후로 이 리스트의 길이를 스냅샷해서 슬라이싱하면,
    "어떤 버튼을 눌렀을 때 어떤 API가 호출됐는지" 매핑할 수 있다.
    API 정의서 작성을 위해 쿼리 파라미터, 요청 바디, 응답 바디(샘플)까지 함께 기록한다.
    """
    captured: list[dict[str, Any]] = []

    async def handle_response(response: Any) -> None:
        try:
            request = response.request
            if request.resource_type not in ("xhr", "fetch"):
                return
            parsed = urlsplit(request.url)

            query_params: dict[str, Any] = {}
            if parsed.query:
                for key, values in parse_qs(parsed.query).items():
                    query_params[key] = values[0] if len(values) == 1 else values

            request_body: Any = None
            try:
                post_data_json = request.post_data_json
                if post_data_json is not None:
                    request_body = sanitize_body(post_data_json)
                else:
                    raw_post_data = request.post_data
                    if raw_post_data:
                        request_body = sanitize_body(raw_post_data)
            except Exception:
                pass

            response_content_type = response.headers.get("content-type", "")
            response_body: Any = None
            if response.status != 204 and (
                "json" in response_content_type or "text" in response_content_type
            ):
                try:
                    text = await response.text()
                    try:
                        response_body = sanitize_body(json.loads(text))
                    except json.JSONDecodeError:
                        response_body = sanitize_body(text)
                except Exception:
                    pass

            captured.append(
                {
                    "method": request.method,
                    "url": request.url,
                    "path": parsed.path,
                    "query": parsed.query,
                    "query_params": query_params,
                    "request_body": request_body,
                    "status": response.status,
                    "response_content_type": response_content_type,
                    "response_body": response_body,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                }
            )
        except Exception:
            pass

    page.on("response", handle_response)
    return captured


def summarize_api_calls(captured: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """(method, path) 기준으로 중복 제거한 REST API 엔드포인트 요약.

    API 정의서 작성용으로, 각 엔드포인트별 관측된 쿼리 파라미터 키 전체 목록과
    요청/응답 바디 샘플(첫 호출 기준)도 함께 담는다.
    """
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for call in captured:
        key = (call["method"], call["path"])
        if key not in grouped:
            grouped[key] = {
                "method": call["method"],
                "path": call["path"],
                "call_count": 0,
                "statuses_seen": set(),
                "query_param_keys": set(),
                "sample_query": call["query"],
                "sample_query_params": call["query_params"],
                "sample_request_body": call["request_body"],
                "sample_response_body": call["response_body"],
            }
        bucket = grouped[key]
        bucket["call_count"] += 1
        bucket["statuses_seen"].add(call["status"])
        bucket["query_param_keys"].update(call["query_params"].keys())
        # request/response 바디는 값이 있는 첫 호출 것을 샘플로 남긴다(이후 호출로 덮지 않음).
        if bucket["sample_request_body"] is None and call["request_body"] is not None:
            bucket["sample_request_body"] = call["request_body"]
        if bucket["sample_response_body"] is None and call["response_body"] is not None:
            bucket["sample_response_body"] = call["response_body"]
    result = []
    for (method, path), bucket in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0])):
        bucket["statuses_seen"] = sorted(bucket["statuses_seen"])
        bucket["query_param_keys"] = sorted(bucket["query_param_keys"])
        result.append(bucket)
    return result


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


def strip_state_classes(class_name: str) -> str:
    tokens = [token for token in class_name.split() if token and token not in STATE_CLASS_TOKENS]
    return " ".join(tokens)


def dedupe_candidates(buttons: list[dict[str, str]]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str], int] = {}
    candidates: list[dict[str, Any]] = []
    for button in buttons:
        display_name = button["ariaLabel"] or button["visibleText"] or button["title"]
        base_class = strip_state_classes(button["className"])
        key = (display_name, base_class)
        occurrence = seen.get(key, 0)
        seen[key] = occurrence + 1
        if occurrence == 0:
            candidates.append(
                {
                    "display_name": display_name,
                    "visible_text": button["visibleText"],
                    "aria_label": button["ariaLabel"],
                    "base_class": base_class,
                    "full_class": button["className"],
                }
            )
    return candidates


def build_locator(page: Any, candidate: dict[str, str]):
    base_class = candidate["base_class"]
    class_selector = "button" + "".join(f".{token}" for token in base_class.split() if token)
    aria_label = candidate["aria_label"]
    visible_text = candidate["visible_text"]

    # 아이콘 전용 버튼은 화면에 보이는 텍스트가 없고 aria-label로만 이름이 붙는 경우가
    # 많아서, has_text(보이는 텍스트 기준) 대신 aria-label 속성 selector를 우선 사용한다.
    if aria_label:
        # ensure_ascii=True(기본값)이면 한글이 \\uXXXX(JSON 이스케이프)로 바뀌는데,
        # 이는 CSS 셀렉터 이스케이프 문법과 달라 실제로는 전혀 매칭되지 않는다.
        return page.locator(f"{class_selector}[aria-label={json.dumps(aria_label, ensure_ascii=False)}]").first
    if visible_text:
        return page.locator(class_selector).filter(has_text=visible_text).first
    return page.locator(class_selector).first


async def run(args: argparse.Namespace) -> int:
    result: dict[str, Any] = {
        "mode": "SKMR_DEEP_MENU_DISCOVERY_PROBE",
        "username": args.username,
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    args.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=args.headless)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        captured_api_calls = attach_api_capture(page)
        try:
            print(f"로그인 시작: {args.username}", flush=True)
            login_result = await login(page, args.username, args.password, args.url)
            result["login"] = login_result
            print(f"로그인 결과: {login_result['login_response_status']} -> {login_result['page_url']}", flush=True)
            base_url = page.url

            raw_buttons = await page.evaluate(TOP_LEVEL_SCAN_SCRIPT)
            all_candidates = dedupe_candidates(raw_buttons)

            # "상세조건검색"처럼 다른 패널(통합검색) 안에서만 나타나는 중첩 버튼은
            # 일반 루프에서 제외하고 별도로(부모를 먼저 열고) 체이닝 처리한다.
            NESTED_CHILDREN = {"상세조건검색"}
            candidates = [c for c in all_candidates if c["display_name"] not in NESTED_CHILDREN]
            nested_candidates = [c for c in all_candidates if c["display_name"] in NESTED_CHILDREN]

            # 대시보드/권한 요청 패널/최근·최신 문서/내 정보/최근 방문 폴더처럼 큰 패널을
            # 여는 버튼은 클릭 후 패널이 화면에 남아 사이드바/트리 등 다른 버튼을 가려버리는
            # 것을 확인했다(state drift). 그런 버튼들을 맨 뒤로 미뤄서, 상태에 민감한 다른
            # 후보들을 화면이 깨끗할 때 먼저 처리한다.
            def is_big_panel_opener(candidate: dict[str, Any]) -> bool:
                base_class = candidate["base_class"]
                return any(token in base_class for token in ("request-open-btn", "kebab", "profile"))

            candidates.sort(key=is_big_panel_opener)
            print(f"클릭 대상(중복 제거) {len(candidates)}개 발견 (+중첩 {len(nested_candidates)}개는 별도 처리)", flush=True)

            # 이 앱(SDMS 계열)은 페이지를 새로 열 때마다 부팅에 20초 이상 걸리는 것으로
            # 이미 react01에서 확인된 바 있다. 매 후보마다 goto()로 새로고침하면 그 지연을
            # 23번 반복하게 되므로, 대신 로그인 직후 한 번만 넉넉히 기다린 뒤 같은 세션
            # 안에서 Escape로 정리하며 이어서 진행한다(새로고침 없음).
            print("초기 부팅 대기 (약 20초)...", flush=True)
            await page.wait_for_timeout(20000)

            explorations: list[dict[str, Any]] = []
            for index, candidate in enumerate(candidates):
                label = candidate["display_name"] or candidate["base_class"]
                print(f"[{index + 1}/{len(candidates)}] 클릭 시도: {label}", flush=True)
                entry: dict[str, Any] = {"candidate": candidate, "label": label}
                try:
                    # 이전 시도에서 열린 드롭다운/모달을 Escape로 정리(새로고침 없이).
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(200)

                    # 클릭 전 오버레이 상태를 기준선으로 잡아, 클릭 후 새로 나타난 것만 걸러낸다
                    # (사이드바처럼 항상 떠 있는 요소가 매번 "새 오버레이"로 오인되는 걸 방지).
                    baseline_overlays = await page.evaluate(OVERLAY_SCAN_SCRIPT)
                    baseline_signatures = {(item["className"], item["textSample"][:80]) for item in baseline_overlays}

                    locator = build_locator(page, candidate)
                    await locator.wait_for(state="visible", timeout=6000)

                    if await locator.is_disabled():
                        # 뒤로가기/앞으로가기/상위 폴더처럼 현재 상태(방문 기록 없음 등)에서
                        # 정상적으로 비활성화된 버튼 - 실패가 아니라 그대로 기록만 한다.
                        entry["status"] = "DISABLED"
                        print("    -> 비활성(disabled) 상태라 클릭 생략", flush=True)
                        explorations.append(entry)
                        continue

                    api_start = len(captured_api_calls)
                    await locator.click(timeout=6000)
                    await page.wait_for_timeout(1200)

                    entry["url_after_click"] = page.url
                    entry["navigated"] = page.url != base_url
                    entry["api_calls"] = list(captured_api_calls[api_start:])

                    all_overlays = await page.evaluate(OVERLAY_SCAN_SCRIPT)
                    new_overlays = [
                        item for item in all_overlays
                        if (item["className"], item["textSample"][:80]) not in baseline_signatures
                    ]
                    entry["new_overlays"] = new_overlays
                    entry["new_overlay_count"] = len(new_overlays)

                    screenshot_path = args.screenshot_dir / f"{index + 1:02d}_{safe_filename(label)}.png"
                    await page.screenshot(path=str(screenshot_path))
                    entry["screenshot"] = str(screenshot_path)

                    entry["status"] = "OK"
                    print(
                        f"    -> 새 오버레이 {len(new_overlays)}개, API 호출 {len(entry['api_calls'])}개, "
                        f"navigated={entry['navigated']}",
                        flush=True,
                    )
                except Exception as exc:
                    entry["status"] = "FAILED"
                    entry["message"] = str(exc)
                    print(f"    -> 실패: {exc}", flush=True)
                explorations.append(entry)

            # 중첩 버튼: 부모(통합검색)를 먼저 열고, 그 안에서 자식(상세조건검색)을 찾아 클릭한다.
            nested_explorations: list[dict[str, Any]] = []
            if nested_candidates:
                print("중첩 버튼 처리: 통합검색 패널을 먼저 엽니다", flush=True)
                nested_entry: dict[str, Any] = {"label": "상세조건검색 (통합검색 하위)"}
                try:
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(200)
                    parent_locator = page.locator("button.explorer-toolbar__unified-search-btn[aria-label=\"통합검색\"]").first
                    await parent_locator.wait_for(state="visible", timeout=6000)
                    api_start = len(captured_api_calls)
                    await parent_locator.click(timeout=6000)
                    await page.wait_for_timeout(500)

                    baseline_overlays = await page.evaluate(OVERLAY_SCAN_SCRIPT)
                    baseline_signatures = {(item["className"], item["textSample"][:80]) for item in baseline_overlays}

                    child_locator = page.locator("button.unified-search-dropdown__detail-toggle").filter(has_text="상세조건검색").first
                    await child_locator.wait_for(state="visible", timeout=6000)
                    await child_locator.click(timeout=6000)
                    await page.wait_for_timeout(1200)

                    nested_entry["api_calls"] = list(captured_api_calls[api_start:])

                    all_overlays = await page.evaluate(OVERLAY_SCAN_SCRIPT)
                    new_overlays = [
                        item for item in all_overlays
                        if (item["className"], item["textSample"][:80]) not in baseline_signatures
                    ]
                    nested_entry["new_overlays"] = new_overlays
                    nested_entry["new_overlay_count"] = len(new_overlays)

                    screenshot_path = args.screenshot_dir / "nested_상세조건검색.png"
                    await page.screenshot(path=str(screenshot_path))
                    nested_entry["screenshot"] = str(screenshot_path)
                    nested_entry["status"] = "OK"
                    print(f"    -> 새 오버레이 {len(new_overlays)}개", flush=True)
                except Exception as exc:
                    nested_entry["status"] = "FAILED"
                    nested_entry["message"] = str(exc)
                    print(f"    -> 실패: {exc}", flush=True)
                nested_explorations.append(nested_entry)
            result["nested_explorations"] = nested_explorations

            # 사이드바 트리도 같은 패턴: 펼치기(체브론)를 눌러야 하위 폴더 항목이 나타난다.
            # 닫혀있는 체브론을 라운드마다 전부 펼치면서, 그 결과로 새로 나타나는 하위
            # 체브론까지(최대 3라운드) 이어서 펼쳐 depth 여러 단계를 순차적으로 드러낸다.
            print("사이드바 트리 심화 탐색 시작", flush=True)
            sidebar_exploration: dict[str, Any] = {"rounds": []}
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(200)
                if not await page.locator(".explorer-sidebar").first.is_visible():
                    reopen = page.locator("button.explorer-workbox-nav__item").filter(has_text="부서문서함").first
                    if await reopen.count() > 0:
                        await reopen.click(timeout=4000)
                        await page.wait_for_timeout(500)

                for round_index in range(3):
                    tree = await page.evaluate(SIDEBAR_TREE_SCAN_SCRIPT)
                    closed_chevrons = [item for item in tree if item["hasChevron"] and not item["chevronOpen"]]
                    if not closed_chevrons:
                        break
                    round_result: dict[str, Any] = {
                        "round": round_index + 1,
                        "before_count": len(tree),
                        "expanded": [],
                    }
                    round_result["api_calls_by_item"] = {}
                    for item in closed_chevrons:
                        try:
                            api_start = len(captured_api_calls)
                            click_result = await page.evaluate(EXPAND_CHEVRON_SCRIPT, item["index"])
                            if click_result["status"] != "CLICKED":
                                raise RuntimeError(click_result["status"])
                            await page.wait_for_timeout(900)
                            label_key = item["labelText"] or item["text"]
                            round_result["expanded"].append(label_key)
                            round_result["api_calls_by_item"][label_key] = list(captured_api_calls[api_start:])
                        except Exception as exc:
                            round_result.setdefault("expand_failed", []).append(
                                {"label": item["labelText"] or item["text"], "message": str(exc)}
                            )
                    after_tree = await page.evaluate(SIDEBAR_TREE_SCAN_SCRIPT)
                    round_result["after_count"] = len(after_tree)
                    sidebar_exploration["rounds"].append(round_result)
                    failed_labels = [f["label"] for f in round_result.get("expand_failed", [])]
                    print(
                        f"    사이드바 확장 {round_index + 1}회차: "
                        f"{round_result['before_count']} -> {round_result['after_count']}개 항목 "
                        f"(펼친 항목: {', '.join(round_result['expanded']) or '없음'}"
                        f"{', 실패: ' + ', '.join(failed_labels) if failed_labels else ''})",
                        flush=True,
                    )

                final_tree = await page.evaluate(SIDEBAR_TREE_SCAN_SCRIPT)
                sidebar_exploration["final_tree"] = final_tree
                screenshot_path = args.screenshot_dir / "sidebar_tree_expanded.png"
                await page.screenshot(path=str(screenshot_path), full_page=True)
                sidebar_exploration["screenshot"] = str(screenshot_path)
                sidebar_exploration["status"] = "OK"
                print(f"사이드바 트리 최종 항목 수: {len(final_tree)}", flush=True)
            except Exception as exc:
                sidebar_exploration["status"] = "FAILED"
                sidebar_exploration["message"] = str(exc)
                print(f"    -> 실패: {exc}", flush=True)
            result["sidebar_tree_exploration"] = sidebar_exploration

            result["candidate_count"] = len(candidates)
            result["explorations"] = explorations
            result["all_captured_api_calls"] = captured_api_calls
            result["api_endpoint_summary"] = summarize_api_calls(captured_api_calls)
            print(
                f"REST API 캡처: 총 호출 {len(captured_api_calls)}건, "
                f"고유 엔드포인트(method+path) {len(result['api_endpoint_summary'])}개",
                flush=True,
            )
            result["status"] = "PROBE_DONE"
            return 0
        except Exception as exc:
            result["status"] = "FAILED"
            result["message"] = str(exc)
            result["all_captured_api_calls"] = captured_api_calls
            result["api_endpoint_summary"] = summarize_api_calls(captured_api_calls)
            print(f"실패: {exc}", flush=True)
            return 1
        finally:
            print("스캔 종료, 60초간 화면을 유지합니다 (확인 시간)...", flush=True)
            await page.wait_for_timeout(60000)
            await context.close()
            await browser.close()
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Report: {args.report}", flush=True)


def safe_filename(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value)
    return cleaned[:40] or "item"


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
