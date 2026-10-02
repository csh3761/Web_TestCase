# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import mimetypes
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import explorer_path_test as explorer


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CSV = PROJECT_ROOT / "data" / "업로드목록.csv"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "login_config.json"
DEFAULT_PASSWORD_FILE = PROJECT_ROOT / "config" / "password.txt"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "batch_upload_report.json"
DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024


@dataclass(frozen=True)
class Account:
    user_id: str
    user_name: str
    department_path: str


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_first_accounts(csv_path: Path, limit: int) -> list[Account]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 문서를 찾을 수 없습니다: {csv_path}")

    accounts: list[Account] = []
    seen: set[str] = set()
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"성명", "사용자ID", "부서 경로"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV 필수 컬럼이 없습니다: {', '.join(sorted(missing))}")

        for row in reader:
            user_id = row["사용자ID"].strip()
            if user_id in seen:
                continue
            seen.add(user_id)
            accounts.append(
                Account(
                    user_id=user_id,
                    user_name=row["성명"].strip(),
                    department_path=row["부서 경로"].strip(),
                )
            )
            if limit > 0 and len(accounts) >= limit:
                break
    return accounts


def load_all_accounts(csv_path: Path, limit: int = 0) -> list[Account]:
    return load_first_accounts(csv_path, limit)


def get_common_password(password_file: Path | None = None) -> str:
    password = os.environ.get("DOCSPHERE_PASSWORD")
    if password:
        return password

    if password_file and password_file.exists():
        password = password_file.read_text(encoding="utf-8").strip()
        if password:
            return password

    raise RuntimeError(
        "공통 비밀번호가 없습니다. 터미널 입력은 사용하지 않습니다. "
        "DOCSPHERE_PASSWORD 환경변수 또는 --password-file 파일로 제공하세요."
    )


def normalize_department(value: str) -> str:
    return "".join(value.split())


def expected_folder_id(account: Account, config: dict[str, Any]) -> str:
    folder_map = config.get("folder_map", {})
    final_department = account.department_path.split(">")[-1].strip()
    candidates = [
        account.department_path,
        normalize_department(account.department_path),
        final_department,
        normalize_department(final_department),
    ]
    for candidate in candidates:
        if candidate in folder_map:
            return folder_map[candidate]
    return ""


async def fill_first_visible(page: Any, selector_list: str, value: str) -> None:
    selectors = [selector.strip() for selector in selector_list.split(",") if selector.strip()]
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=5000)
            await locator.fill(value)
            return
        except Exception:
            continue
    raise RuntimeError(f"입력 가능한 selector를 찾지 못했습니다: {selector_list}")


async def click_first_visible(page: Any, selector_list: str) -> None:
    selectors = [selector.strip() for selector in selector_list.split(",") if selector.strip()]
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=5000)
            await locator.click()
            return
        except Exception:
            continue
    raise RuntimeError(f"클릭 가능한 selector를 찾지 못했습니다: {selector_list}")


async def force_click(locator: Any) -> None:
    try:
        await locator.click(force=True, timeout=1500)
    except Exception:
        await locator.evaluate("(element) => element.click()")


async def check_session(
    page: Any,
    config: dict[str, Any],
    folder_id: str | None = None,
    auth_header: str = "",
) -> tuple[int, Any]:
    folder_id = folder_id or config["session_check_folder_id"]
    gubun = config.get("gubun", "D")
    query = urlencode({"folderId": folder_id, "gubun": gubun})
    api_base_url = config.get("api_base_url", config["site_url"]).rstrip("/")
    headers = {"Authorization": auth_header} if auth_header else {}
    response = await page.request.get(f"{api_base_url}/documents?{query}", headers=headers)
    try:
        payload = await response.json()
    except Exception:
        payload = await response.text()
    return response.status, payload


async def expand_first_closed_tree(page: Any, selector: str) -> str:
    chevrons = page.locator(selector)
    count = await chevrons.count()
    for index in range(count):
        chevron = chevrons.nth(index)
        expanded = await chevron.get_attribute("aria-expanded")
        if expanded == "false":
            await force_click(chevron)
            await page.wait_for_timeout(200)
            return "EXPANDED"
    return "ALREADY_OPEN_OR_NOT_FOUND"


async def expand_tree_row_if_closed(page: Any, row: Any) -> str:
    tree_item = row.locator("xpath=ancestor::li[@role='treeitem'][1]")
    chevron = row.locator("button.explorer-tree__chevron[aria-expanded]").first
    if await chevron.count() == 0:
        return "NO_CHEVRON"

    item_expanded = await tree_item.get_attribute("aria-expanded")
    chevron_expanded = await chevron.get_attribute("aria-expanded")
    if item_expanded == "true" or chevron_expanded == "true":
        return "ROOT_ALREADY_OPEN"

    if item_expanded == "false" or chevron_expanded == "false":
        await force_click(chevron)
        await page.wait_for_timeout(200)
        return "ROOT_EXPANDED"

    return "ROOT_EXPAND_STATE_UNKNOWN"


async def first_visible_locator(page: Any, selector_list: str, timeout: int = 1000) -> Any | None:
    selectors = [selector.strip() for selector in selector_list.split(",") if selector.strip()]
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=timeout)
            return locator
        except Exception:
            continue
    return None


