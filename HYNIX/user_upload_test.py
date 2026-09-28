# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
from pathlib import Path
from typing import Any

import explorer_path_test as explorer
import login_session_check as login


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REPORT = PROJECT_ROOT / "reports" / "user_upload_test.json"
DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024


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


async def api_json(page: Any, method: str, url: str, auth_header: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
    headers = {"Authorization": auth_header, "Content-Type": "application/json"}
    data = json.dumps(payload, ensure_ascii=False) if payload is not None else None
    response = await page.request.fetch(url, method=method, headers=headers, data=data)
    try:
        body = await response.json()
    except Exception:
        body = await response.text()
    return response.status, body


async def create_upload(page: Any, config: dict[str, Any], auth_header: str, folder_id: str, file_path: Path) -> dict[str, Any]:
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
        raise RuntimeError(f"업로드 생성 실패: status={status}, body={body}")
    return body


async def upload_chunks(page: Any, config: dict[str, Any], auth_header: str, upload_id: str, file_path: Path, chunk_size: int) -> list[dict[str, Any]]:
    api_base_url = config.get("api_base_url", config["site_url"]).rstrip("/")
    chunk_results: list[dict[str, Any]] = []
    headers = {"Authorization": auth_header, "Content-Type": "application/octet-stream"}

    with file_path.open("rb") as handle:
        index = 0
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            response = await page.request.put(
                f"{api_base_url}/document-uploads/{upload_id}/chunks/{index}",
                headers=headers,
                data=chunk,
            )
            chunk_results.append({"index": index, "status": response.status, "size": len(chunk)})
            if not 200 <= response.status < 300:
                text = await response.text()
                raise RuntimeError(f"chunk 업로드 실패: file={file_path.name}, index={index}, status={response.status}, body={text}")
            index += 1
    return chunk_results


async def complete_upload(page: Any, config: dict[str, Any], auth_header: str, upload_id: str) -> tuple[int, Any]:
    api_base_url = config.get("api_base_url", config["site_url"]).rstrip("/")
    return await api_json(page, "POST", f"{api_base_url}/document-uploads/{upload_id}/complete", auth_header)


async def upload_file(page: Any, config: dict[str, Any], auth_header: str, folder_id: str, file_path: Path, chunk_size: int) -> dict[str, Any]:
    upload = await create_upload(page, config, auth_header, folder_id, file_path)
    upload_id = upload["uploadId"]
    chunk_results = await upload_chunks(page, config, auth_header, upload_id, file_path, chunk_size)
    complete_status, complete_body = await complete_upload(page, config, auth_header, upload_id)
    if not 200 <= complete_status < 300:
        raise RuntimeError(f"업로드 완료 실패: file={file_path.name}, status={complete_status}, body={complete_body}")
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
        status_code, payload = await login.check_session(page, config, folder_id, auth_header)
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


async def run(args: argparse.Namespace) -> int:
    from playwright.async_api import async_playwright

    config = login.load_json(args.config)
    documents = explorer.load_user_documents(args.csv, args.user_id)
    account_doc = documents[0]
    account = login.Account(account_doc.user_id, account_doc.user_name, account_doc.department_path)
    password = login.get_common_password(args.password_file)

    async with async_playwright() as playwright:
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
        }

        try:
            selectors = config["selectors"]
            await page.goto(config["login_url"], wait_until="domcontentloaded")
            await login.fill_first_visible(page, selectors["username"], account.user_id)
            await login.fill_first_visible(page, selectors["password"], password)
            login_submit_status, auth_header = await login.submit_login_and_wait_response(page, selectors["submit"])
            result["login_submit_status"] = login_submit_status
            result["login_wait_status"] = await login.wait_after_login(page, config)

            if not auth_header and not captured_auth_header:
                result["frontend_auth_wait_status"] = await login.wait_for_frontend_auth_settle(page)
            else:
                result["frontend_auth_wait_status"] = "SKIPPED_AUTH_HEADER_ALREADY_CAPTURED"

            auth_header = auth_header or captured_auth_header
            result["auth_header_status"] = "CAPTURED" if auth_header else "NOT_FOUND"
            result["auth_wait_status"] = await login.wait_for_authenticated_session(page, config, auth_header)

            navigation = await login.move_to_default_folder(page, config, account)
            result.update(navigation)

            explorer_args = argparse.Namespace(
                csv=args.csv,
                root=args.root,
                report=args.explorer_report,
                user_id=args.user_id,
                timeout=args.explorer_timeout,
                max_select=args.max_files,
            )
            explorer_report = explorer.build_report(explorer_args)
            args.explorer_report.parent.mkdir(parents=True, exist_ok=True)
            args.explorer_report.write_text(json.dumps(explorer_report, ensure_ascii=False, indent=2), encoding="utf-8")
            result["explorer"] = explorer_report

            selected_files = [Path(explorer_report["resolved_folder"]) / name for name in explorer_report["selected_files"]]
            result["selected_local_files"] = [str(path) for path in selected_files]
            result["selected_local_file_count"] = len(selected_files)

            status_code, payload = await login.check_session(page, config, navigation["selected_folder_id"], auth_header)
            existing_names = collect_document_names(payload)
            duplicate_files = [path.name for path in selected_files if path.name in existing_names]
            upload_targets = [path for path in selected_files if path.name not in existing_names]

            result["document_list_status"] = status_code
            result["document_list_type"] = type(payload).__name__
            result["document_list_item_count"] = len(payload) if isinstance(payload, list) else None
            result["existing_document_name_count"] = len(existing_names)
            result["existing_document_names_sample"] = sorted(existing_names)[:10]
            result["duplicate_files"] = duplicate_files
            result["upload_plan"] = [path.name for path in upload_targets]

            if duplicate_files and not args.skip_duplicates:
                result["status"] = "BLOCKED_DUPLICATE_FILES"
            elif not args.execute:
                result["status"] = "DRY_RUN_READY"
            elif not upload_targets:
                result["uploaded"] = []
                result["verify_status"] = status_code
                result["verified_uploaded_files"] = []
                result["status"] = "NO_UPLOAD_TARGETS"
            else:
                uploaded = []
                for file_path in upload_targets:
                    uploaded.append(
                        await upload_file(
                            page,
                            config,
                            auth_header,
                            navigation["selected_folder_id"],
                            file_path,
                            args.chunk_size,
                        )
                    )
                result["uploaded"] = uploaded
                visibility = await wait_for_uploaded_files(
                    page,
                    config,
                    auth_header,
                    navigation["selected_folder_id"],
                    [item["file"] for item in uploaded],
                    args.verify_timeout_ms,
                    args.verify_interval_ms,
                )
                result["upload_visibility"] = visibility
                result["verify_status"] = visibility["last_status"]
                result["verified_uploaded_files"] = visibility["verified_files"]
                result["status"] = "UPLOAD_COMPLETED" if visibility["status"] == "UPLOAD_VISIBLE_IN_DOCUMENT_LIST" else "UPLOAD_VERIFY_INCOMPLETE"

            safe_to_logout = result["status"] in {"DRY_RUN_READY", "NO_UPLOAD_TARGETS", "UPLOAD_COMPLETED"}
            if args.logout and safe_to_logout:
                result["logout"] = await login.logout(page, config)
            elif args.logout:
                result["logout"] = "SKIPPED_UPLOAD_NOT_VERIFIED"
            else:
                result["logout"] = "SKIPPED_FOR_UPLOAD_TEST"
        except Exception as exc:
            result["status"] = "FAILED"
            result["message"] = str(exc)
        finally:
            await context.close()
            await browser.close()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Report: {args.report}")
    return 0 if result["status"] in {"DRY_RUN_READY", "UPLOAD_COMPLETED", "NO_UPLOAD_TARGETS"} else 1


def main() -> int:
    explorer.configure_console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=login.DEFAULT_CSV)
    parser.add_argument("--config", type=Path, default=login.DEFAULT_CONFIG)
    parser.add_argument("--password-file", type=Path, default=login.DEFAULT_PASSWORD_FILE)
    parser.add_argument("--root", type=Path, default=explorer.DEFAULT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--explorer-report", type=Path, default=PROJECT_ROOT / "reports" / "user_upload_test_explorer.json")
    parser.add_argument("--user-id", default="INF93284")
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--verify-timeout-ms", type=int, default=30000)
    parser.add_argument("--verify-interval-ms", type=int, default=1000)
    parser.add_argument("--explorer-timeout", type=float, default=10.0)
    parser.add_argument("--skip-duplicates", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--logout", action="store_true")
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
