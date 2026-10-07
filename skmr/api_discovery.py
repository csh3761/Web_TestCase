# -*- coding: utf-8 -*-
"""skmr API 탐색 통합 도구.

브라우저로 skmr 에 접속해 실제로 발생하는 XHR/fetch 요청을 수집하고, 엔드포인트별로 정리한다.
기존에 둘로 나뉘어 있던 기능을 하나로 합친 것이다.
  - 자동 스캔  : 상단 버튼 전체 클릭, 중첩 패널, 사이드바 트리 확장 (구 probe_deep_menu_discovery.py)
  - 수동 조작  : 사람이 직접 화면을 조작(예: 업로드)하는 동안 기록 (구 capture_upload_api.py)

실행 모드 (--mode)
  both   로그인 -> 자동 스캔 -> 수동 조작 구간 (기본)
  auto   로그인 -> 자동 스캔만
  manual 로그인 -> 수동 조작 구간만 (업로드 같은 쓰기 동작 캡처용)

수집 내용
  - 로그인 호출 포함 (phase=login): 요청 헤더 이름 확인에 유용 (API key 헤더 등)
  - 요청 순서, method/path/query, 요청 헤더(Authorization/Cookie 값은 마스킹), 요청 바디(JSON 은 내용,
    바이너리 chunk 는 크기만), 응답 상태/헤더/바디 샘플
  - id/uuid/index 가 들어간 경로는 {id}/{index} 로 일반화해서 엔드포인트별로 묶음

산출물
  reports/skmr_api_discovery.json  전체(호출 단위 + 엔드포인트 요약 + 자동 스캔 상세)
  reports/skmr_api_discovery.md    엔드포인트 표 (Notion 가져오기용)
  reports/skmr_api_discovery.csv   엔드포인트 표 (Notion 데이터베이스 가져오기용, UTF-8 BOM)

자동 스캔은 업로드/삭제 같은 쓰기 동작을 하지 않는다 (버튼 클릭만).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from playwright.async_api import async_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://skmr.ifns.work/"
DEFAULT_ACCOUNTS = PROJECT_ROOT / "config" / "skmr_accounts.json"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "skmr_api_discovery.json"
DEFAULT_SCREENSHOT_DIR = PROJECT_ROOT / "reports" / "skmr_api_discovery_shots"

USERNAME_SELECTOR = "input[type='text']"
PASSWORD_SELECTOR = "input[type='password']"
SUBMIT_SELECTOR = "button[type='submit'].login-form__submit"

# ---------------------------------------------------------------- 자동 스캔용 DOM 스크립트
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
# 문제없을 장식 요소이므로, DOM에서 직접 element.click()을 호출해 우회한다.
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
STATE_CLASS_TOKENS = {"is-active", "is-open", "is-pinned", "is-current", "is-selected", "is-expanded"}

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


# ---------------------------------------------------------------- 수집 코어 (자동/수동 공용)

SENSITIVE_HEADERS = ("authorization", "cookie", "set-cookie", "x-csrf", "x-xsrf")
SENSITIVE_KEY_TOKENS = ("password", "pwd", "token", "secret", "authorization")
IGNORED_PATH_PARTS = ("/cdn-cgi/",)
JSON_BODY_LIMIT = 2000
STRING_LIMIT = 300
ARRAY_SAMPLE_LIMIT = 2


def mask_headers(headers: dict[str, str]) -> dict[str, str]:
    masked: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower().startswith(SENSITIVE_HEADERS):
            scheme = value.split(" ", 1)[0] if key.lower() == "authorization" and " " in value else ""
            masked[key] = f"***MASKED*** {scheme}".strip()
        else:
            masked[key] = value
    return masked


def sanitize(value: Any, depth: int = 0) -> Any:
    """민감 키는 마스킹, 배열은 앞 몇 건만, 긴 문자열은 잘라서 '형태'만 남긴다."""
    if depth > 6:
        return "...(depth)"
    if isinstance(value, dict):
        return {
            k: "***MASKED***" if any(t in str(k).lower() for t in SENSITIVE_KEY_TOKENS) else sanitize(v, depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, list):
        out = [sanitize(v, depth + 1) for v in value[:ARRAY_SAMPLE_LIMIT]]
        if len(value) > ARRAY_SAMPLE_LIMIT:
            out.append(f"...(총 {len(value)}건 중 {ARRAY_SAMPLE_LIMIT}건만 표시)")
        return out
    if isinstance(value, str) and len(value) > STRING_LIMIT:
        return value[:STRING_LIMIT] + "...(truncated)"
    return value


def generalize_path(path: str) -> str:
    """id/uuid/숫자 index 세그먼트를 {id}/{index} 로 바꿔 엔드포인트 단위로 묶는다."""
    parts = path.split("/")
    out: list[str] = []
    for i, part in enumerate(parts):
        if not part:
            out.append(part)
        elif part.isdigit():
            out.append("{index}" if i > 0 and parts[i - 1] in ("chunks", "parts", "chunk", "part") else "{n}")
        elif re.fullmatch(r"[0-9a-fA-F-]{32,}", part) or (
            len(part) >= 16 and re.fullmatch(r"[A-Za-z0-9_\-=.:]+", part) and re.search(r"\d", part)
        ):
            out.append("{id}")
        elif re.fullmatch(r"[A-Za-z]+_[A-Za-z0-9_\-]{8,}", part):
            out.append("{id}")
        else:
            out.append(part)
    return "/".join(out)


def describe_request_body(request: Any) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    info: dict[str, Any] = {"content_type": content_type}
    try:
        buffer = request.post_data_buffer
    except Exception:
        buffer = None
    if buffer is None:
        return info
    info["size"] = len(buffer)
    is_text = "json" in content_type or "x-www-form-urlencoded" in content_type or "text/" in content_type
    if is_text and len(buffer) <= JSON_BODY_LIMIT * 20:
        try:
            text = buffer.decode("utf-8")
            try:
                info["json"] = sanitize(json.loads(text))
            except json.JSONDecodeError:
                info["text"] = text[:JSON_BODY_LIMIT]
        except UnicodeDecodeError:
            info["binary"] = True
    else:
        info["binary"] = True
        if "multipart" in content_type:
            info["note"] = "multipart: 필드/파일 구성은 별도 확인 필요 (크기만 기록)"
    return info


class Capture:
    """page 의 XHR/fetch 호출을 순서대로 기록한다. mark()/since() 로 '특정 동작 중 발생한 호출'을 잘라낼 수 있다."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.phase = "login"
        self._seq: dict[int, int] = {}
        self._counter = 0

    def attach(self, page: Any) -> None:
        page.on("request", self._on_request)
        page.on("response", lambda response: asyncio.ensure_future(self._on_response(response)))

    def mark(self) -> int:
        return len(self.events)

    def since(self, mark: int) -> list[dict[str, Any]]:
        return list(self.events[mark:])

    def _on_request(self, request: Any) -> None:
        if request.resource_type in ("xhr", "fetch"):
            self._counter += 1
            self._seq[id(request)] = self._counter

    async def _on_response(self, response: Any) -> None:
        try:
            request = response.request
            if request.resource_type not in ("xhr", "fetch"):
                return
            parsed = urlsplit(request.url)
            if any(part in parsed.path for part in IGNORED_PATH_PARTS):
                return
            content_type = response.headers.get("content-type", "")
            body: Any = None
            if response.status != 204 and ("json" in content_type or "text" in content_type):
                try:
                    text = await response.text()
                    try:
                        body = sanitize(json.loads(text))
                    except json.JSONDecodeError:
                        body = text[:STRING_LIMIT]
                except Exception:
                    pass
            self.events.append(
                {
                    "seq": self._seq.get(id(request), 0),
                    "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                    "phase": self.phase,
                    "method": request.method,
                    "path": parsed.path,
                    "path_template": generalize_path(parsed.path),
                    "query": {k: (v[0] if len(v) == 1 else v) for k, v in parse_qs(parsed.query).items()},
                    "request_headers": mask_headers(dict(request.headers)),
                    "request_body": describe_request_body(request),
                    "status": response.status,
                    "response_content_type": content_type,
                    "response_body": body,
                }
            )
            if self.phase == "manual":  # 수동 구간은 실시간으로 보여준다
                e = self.events[-1]
                print(f"  #{e['seq']:>3} {e['method']:<6} {e['path_template']}  -> {e['status']}", flush=True)
        except Exception:
            pass