async def first_attached_locator(page: Any, selector_list: str, timeout: int = 1000) -> Any | None:
    selectors = [selector.strip() for selector in selector_list.split(",") if selector.strip()]
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="attached", timeout=timeout)
            return locator
        except Exception:
            continue
    return None


async def is_locator_visible(locator: Any, timeout: int = 700) -> bool:
    try:
        await locator.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


async def pin_sidebar_if_possible(page: Any, config: dict[str, Any]) -> str:
    selector = config["selectors"].get("sidebar_pin", "")
    if not selector:
        return "PIN_SELECTOR_NOT_CONFIGURED"

    pin_button = await first_attached_locator(page, selector, timeout=1000)
    if not pin_button:
        return "PIN_NOT_FOUND"

    pressed = await pin_button.get_attribute("aria-pressed")
    if pressed == "false":
        await force_click(pin_button)
        await page.wait_for_timeout(120)
        return "PINNED"
    if pressed == "true":
        return "ALREADY_PINNED"
    return "PIN_STATE_UNKNOWN"


async def ensure_sidebar_ready(page: Any, config: dict[str, Any]) -> str:
    selectors = config["selectors"]
    sidebar_selector = selectors.get("sidebar_panel", "aside.explorer-sidebar")
    sidebar = page.locator(sidebar_selector).first

    events: list[str] = []
    if not await is_locator_visible(sidebar):
        # Collapsed sidebars in this UI become visible from the left rail area.
        await page.mouse.move(8, 260)
        await page.wait_for_timeout(200)
        events.append("HOVER_LEFT_RAIL")

    if not await is_locator_visible(sidebar):
        nav_selector = selectors.get("workbox_nav_department") or selectors.get("department_workbox", "")
        nav_button = await first_attached_locator(page, nav_selector, timeout=1000) if nav_selector else None
        if nav_button:
            await force_click(nav_button)
            await page.wait_for_timeout(200)
            events.append("CLICKED_WORKBOX_NAV")

    if not await is_locator_visible(sidebar):
        raise RuntimeError("사이드바 패널을 열지 못했습니다. sidebar selector 또는 접힘 해제 버튼 확인이 필요합니다.")

    events.append(await pin_sidebar_if_possible(page, config))
    return "+".join(events)


async def select_department_workbox_by_structure(page: Any, config: dict[str, Any]) -> str:
    selectors = config["selectors"]
    sidebar_status = await ensure_sidebar_ready(page, config)

    nav_selector = selectors.get("workbox_nav_department") or selectors.get("department_workbox", "")
    nav_button = await first_visible_locator(page, nav_selector, timeout=1200) if nav_selector else None
    if nav_button:
        await force_click(nav_button)
        await page.wait_for_timeout(200)
        sidebar_status = f"{sidebar_status}+WORKBOX_NAV_SELECTED"

    await ensure_sidebar_ready(page, config)
    root_row = await first_attached_locator(page, selectors["department_root_row"], timeout=1500)
    if root_row:
        expand_status = await expand_tree_row_if_closed(page, root_row)
    else:
        expand_status = await expand_first_closed_tree(page, selectors["tree_chevron"])
    return f"{sidebar_status}+{expand_status}"


async def wait_after_login(page: Any, config: dict[str, Any]) -> str:
    selectors = config["selectors"]
    login_ready_selectors = [
        selectors.get("sidebar_panel", "aside.explorer-sidebar"),
        selectors.get("workbox_nav_department", ""),
        selectors.get("department_workbox", ""),
    ]
    selector_list = ", ".join(selector for selector in login_ready_selectors if selector)
    locator = await first_attached_locator(page, selector_list, timeout=8000)
    if locator:
        return "LOGIN_UI_ATTACHED"
    raise RuntimeError("로그인 후 문서함 UI를 찾지 못했습니다.")


async def submit_login_and_wait_response(page: Any, submit_selector: str) -> tuple[str, str]:
    try:
        async with page.expect_response(
            lambda response: "/api/v1/auth/login" in response.url and response.request.method == "POST",
            timeout=8000,
        ) as response_info:
            await click_first_visible(page, submit_selector)
        response = await response_info.value
        auth_header = response.headers.get("authorization", "")
        return f"LOGIN_RESPONSE:{response.status}", auth_header
    except Exception:
        await click_first_visible(page, submit_selector)
        return "LOGIN_RESPONSE_NOT_CAPTURED", ""


async def wait_for_authenticated_session(page: Any, config: dict[str, Any], auth_header: str = "") -> str:
    last_status = 0
    for _ in range(20):
        status_code, _ = await check_session(page, config, config["session_check_folder_id"], auth_header)
        last_status = status_code
        if 200 <= status_code < 300:
            return f"AUTH_READY:{status_code}"
        await page.wait_for_timeout(200)
    raise RuntimeError(f"로그인 세션 API가 준비되지 않았습니다. last_status={last_status}")


async def wait_for_frontend_auth_settle(page: Any) -> str:
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
        return "FRONTEND_AUTH_NETWORK_IDLE"
    except Exception:
        return "FRONTEND_AUTH_NETWORK_IDLE_TIMEOUT"