def summarize(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """(method, path_template) 기준 엔드포인트 요약. 최초 호출 순서대로 정렬."""
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for event in sorted(events, key=lambda e: e["seq"]):
        key = (event["method"], event["path_template"])
        group = grouped.setdefault(
            key,
            {
                "method": event["method"],
                "path_template": event["path_template"],
                "first_seq": event["seq"],
                "calls": 0,
                "statuses": set(),
                "phases": set(),
                "query_keys": set(),
                "path_examples": [],
                "sample_query": event["query"],
                "sample_request_headers": event["request_headers"],
                "sample_request_body": None,
                "sample_response_body": None,
            },
        )
        group["calls"] += 1
        group["statuses"].add(event["status"])
        group["phases"].add(event["phase"])
        group["query_keys"].update(event["query"].keys())
        if event["path"] not in group["path_examples"] and len(group["path_examples"]) < 3:
            group["path_examples"].append(event["path"])
        body = event["request_body"]
        if group["sample_request_body"] is None and (body.get("json") is not None or body.get("size") is not None):
            group["sample_request_body"] = body
        if group["sample_response_body"] is None and event["response_body"] is not None:
            group["sample_response_body"] = event["response_body"]
    result = []
    for group in sorted(grouped.values(), key=lambda g: g["first_seq"]):
        for field in ("statuses", "phases", "query_keys"):
            group[field] = sorted(group[field])
        result.append(group)
    return result


# ---------------------------------------------------------------- 로그인

def load_password(path: Path, username: str) -> str:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    for account in data["accounts"]:
        if account["username"] == username:
            return str(account["password"])
    raise KeyError(f"{path}에 {username} 계정이 없습니다.")


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


# ---------------------------------------------------------------- 자동 스캔

def safe_filename(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value)
    return cleaned[:40] or "item"


def strip_state_classes(class_name: str) -> str:
    return " ".join(t for t in class_name.split() if t and t not in STATE_CLASS_TOKENS)


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
    # 아이콘 전용 버튼은 aria-label 로만 이름이 붙는 경우가 많아 aria-label selector 를 우선한다.
    # (ensure_ascii=False: \\uXXXX 이스케이프는 CSS 셀렉터에서 매칭되지 않는다)
    if aria_label:
        return page.locator(f"{class_selector}[aria-label={json.dumps(aria_label, ensure_ascii=False)}]").first
    if visible_text:
        return page.locator(class_selector).filter(has_text=visible_text).first
    return page.locator(class_selector).first


async def scan_overlays(page: Any) -> tuple[list[dict[str, Any]], set[tuple[str, str]]]:
    overlays = await page.evaluate(OVERLAY_SCAN_SCRIPT)
    return overlays, {(item["className"], item["textSample"][:80]) for item in overlays}


async def run_auto(page: Any, capture: Capture, args: argparse.Namespace, result: dict[str, Any]) -> None:
    base_url = page.url
    capture.phase = "auto"
    args.screenshot_dir.mkdir(parents=True, exist_ok=True)

    all_candidates = dedupe_candidates(await page.evaluate(TOP_LEVEL_SCAN_SCRIPT))

    # "상세조건검색"처럼 다른 패널(통합검색) 안에서만 나타나는 중첩 버튼은 별도로(부모를 먼저 열고) 처리한다.
    nested_children = {"상세조건검색"}
    candidates = [c for c in all_candidates if c["display_name"] not in nested_children]
    nested_candidates = [c for c in all_candidates if c["display_name"] in nested_children]

    # 큰 패널을 여는 버튼은 클릭 후 패널이 남아 다른 버튼을 가려버리므로(state drift) 맨 뒤로 미룬다.
    candidates.sort(key=lambda c: any(t in c["base_class"] for t in ("request-open-btn", "kebab", "profile")))
    print(f"[auto] 클릭 대상(중복 제거) {len(candidates)}개 (+중첩 {len(nested_candidates)}개 별도 처리)", flush=True)

    # 이 앱은 페이지 부팅에 20초 이상 걸린다. 로그인 직후 한 번만 넉넉히 기다리고 같은 세션에서 계속 진행한다.
    print(f"[auto] 초기 부팅 대기 ({args.boot_wait_s:.0f}초)...", flush=True)
    await page.wait_for_timeout(int(args.boot_wait_s * 1000))

    explorations: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        label = candidate["display_name"] or candidate["base_class"]
        print(f"[auto {index + 1}/{len(candidates)}] 클릭: {label}", flush=True)
        entry: dict[str, Any] = {"candidate": candidate, "label": label}
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)
            _, baseline = await scan_overlays(page)

            locator = build_locator(page, candidate)
            await locator.wait_for(state="visible", timeout=6000)
            if await locator.is_disabled():
                entry["status"] = "DISABLED"  # 뒤로가기 등 현재 상태에서 정상적으로 비활성인 버튼
                print("    -> 비활성(disabled) 상태라 생략", flush=True)
                explorations.append(entry)
                continue

            mark = capture.mark()
            await locator.click(timeout=6000)
            await page.wait_for_timeout(1200)

            entry["url_after_click"] = page.url
            entry["navigated"] = page.url != base_url
            entry["api_calls"] = capture.since(mark)
            all_overlays, _ = await scan_overlays(page)
            new_overlays = [o for o in all_overlays if (o["className"], o["textSample"][:80]) not in baseline]
            entry["new_overlays"] = new_overlays
            entry["new_overlay_count"] = len(new_overlays)

            shot = args.screenshot_dir / f"{index + 1:02d}_{safe_filename(label)}.png"
            await page.screenshot(path=str(shot))
            entry["screenshot"] = str(shot)
            entry["status"] = "OK"
            print(f"    -> 새 오버레이 {len(new_overlays)}개, API 호출 {len(entry['api_calls'])}개, navigated={entry['navigated']}", flush=True)
        except Exception as exc:
            entry["status"] = "FAILED"
            entry["message"] = str(exc)
            print(f"    -> 실패: {exc}", flush=True)
        explorations.append(entry)
    result["candidate_count"] = len(candidates)
    result["explorations"] = explorations

    # 중첩 버튼: 부모(통합검색)를 먼저 열고 그 안에서 자식(상세조건검색)을 클릭
    nested: list[dict[str, Any]] = []
    if nested_candidates:
        print("[auto] 중첩 버튼 처리: 통합검색 패널을 먼저 엽니다", flush=True)
        nested_entry: dict[str, Any] = {"label": "상세조건검색 (통합검색 하위)"}
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)
            parent = page.locator('button.explorer-toolbar__unified-search-btn[aria-label="통합검색"]').first
            await parent.wait_for(state="visible", timeout=6000)
            mark = capture.mark()
            await parent.click(timeout=6000)
            await page.wait_for_timeout(500)
            _, baseline = await scan_overlays(page)

            child = page.locator("button.unified-search-dropdown__detail-toggle").filter(has_text="상세조건검색").first
            await child.wait_for(state="visible", timeout=6000)
            await child.click(timeout=6000)
            await page.wait_for_timeout(1200)

            nested_entry["api_calls"] = capture.since(mark)
            all_overlays, _ = await scan_overlays(page)
            nested_entry["new_overlays"] = [o for o in all_overlays if (o["className"], o["textSample"][:80]) not in baseline]
            nested_entry["new_overlay_count"] = len(nested_entry["new_overlays"])
            shot = args.screenshot_dir / "nested_상세조건검색.png"
            await page.screenshot(path=str(shot))
            nested_entry["screenshot"] = str(shot)
            nested_entry["status"] = "OK"
        except Exception as exc:
            nested_entry["status"] = "FAILED"
            nested_entry["message"] = str(exc)
            print(f"    -> 실패: {exc}", flush=True)
        nested.append(nested_entry)
    result["nested_explorations"] = nested

    # 사이드바 트리: 닫힌 체브론을 라운드마다 펼치고, 새로 나타난 하위 체브론까지 (최대 3라운드) 이어서 펼친다.
    print("[auto] 사이드바 트리 심화 탐색", flush=True)
    sidebar: dict[str, Any] = {"rounds": []}
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
            closed = [item for item in tree if item["hasChevron"] and not item["chevronOpen"]]
            if not closed:
                break
            round_result: dict[str, Any] = {"round": round_index + 1, "before_count": len(tree), "expanded": [], "api_calls_by_item": {}}
            for item in closed:
                try:
                    mark = capture.mark()
                    click_result = await page.evaluate(EXPAND_CHEVRON_SCRIPT, item["index"])
                    if click_result["status"] != "CLICKED":
                        raise RuntimeError(click_result["status"])
                    await page.wait_for_timeout(900)
                    key = item["labelText"] or item["text"]
                    round_result["expanded"].append(key)
                    round_result["api_calls_by_item"][key] = capture.since(mark)
                except Exception as exc:
                    round_result.setdefault("expand_failed", []).append(
                        {"label": item["labelText"] or item["text"], "message": str(exc)}
                    )
            round_result["after_count"] = len(await page.evaluate(SIDEBAR_TREE_SCAN_SCRIPT))
            sidebar["rounds"].append(round_result)
            print(f"    사이드바 확장 {round_index + 1}회차: {round_result['before_count']} -> {round_result['after_count']}개 항목", flush=True)

        sidebar["final_tree"] = await page.evaluate(SIDEBAR_TREE_SCAN_SCRIPT)
        shot = args.screenshot_dir / "sidebar_tree_expanded.png"
        await page.screenshot(path=str(shot), full_page=True)
        sidebar["screenshot"] = str(shot)
        sidebar["status"] = "OK"
    except Exception as exc:
        sidebar["status"] = "FAILED"
        sidebar["message"] = str(exc)
        print(f"    -> 실패: {exc}", flush=True)
    result["sidebar_tree_exploration"] = sidebar