async def selected_tree_key(page: Any, config: dict[str, Any]) -> str:
    selectors = config["selectors"]
    root_selector = selectors.get("department_root_row", "")
    if root_selector:
        root_row = await first_attached_locator(page, root_selector, timeout=1000)
        if root_row:
            key = await root_row.get_attribute("data-tree-key")
            if key:
                return key

    selected = page.locator(selectors["selected_tree_row"]).first
    try:
        await selected.wait_for(state="attached", timeout=1000)
        return await selected.get_attribute("data-tree-key") or ""
    except Exception:
        return ""


async def first_visible_tree_label(page: Any, names: list[str], timeout: int = 1000) -> Any | None:
    for name in names:
        if not name:
            continue
        name_locator = page.locator(".explorer-tree__name").filter(has_text=name).first
        try:
            await name_locator.wait_for(state="visible", timeout=timeout)
            button = name_locator.locator("xpath=ancestor::button[contains(@class, 'explorer-tree__label')][1]")
            try:
                await button.wait_for(state="visible", timeout=500)
                return button
            except Exception:
                return name_locator
        except Exception:
            try:
                await name_locator.wait_for(state="attached", timeout=500)
                button = name_locator.locator("xpath=ancestor::button[contains(@class, 'explorer-tree__label')][1]")
                return button
            except Exception:
                continue
    return None


def upload_target_names(account: Account) -> list[str]:
    final_department = account.department_path.split(">")[-1].strip()
    compact_department = "".join(final_department.split())
    return [
        "01. 기본 폴더",
        "01. 기본폴더",
        final_department,
        compact_department,
    ]


def folder_label_candidates(name: str) -> list[str]:
    compact = normalize_department(name)
    candidates = [name.strip(), compact]
    if name.strip() == "01. 기본 폴더":
        candidates.append("01. 기본폴더")
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def csv_department_parts(account: Account) -> list[str]:
    return [part.strip() for part in account.department_path.split(">") if part.strip()]


def upload_subfolder_paths(account: Account, config: dict[str, Any]) -> list[list[str]]:
    parts = csv_department_parts(account)
    final_department = parts[-1] if parts else ""
    leaf_folder = str(config.get("default_leaf_folder", "01. 기본 폴더")).strip()
    paths: list[list[str]] = []
    if final_department:
        paths.append([final_department, leaf_folder])
        paths.append([normalize_department(final_department), leaf_folder])

    # The web tree can expose either the final department only or a deeper suffix
    # of the CSV department path. Build candidates from the CSV instead of fixing
    # a specific "department1 > department2" depth.
    for start in range(max(1, len(parts) - 3), len(parts)):
        suffix = parts[start:]
        if suffix:
            paths.append([*suffix, leaf_folder])

    unique_paths: list[list[str]] = []
    seen: set[str] = set()
    for path in paths:
        key = "\x1f".join(path)
        if key not in seen:
            seen.add(key)
            unique_paths.append(path)
    return unique_paths


def upload_subfolder_path(account: Account, config: dict[str, Any]) -> list[str]:
    paths = upload_subfolder_paths(account, config)
    return paths[0] if paths else []


async def tree_row_for_label(label: Any) -> Any:
    return label.locator("xpath=ancestor::*[contains(@class, 'explorer-tree__row')][1]")


async def tree_key_for_row(row: Any) -> str:
    return await row.get_attribute("data-tree-key") or ""


async def click_tree_folder_by_name(page: Any, names: list[str]) -> tuple[str, str]:
    label = await first_visible_tree_label(page, names, timeout=900)
    if not label:
        debug_names = await page.locator(".explorer-tree__name").evaluate_all(
            "(nodes) => nodes.map((node) => node.textContent?.trim()).filter(Boolean)"
        )
        raise RuntimeError(f"하위 문서함 태그를 찾지 못했습니다. 대상 후보={names}, 현재 트리 이름={debug_names}")

    await force_click(label)
    await page.wait_for_timeout(150)
    row = await tree_row_for_label(label)
    tree_key = await tree_key_for_row(row)
    expand_status = await expand_tree_row_if_closed(page, row)
    return tree_key, expand_status


async def navigate_upload_subfolders(page: Any, config: dict[str, Any], account: Account) -> dict[str, Any]:
    path_errors: list[dict[str, Any]] = []
    for subfolder_path in upload_subfolder_paths(account, config):
        events: list[str] = []
        tree_key = ""
        try:
            for folder_name in subfolder_path:
                candidates = folder_label_candidates(folder_name)
                tree_key, expand_status = await click_tree_folder_by_name(page, candidates)
                events.append(f"{folder_name}:{expand_status}")

            return {
                "upload_path_source": "CSV_DEPARTMENT_PATH",
                "upload_subfolder_path": " > ".join(subfolder_path),
                "upload_subfolder_status": "+".join(events),
                "upload_tree_key": tree_key,
                "upload_path_attempts": len(path_errors) + 1,
            }
        except Exception as exc:
            path_errors.append(
                {
                    "path": " > ".join(subfolder_path),
                    "events": events,
                    "message": str(exc),
                }
            )

    raise RuntimeError(f"CSV 기준 업로드 경로를 웹 트리에서 찾지 못했습니다. attempts={path_errors}")


async def reveal_upload_folder(page: Any, config: dict[str, Any], account: Account) -> tuple[Any, str]:
    selectors = config["selectors"]
    expand_events: list[str] = []
    target_names = upload_target_names(account)
    for _ in range(6):
        target_folder = await first_visible_tree_label(page, target_names, timeout=1200)
        if target_folder:
            return target_folder, "+".join(expand_events) if expand_events else "TARGET_VISIBLE"

        default_folder = await first_visible_locator(page, selectors["default_folder"], timeout=500)
        if default_folder:
            return default_folder, "+".join(expand_events) if expand_events else "DEFAULT_VISIBLE"

        expand_events.append(await expand_first_closed_tree(page, selectors["tree_chevron"]))
        await page.wait_for_timeout(500)

    debug_names = await page.locator(".explorer-tree__name").evaluate_all(
        "(nodes) => nodes.map((node) => node.textContent?.trim()).filter(Boolean)"
    )
    raise RuntimeError(f"업로드 대상 폴더를 찾지 못했습니다. 대상 후보={target_names}, 현재 트리 이름={debug_names}")


async def move_to_default_folder(page: Any, config: dict[str, Any], account: Account) -> dict[str, str]:
    selectors = config["selectors"]
    expand_status = await select_department_workbox_by_structure(page, config)
    upload_navigation = await navigate_upload_subfolders(page, config, account)
    tree_key = await selected_tree_key(page, config)
    if upload_navigation.get("upload_tree_key"):
        tree_key = str(upload_navigation["upload_tree_key"])
    if not tree_key:
        row_debug = await page.locator(".explorer-tree__row").evaluate_all(
            """(rows) => rows.map((row) => ({
                text: row.textContent?.trim(),
                key: row.getAttribute('data-tree-key')
            })).filter((row) => row.text || row.key)"""
        )
        raise RuntimeError(f"선택된 폴더의 data-tree-key를 찾지 못했습니다. row_debug={row_debug}")

    parts = tree_key.split("\x1f")
    folder_id = next((part for part in reversed(parts) if part.startswith("DOCBOXM_")), "")
    expected_id = expected_folder_id(account, config)
    folder_id_source = "data-tree-key"
    if expected_id and (not folder_id or folder_id == "DOCBOXM_000000000001"):
        folder_id = expected_id
        folder_id_source = "folder_map"
    if not folder_id:
        raise RuntimeError(f"data-tree-key에서 folderId를 추출하지 못했습니다: {tree_key}")

    return {
        "navigation_status": "UPLOAD_SUBFOLDER_PATH_SELECTED",
        "expand_status": expand_status,
        "tree_key": tree_key,
        "selected_folder_id": folder_id,
        "selected_folder_id_source": folder_id_source,
        "upload_subfolder_path": str(upload_navigation["upload_subfolder_path"]),
        "upload_subfolder_status": str(upload_navigation["upload_subfolder_status"]),
    }


async def logout(page: Any, config: dict[str, Any]) -> str:
    selectors = config.get("selectors", {})
    kebab_selector = selectors.get("kebab_menu", "")
    settings_selector = selectors.get("settings_menu_item", "")
    logout_selector = selectors.get("logout", "")
    if not logout_selector:
        return "SKIPPED_NO_SELECTOR"
    try:
        direct_logout = await first_visible_locator(page, logout_selector, timeout=500)
        if direct_logout:
            await force_click(direct_logout)
            await page.wait_for_timeout(300)
            return "LOGGED_OUT_DIRECT"

        if kebab_selector:
            await click_first_visible(page, kebab_selector)
            await page.wait_for_timeout(150)

        if settings_selector:
            await click_first_visible(page, settings_selector)
            await page.wait_for_timeout(200)

        await click_first_visible(page, logout_selector)
        await page.wait_for_timeout(500)
        return "LOGGED_OUT"
    except Exception as exc:
        return f"LOGOUT_NOT_CONFIRMED: {exc}"


async def login_one(playwright: Any, account: Account, password: str, config: dict[str, Any]) -> dict[str, Any]:
    browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
    context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
    page = await context.new_page()
    captured_auth_header = ""

    def capture_auth_header(request: Any) -> None:
        nonlocal captured_auth_header
        auth_header = request.headers.get("authorization", "")
        if "/api/v1/" in request.url and auth_header:
            captured_auth_header = auth_header

    page.on("request", capture_auth_header)
    result: dict[str, Any] = {
        "user_id": account.user_id,
        "user_name": account.user_name,
        "department_path": account.department_path,
        "status": "UNKNOWN",
    }

    try:
        selectors = config["selectors"]
        await page.goto(config["login_url"], wait_until="domcontentloaded")
        await fill_first_visible(page, selectors["username"], account.user_id)
        await fill_first_visible(page, selectors["password"], password)
        login_submit_status, auth_header = await submit_login_and_wait_response(page, selectors["submit"])
        result["login_submit_status"] = login_submit_status
        result["login_wait_status"] = await wait_after_login(page, config)
        if not auth_header and not captured_auth_header:
            result["frontend_auth_wait_status"] = await wait_for_frontend_auth_settle(page)
        else:
            result["frontend_auth_wait_status"] = "SKIPPED_AUTH_HEADER_ALREADY_CAPTURED"
        auth_header = auth_header or captured_auth_header
        result["auth_header_status"] = "CAPTURED" if auth_header else "NOT_FOUND"
        result["auth_wait_status"] = await wait_for_authenticated_session(page, config, auth_header)

        navigation = await move_to_default_folder(page, config, account)
        result.update(navigation)
        status_code, payload = await check_session(page, config, navigation["selected_folder_id"], auth_header)
        result["session_check_status"] = status_code
        result["session_check_payload_type"] = type(payload).__name__
        result["status"] = "SESSION_AND_NAVIGATION_OK" if 200 <= status_code < 300 else "NAVIGATION_OK_SESSION_INVALID"
        result["logout"] = await logout(page, config)
    except Exception as exc:
        result["status"] = "FAILED"
        result["message"] = str(exc)
    finally:
        await context.close()
        await browser.close()
    return result