# ---------------------------------------------------------------- 수동 조작

async def run_manual(capture: Capture) -> None:
    capture.phase = "manual"
    print("\n=== 수동 조작 구간 (캡처 중) ===", flush=True)
    print("브라우저에서 원하는 동작을 직접 수행하세요. (예: 폴더로 이동 -> 파일 업로드 -> 목록 반영 확인)", flush=True)
    print("끝나면 이 터미널에서 Enter 를 누르세요.\n", flush=True)
    await asyncio.to_thread(input)


# ---------------------------------------------------------------- 산출물

def endpoint_rows(endpoints: list[dict[str, Any]]) -> list[list[str]]:
    rows = []
    for ep in endpoints:
        body = ep["sample_request_body"] or {}
        rows.append(
            [
                ep["method"],
                ep["path_template"],
                str(ep["calls"]),
                ",".join(str(s) for s in ep["statuses"]),
                ",".join(ep["phases"]),
                ",".join(ep["query_keys"]),
                body.get("content_type", ""),
            ]
        )
    return rows


ENDPOINT_COLUMNS = ["메서드", "경로", "호출수", "상태코드", "수집구간", "쿼리 파라미터", "요청 Content-Type"]


def write_outputs(report_path: Path, result: dict[str, Any], events: list[dict[str, Any]]) -> list[Path]:
    endpoints = summarize(events)
    result["total_calls"] = len(events)
    result["endpoint_count"] = len(endpoints)
    result["endpoints"] = endpoints
    result["calls"] = sorted(events, key=lambda e: e["seq"])

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = endpoint_rows(endpoints)
    md_path = report_path.with_suffix(".md")
    clean = lambda s: s.replace("|", "/").replace("<", "").replace(">", "")  # noqa: E731  (Notion 표 깨짐 방지)
    lines = [
        "# skmr API 탐색 결과",
        "",
        f"수집 시각: {result['created_at']} / 총 호출 {len(events)}건 / 고유 엔드포인트 {len(endpoints)}개",
        "",
        "| " + " | ".join(ENDPOINT_COLUMNS) + " |",
        "| " + " | ".join(["---"] * len(ENDPOINT_COLUMNS)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(clean(f"`{c}`" if i == 1 and c else c) for i, c in enumerate(row)) + " |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    csv_path = report_path.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(ENDPOINT_COLUMNS)
        writer.writerows([[clean(c) for c in row] for row in rows])
    return [report_path, md_path, csv_path]


# ---------------------------------------------------------------- 실행

async def run(args: argparse.Namespace) -> int:
    result: dict[str, Any] = {
        "mode": "SKMR_API_DISCOVERY",
        "run_mode": args.mode,
        "username": args.username,
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    capture = Capture()
    exit_code = 0

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=args.headless)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        capture.attach(page)  # 로그인 호출까지 수집 (phase=login)
        try:
            if args.manual_login:
                await page.goto(args.url, wait_until="domcontentloaded")
                print("브라우저에서 직접 로그인한 뒤 Enter 를 누르세요.", flush=True)
                await asyncio.to_thread(input)
            else:
                password = args.password or load_password(args.accounts, args.username)
                print(f"로그인 시작: {args.username}", flush=True)
                result["login"] = await login(page, args.username, password, args.url)
                print(f"로그인 결과: {result['login']['login_response_status']} -> {result['login']['page_url']}", flush=True)

            if args.mode in ("auto", "both"):
                await run_auto(page, capture, args, result)
            if args.mode in ("manual", "both"):
                await run_manual(capture)
            result["status"] = "DONE"
        except Exception as exc:
            result["status"] = "FAILED"
            result["message"] = str(exc)
            print(f"실패: {exc}", flush=True)
            exit_code = 1
        finally:
            if args.hold_s > 0:
                print(f"{args.hold_s:.0f}초간 화면을 유지합니다...", flush=True)
                await page.wait_for_timeout(int(args.hold_s * 1000))
            await asyncio.sleep(0.5)  # 마지막 응답 처리 대기
            await context.close()
            await browser.close()

    paths = write_outputs(args.report, result, capture.events)
    print(f"\nREST API 수집: 총 호출 {result['total_calls']}건, 고유 엔드포인트 {result['endpoint_count']}개", flush=True)
    for ep in result["endpoints"]:
        print(f"  {ep['method']:<6} {ep['path_template']}  calls={ep['calls']} status={ep['statuses']} phase={ep['phases']}", flush=True)
    for path in paths:
        print(f"Report: {path}", flush=True)
    return exit_code


def main() -> int:
    configure_console_output()
    parser = argparse.ArgumentParser(description="skmr API 탐색 통합 도구 (자동 스캔 + 수동 조작 캡처)")
    parser.add_argument("--mode", choices=("both", "auto", "manual"), default="both")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--username", default="new1")
    parser.add_argument("--password", default="", help="생략하면 config/skmr_accounts.json 에서 읽음")
    parser.add_argument("--accounts", type=Path, default=DEFAULT_ACCOUNTS)
    parser.add_argument("--manual-login", action="store_true", help="로그인도 브라우저에서 직접 수행")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--screenshot-dir", type=Path, default=DEFAULT_SCREENSHOT_DIR)
    parser.add_argument("--boot-wait-s", type=float, default=20.0, help="자동 스캔 전 초기 부팅 대기(초)")
    parser.add_argument("--hold-s", type=float, default=0.0, help="종료 전 화면 유지 시간(초)")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