def collect_document_names(payload: Any) -> set[str]:
    names: set[str] = set()
    name_keys = {
        "fileName",
        "filename",
        "name",
        "documentName",
        "title",
        "originalFileName",
        "contentTitle",
    }

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in name_keys and isinstance(item, str):
                    names.add(item)
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return names


async def api_json(
    page: Any,
    method: str,
    url: str,
    auth_header: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    headers = {"Authorization": auth_header, "Content-Type": "application/json"}
    data = json.dumps(payload, ensure_ascii=False) if payload is not None else None
    response = await page.request.fetch(url, method=method, headers=headers, data=data)
    try:
        body = await response.json()
    except Exception:
        body = await response.text()
    return response.status, body


async def create_upload(
    page: Any,
    config: dict[str, Any],
    auth_header: str,
    folder_id: str,
    file_path: Path,
) -> dict[str, Any]:
    api_base_url = config.get("api_base_url", config["site_url"]).rstrip("/")
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    status, body = await api_json(
        page,
        "POST",
        f"{api_base_url}/document-uploads",
        auth_header,
        {
            "folderId": folder_id,
            "fileName": file_path.name,
            "fileSize": file_path.stat().st_size,
            "mimeType": mime_type,
        },
    )
    if not 200 <= status < 300 or not isinstance(body, dict) or not body.get("uploadId"):
        raise RuntimeError(f"upload create failed: status={status}, body={body}")
    return body


async def upload_chunks(
    page: Any,
    config: dict[str, Any],
    auth_header: str,
    upload_id: str,
    file_path: Path,
    chunk_size: int,
) -> list[dict[str, Any]]:
    api_base_url = config.get("api_base_url", config["site_url"]).rstrip("/")
    headers = {"Authorization": auth_header, "Content-Type": "application/octet-stream"}
    chunk_results: list[dict[str, Any]] = []

    with file_path.open("rb") as handle:
        chunk_index = 0
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            response = await page.request.put(
                f"{api_base_url}/document-uploads/{upload_id}/chunks/{chunk_index}",
                headers=headers,
                data=chunk,
            )
            chunk_results.append({"index": chunk_index, "status": response.status, "size": len(chunk)})
            if not 200 <= response.status < 300:
                text = await response.text()
                raise RuntimeError(
                    f"chunk upload failed: file={file_path.name}, index={chunk_index}, "
                    f"status={response.status}, body={text}"
                )
            chunk_index += 1
    return chunk_results


async def complete_upload(page: Any, config: dict[str, Any], auth_header: str, upload_id: str) -> tuple[int, Any]:
    api_base_url = config.get("api_base_url", config["site_url"]).rstrip("/")
    return await api_json(page, "POST", f"{api_base_url}/document-uploads/{upload_id}/complete", auth_header)


async def upload_file(
    page: Any,
    config: dict[str, Any],
    auth_header: str,
    folder_id: str,
    file_path: Path,
    chunk_size: int,
) -> dict[str, Any]:
    upload = await create_upload(page, config, auth_header, folder_id, file_path)
    upload_id = upload["uploadId"]
    chunk_results = await upload_chunks(page, config, auth_header, upload_id, file_path, chunk_size)
    complete_status, complete_body = await complete_upload(page, config, auth_header, upload_id)
    if not 200 <= complete_status < 300:
        raise RuntimeError(f"upload complete failed: file={file_path.name}, status={complete_status}, body={complete_body}")
    return {
        "file": file_path.name,
        "upload_id": upload_id,
        "file_size": file_path.stat().st_size,
        "chunk_count": len(chunk_results),
        "chunks": chunk_results,
        "complete_status": complete_status,
        "complete_body": complete_body,
    }


async def wait_for_uploaded_files(
    page: Any,
    config: dict[str, Any],
    auth_header: str,
    folder_id: str,
    expected_files: list[str],
    timeout_ms: int,
    interval_ms: int,
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000)
    expected = set(expected_files)
    last_status = 0
    last_names: set[str] = set()
    attempts = 0

    while asyncio.get_running_loop().time() < deadline:
        attempts += 1
        status_code, payload = await check_session(page, config, folder_id, auth_header)
        last_status = status_code
        last_names = collect_document_names(payload)
        verified = sorted(expected & last_names)
        if expected and len(verified) == len(expected):
            return {
                "status": "UPLOAD_VISIBLE_IN_DOCUMENT_LIST",
                "attempts": attempts,
                "last_status": last_status,
                "verified_files": verified,
                "missing_files": [],
                "document_names_sample": sorted(last_names)[:10],
            }
        await page.wait_for_timeout(interval_ms)

    return {
        "status": "UPLOAD_VISIBILITY_TIMEOUT",
        "attempts": attempts,
        "last_status": last_status,
        "verified_files": sorted(expected & last_names),
        "missing_files": sorted(expected - last_names),
        "document_names_sample": sorted(last_names)[:10],
    }


def safe_status(status: str) -> bool:
    return status in {"DRY_RUN_READY", "NO_UPLOAD_TARGETS", "UPLOAD_COMPLETED"}


def explorer_report_path(base_report: Path, user_id: str) -> Path:
    return base_report.parent / f"{base_report.stem}_{user_id}{base_report.suffix}"


def stage_timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def add_stage_log(result: dict[str, Any], stage: str, status: str, message: str = "", **extra: Any) -> None:
    result.setdefault("stage_log", []).append(
        {
            "time": stage_timestamp(),
            "stage": stage,
            "status": status,
            "message": message,
            **extra,
        }
    )
    result["last_stage"] = stage
    result["last_stage_status"] = status


async def wait_server_result(coro: Any, timeout_ms: int, stage: str) -> Any:
    try:
        return await asyncio.wait_for(coro, timeout=timeout_ms / 1000)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"SERVER_DELAY_TIMEOUT stage={stage} timeout_ms={timeout_ms}") from exc


def build_local_file_report(csv_path: Path, root: Path, user_id: str, max_files: int) -> dict[str, Any]:
    documents = explorer.load_user_documents(csv_path, user_id)
    account_doc = documents[0]
    folder = explorer.resolve_user_folder(root, account_doc)
    if not folder.exists():
        raise FileNotFoundError(f"user folder not found: {folder}")

    expected_names = explorer.expected_file_names(documents)
    all_files = explorer.folder_files(folder)
    selected_files = all_files if max_files <= 0 else all_files[:max_files]
    return {
        "mode": "DIRECT_FILESYSTEM_SCAN",
        "user_id": account_doc.user_id,
        "user_name": account_doc.user_name,
        "department_path": account_doc.department_path,
        "resolved_folder": str(folder),
        "folder_exists": folder.exists(),
        "csv_expected_file_count": len(expected_names),
        "folder_file_count": len(all_files),
        "missing_files": [name for name in expected_names if not (folder / name).exists()],
        "all_files": [path.name for path in all_files],
        "selected_count": len(selected_files),
        "selected_files": [path.name for path in selected_files],
    }


async def upload_one_account(playwright: Any, account: Account, password: str, config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
    context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
    page = await context.new_page()
    captured_auth_header = ""

    def capture_auth_header(request: Any) -> None:
        nonlocal captured_auth_header
        auth_header = request.headers.get("authorization", "")
        if "/api/v1/" in request.url and auth_header:
            captured_auth_header = auth_header

    page.on("request", capture_auth_header)
    result: dict[str, Any] = {
        "user_id": account.user_id,
        "user_name": account.user_name,
        "department_path": account.department_path,
        "upload_source_policy": "ALL_FILES_IN_ID_FOLDER",
        "execute": args.execute,
        "status": "UNKNOWN",
        "stage_log": [],
        "uploaded_completed_files": [],
    }

    try:
        selectors = config["selectors"]
        add_stage_log(result, "LOGIN_PAGE_GOTO", "START", config["login_url"])
        await wait_server_result(page.goto(config["login_url"], wait_until="domcontentloaded"), args.server_timeout_ms, "LOGIN_PAGE_GOTO")
        add_stage_log(result, "LOGIN_PAGE_GOTO", "DONE")

        add_stage_log(result, "LOGIN_INPUT", "START")
        await wait_server_result(fill_first_visible(page, selectors["username"], account.user_id), args.server_timeout_ms, "LOGIN_INPUT_USERNAME")
        await wait_server_result(fill_first_visible(page, selectors["password"], password), args.server_timeout_ms, "LOGIN_INPUT_PASSWORD")
        add_stage_log(result, "LOGIN_INPUT", "DONE")

        add_stage_log(result, "LOGIN_SUBMIT", "START")
        login_submit_status, auth_header = await wait_server_result(
            submit_login_and_wait_response(page, selectors["submit"]),
            args.server_timeout_ms,
            "LOGIN_SUBMIT",
        )
        add_stage_log(result, "LOGIN_SUBMIT", "DONE", login_submit_status)
        result["login_submit_status"] = login_submit_status

        add_stage_log(result, "LOGIN_UI_WAIT", "START")
        result["login_wait_status"] = await wait_server_result(wait_after_login(page, config), args.server_timeout_ms, "LOGIN_UI_WAIT")
        add_stage_log(result, "LOGIN_UI_WAIT", "DONE", result["login_wait_status"])

        if not auth_header and not captured_auth_header:
            add_stage_log(result, "FRONTEND_AUTH_SETTLE", "START")
            result["frontend_auth_wait_status"] = await wait_server_result(
                wait_for_frontend_auth_settle(page),
                args.server_timeout_ms,
                "FRONTEND_AUTH_SETTLE",
            )
            add_stage_log(result, "FRONTEND_AUTH_SETTLE", "DONE", result["frontend_auth_wait_status"])
        else:
            result["frontend_auth_wait_status"] = "SKIPPED_AUTH_HEADER_ALREADY_CAPTURED"
            add_stage_log(result, "FRONTEND_AUTH_SETTLE", "SKIPPED", result["frontend_auth_wait_status"])

        auth_header = auth_header or captured_auth_header
        result["auth_header_status"] = "CAPTURED" if auth_header else "NOT_FOUND"
        add_stage_log(result, "AUTH_SESSION_CHECK", "START")
        result["auth_wait_status"] = await wait_server_result(
            wait_for_authenticated_session(page, config, auth_header),
            args.server_timeout_ms,
            "AUTH_SESSION_CHECK",
        )
        add_stage_log(result, "AUTH_SESSION_CHECK", "DONE", result["auth_wait_status"])

        add_stage_log(result, "WEB_FOLDER_NAVIGATION", "START")
        navigation = await wait_server_result(move_to_default_folder(page, config, account), args.server_timeout_ms, "WEB_FOLDER_NAVIGATION")
        result.update(navigation)
        add_stage_log(
            result,
            "WEB_FOLDER_NAVIGATION",
            "DONE",
            folder_id=navigation.get("selected_folder_id"),
            upload_subfolder_path=navigation.get("upload_subfolder_path"),
        )

        add_stage_log(result, "LOCAL_FILE_SCAN", "START")
        per_user_explorer_report = explorer_report_path(args.explorer_report, account.user_id)
        local_report = build_local_file_report(args.csv, args.root, account.user_id, args.max_files)
        per_user_explorer_report.parent.mkdir(parents=True, exist_ok=True)
        per_user_explorer_report.write_text(json.dumps(local_report, ensure_ascii=False, indent=2), encoding="utf-8")
        result["explorer_report"] = str(per_user_explorer_report)
        result["explorer"] = local_report
        add_stage_log(
            result,
            "LOCAL_FILE_SCAN",
            "DONE",
            selected_count=local_report.get("selected_count"),
            folder_file_count=local_report.get("folder_file_count"),
            resolved_folder=local_report.get("resolved_folder"),
        )

        selected_files = [Path(local_report["resolved_folder"]) / name for name in local_report["selected_files"]]
        result["selected_local_files"] = [str(path) for path in selected_files]
        result["selected_local_file_count"] = len(selected_files)

        add_stage_log(result, "DOCUMENT_LIST_BEFORE_UPLOAD", "START")
        status_code, payload = await wait_server_result(
            check_session(page, config, navigation["selected_folder_id"], auth_header),
            args.server_timeout_ms,
            "DOCUMENT_LIST_BEFORE_UPLOAD",
        )
        existing_names = collect_document_names(payload)
        duplicate_files = [path.name for path in selected_files if path.name in existing_names]
        upload_targets = [path for path in selected_files if path.name not in existing_names]

        result["document_list_status"] = status_code
        result["document_list_type"] = type(payload).__name__
        result["existing_document_name_count"] = len(existing_names)
        result["existing_document_names_sample"] = sorted(existing_names)[:10]
        result["duplicate_files"] = duplicate_files
        result["upload_plan"] = [path.name for path in upload_targets]
        add_stage_log(
            result,
            "DOCUMENT_LIST_BEFORE_UPLOAD",
            "DONE",
            http_status=status_code,
            existing_count=len(existing_names),
            upload_plan_count=len(upload_targets),
            duplicate_count=len(duplicate_files),
        )

        if duplicate_files and args.fail_on_duplicates:
            result["status"] = "BLOCKED_DUPLICATE_FILES"
            add_stage_log(result, "UPLOAD_DECISION", "BLOCKED_DUPLICATE_FILES", duplicate_count=len(duplicate_files))
        elif not args.execute:
            result["status"] = "DRY_RUN_READY"
            add_stage_log(result, "UPLOAD_DECISION", "DRY_RUN_READY", upload_plan_count=len(upload_targets))
        elif not upload_targets:
            result["uploaded"] = []
            result["upload_visibility"] = {
                "status": "SKIPPED_NO_NEW_FILES",
                "verified_files": [],
                "missing_files": [],
            }
            result["status"] = "NO_UPLOAD_TARGETS"
            add_stage_log(result, "UPLOAD_DECISION", "NO_UPLOAD_TARGETS")
        else:
            uploaded = []
            for file_path in upload_targets:
                add_stage_log(result, "UPLOAD_FILE", "START", file=file_path.name, size=file_path.stat().st_size)
                uploaded_item = await wait_server_result(
                    upload_file(
                        page,
                        config,
                        auth_header,
                        navigation["selected_folder_id"],
                        file_path,
                        args.chunk_size,
                    ),
                    args.server_timeout_ms,
                    f"UPLOAD_FILE:{file_path.name}",
                )
                uploaded.append(uploaded_item)
                result["uploaded_completed_files"].append(file_path.name)
                add_stage_log(
                    result,
                    "UPLOAD_FILE",
                    "DONE",
                    file=file_path.name,
                    uploaded_completed_count=len(result["uploaded_completed_files"]),
                )
            result["uploaded"] = uploaded
            add_stage_log(result, "UPLOAD_VISIBILITY_VERIFY", "START", expected_count=len(uploaded))
            visibility = await wait_server_result(
                wait_for_uploaded_files(
                    page,
                    config,
                    auth_header,
                    navigation["selected_folder_id"],
                    [item["file"] for item in uploaded],
                    args.verify_timeout_ms,
                    args.verify_interval_ms,
                ),
                args.server_timeout_ms + args.verify_timeout_ms,
                "UPLOAD_VISIBILITY_VERIFY",
            )
            result["upload_visibility"] = visibility
            result["verified_uploaded_files"] = visibility["verified_files"]
            result["status"] = "UPLOAD_COMPLETED" if visibility["status"] == "UPLOAD_VISIBLE_IN_DOCUMENT_LIST" else "UPLOAD_VERIFY_INCOMPLETE"
            add_stage_log(
                result,
                "UPLOAD_VISIBILITY_VERIFY",
                "DONE",
                visibility_status=visibility.get("status"),
                verified_count=len(visibility.get("verified_files", [])),
                missing_count=len(visibility.get("missing_files", [])),
            )

        if args.logout_on_success and safe_status(result["status"]):
            add_stage_log(result, "LOGOUT", "START")
            result["logout"] = await logout(page, config)
            add_stage_log(result, "LOGOUT", "DONE", result["logout"])
        elif args.logout_on_success:
            result["logout"] = "SKIPPED_UPLOAD_NOT_VERIFIED"
            add_stage_log(result, "LOGOUT", "SKIPPED_UPLOAD_NOT_VERIFIED", current_status=result["status"])
        else:
            result["logout"] = "SKIPPED_BY_OPTION"
            add_stage_log(result, "LOGOUT", "SKIPPED_BY_OPTION")
    except TimeoutError as exc:
        result["status"] = "SERVER_DELAY_TIMEOUT"
        result["message"] = str(exc)
        result["failure_stage"] = result.get("last_stage", "UNKNOWN")
        result["failure_stage_status"] = "SERVER_DELAY_TIMEOUT"
        add_stage_log(result, str(result.get("last_stage", "UNKNOWN")), "SERVER_DELAY_TIMEOUT", str(exc))
    except Exception as exc:
        result["status"] = "FAILED"
        result["message"] = str(exc)
        result["failure_stage"] = result.get("last_stage", "UNKNOWN")
        result["failure_stage_status"] = "FAILED"
        add_stage_log(result, str(result.get("last_stage", "UNKNOWN")), "FAILED", str(exc))
    finally:
        add_stage_log(result, "BROWSER_CONTEXT_CLOSE", "START")
        await context.close()
        await browser.close()
        add_stage_log(result, "BROWSER_CONTEXT_CLOSE", "DONE")
    return result


async def run(args: argparse.Namespace) -> int:
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright가 설치되어 있지 않습니다. "
            f"{PROJECT_ROOT.parent}\\.venv\\Scripts\\python.exe -m pip install playwright 후 "
            f"{PROJECT_ROOT.parent}\\.venv\\Scripts\\python.exe -m playwright install chromium 을 실행하세요."
        ) from exc

    config = load_json(args.config)
    accounts = load_all_accounts(args.csv, args.limit)
    password = get_common_password(args.password_file)

    results: list[dict[str, Any]] = []
    async with async_playwright() as playwright:
        for account in accounts:
            result = await upload_one_account(playwright, account, password, config, args)
            results.append(result)
            print(
                json.dumps(
                    {
                        "user_id": result.get("user_id"),
                        "user_name": result.get("user_name"),
                        "status": result.get("status"),
                        "selected_local_file_count": result.get("selected_local_file_count"),
                        "upload_plan_count": len(result.get("upload_plan", [])),
                        "uploaded_count": len(result.get("uploaded", [])),
                        "uploaded_completed_count": len(result.get("uploaded_completed_files", [])),
                        "last_stage": result.get("last_stage"),
                        "last_stage_status": result.get("last_stage_status"),
                        "logout": result.get("logout"),
                    },
                    ensure_ascii=False,
                )
            )

    completed_statuses = {"DRY_RUN_READY", "NO_UPLOAD_TARGETS", "UPLOAD_COMPLETED"}
    completed_ids = [item["user_id"] for item in results if item.get("status") in completed_statuses]
    failed_ids = [item["user_id"] for item in results if item.get("status") not in completed_statuses]
    report = {
        "mode": "BATCH_UPLOAD_MAIN",
        "execute": args.execute,
        "logout_on_success": args.logout_on_success,
        "total_users": len(accounts),
        "completed_count": len(completed_ids),
        "failed_count": len(failed_ids),
        "completed_ids": completed_ids,
        "failed_ids": failed_ids,
        "results": results,
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Report: {args.report}")
    return 0 if not failed_ids else 1


def main() -> int:
    explorer.configure_console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--explorer-report", type=Path, default=PROJECT_ROOT / "reports" / "batch_explorer_report.json")
    parser.add_argument("--root", type=Path, default=explorer.DEFAULT_ROOT)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--verify-timeout-ms", type=int, default=45000)
    parser.add_argument("--verify-interval-ms", type=int, default=1000)
    parser.add_argument("--server-timeout-ms", type=int, default=90000)
    parser.add_argument("--explorer-timeout", type=float, default=10.0)
    parser.add_argument("--password-file", type=Path, default=DEFAULT_PASSWORD_FILE)
    parser.add_argument("--fail-on-duplicates", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--logout-on-success", action="store_true")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
