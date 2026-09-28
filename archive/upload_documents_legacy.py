from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import re
import ssl
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPSHandler


DEFAULT_CONFIG = Path(r"C:\Dummy\config\upload_config.json")
DEFAULT_COOKIES = Path(r"C:\Dummy\config\cookies.json")
REPORT_CSV = Path(r"C:\Dummy\reports\upload_report.csv")
REPORT_JSON = Path(r"C:\Dummy\reports\upload_report.json")


@dataclass(frozen=True)
class LocalFile:
    no: str
    user_name: str
    user_id: str
    department_path: str
    department: str
    folder_id: str
    path: Path


class ApiClient:
    def __init__(self, base_url: str, cookies: dict[str, str], insecure: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items() if v)
        handlers = []
        if insecure:
            context = ssl._create_unverified_context()
            handlers.append(HTTPSHandler(context=context))
        self.opener = build_opener(*handlers)

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        data: bytes | None = None,
        content_type: str | None = None,
    ) -> tuple[int, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {
            "Accept": "application/json",
            "Origin": "https://react01.ifns.devel:1443",
            "Referer": "https://react01.ifns.devel:1443/",
        }
        if self.cookie_header:
            headers["Cookie"] = self.cookie_header
        body = data
        if json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif content_type:
            headers["Content-Type"] = content_type
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=60) as response:
                raw = response.read()
                if not raw:
                    return response.status, None
                text = raw.decode("utf-8", errors="replace")
                try:
                    return response.status, json.loads(text)
                except json.JSONDecodeError:
                    return response.status, text
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} {method} {url}: {raw}") from exc
        except URLError as exc:
            raise RuntimeError(f"Network error {method} {url}: {exc}") from exc


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_department(value: str) -> str:
    return "".join(value.split())


def load_folder_map(config: dict[str, Any]) -> dict[str, str]:
    raw = config.get("folder_map", {})
    folder_map: dict[str, str] = {}
    for name, folder_id in raw.items():
        folder_map[name] = folder_id
        folder_map[normalize_department(name)] = folder_id
    return folder_map


def sanitize_filename(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*]', "_", value.strip())
    value = re.sub(r"\s+", " ", value)
    return value.rstrip(". ")


def read_upload_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def find_user_files(config: dict[str, Any]) -> tuple[list[LocalFile], list[str]]:
    org_root = Path(config["org_root"])
    csv_path = Path(config["csv_path"])
    folder_map = load_folder_map(config)
    if not org_root.exists():
        raise FileNotFoundError(f"Organization root not found: {org_root}")

    items: list[LocalFile] = []
    missing_departments: set[str] = set()
    missing_files: list[str] = []
    for row in read_upload_rows(csv_path):
        department_path = row["부서 경로"].strip()
        department_parts = [part.strip() for part in department_path.split(">")]
        department = department_parts[-1]
        user_id = row["사용자ID"].strip()
        file_name = f"{sanitize_filename(row['문서명'])}.{row['확장자'].strip().lower()}"
        file_path = org_root.joinpath(*department_parts, user_id, file_name)
        folder_id = (
            folder_map.get(department_path)
            or folder_map.get(normalize_department(department_path))
            or folder_map.get(department)
            or folder_map.get(normalize_department(department))
        )
        if not folder_id:
            missing_departments.add(department_path)
            continue
        if not file_path.exists():
            missing_files.append(str(file_path))
            continue
        items.append(
            LocalFile(
                no=row["No."],
                user_name=row["성명"],
                user_id=user_id,
                department_path=department_path,
                department=department,
                folder_id=folder_id,
                path=file_path,
            )
        )
    return items, sorted(missing_departments) + [f"FILE_NOT_FOUND: {path}" for path in missing_files]


def extract_remote_names(value: Any, keys: set[str]) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys and isinstance(item, str):
                names.add(item)
            else:
                names.update(extract_remote_names(item, keys))
    elif isinstance(value, list):
        for item in value:
            names.update(extract_remote_names(item, keys))
    return names


def list_remote_names(client: ApiClient, config: dict[str, Any], folder_id: str) -> set[str]:
    status, payload = client.request(
        "GET",
        "/documents",
        query={"folderId": folder_id, "gubun": config.get("gubun", "D")},
    )
    if status < 200 or status >= 300:
        raise RuntimeError(f"Unexpected documents status: {status}")
    return extract_remote_names(payload, set(config.get("remote_name_keys", [])))


def init_upload(client: ApiClient, folder_id: str, file_path: Path) -> dict[str, Any]:
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    payload = {
        "folderId": folder_id,
        "fileName": file_path.name,
        "fileSize": file_path.stat().st_size,
        "mimeType": mime_type,
    }
    status, response = client.request("POST", "/document-uploads", json_body=payload)
    if status not in {200, 201}:
        raise RuntimeError(f"Unexpected upload init status: {status}")
    if not isinstance(response, dict) or "uploadId" not in response:
        raise RuntimeError(f"Upload init response has no uploadId: {response}")
    return response


def put_chunks(client: ApiClient, upload: dict[str, Any], file_path: Path) -> None:
    upload_id = upload["uploadId"]
    chunk_size = int(upload["chunkSize"])
    total_chunks = int(upload["totalChunks"])
    with file_path.open("rb") as handle:
        for index in range(total_chunks):
            chunk = handle.read(chunk_size)
            status, _ = client.request(
                "PUT",
                f"/document-uploads/{upload_id}/chunks/{index}",
                data=chunk,
                content_type="application/octet-stream",
            )
            if status < 200 or status >= 300:
                raise RuntimeError(f"Unexpected chunk status for {file_path.name}: {status}")


def complete_upload(client: ApiClient, upload_id: str) -> dict[str, Any]:
    status, response = client.request("POST", f"/document-uploads/{upload_id}/complete")
    if status not in {200, 201}:
        raise RuntimeError(f"Unexpected complete status: {status}")
    if not isinstance(response, dict) or "contentCode" not in response:
        raise RuntimeError(f"Complete response has no contentCode: {response}")
    return response


def upload_one(client: ApiClient, item: LocalFile) -> dict[str, Any]:
    upload = init_upload(client, item.folder_id, item.path)
    put_chunks(client, upload, item.path)
    complete = complete_upload(client, upload["uploadId"])
    return {
        "uploadId": upload["uploadId"],
        "contentCode": complete.get("contentCode", ""),
        "revisionCode": complete.get("revisionCode", ""),
    }


def write_reports(rows: list[dict[str, Any]]) -> None:
    REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "status",
        "no",
        "user_name",
        "user_id",
        "department_path",
        "department",
        "folder_id",
        "file_name",
        "size",
        "contentCode",
        "revisionCode",
        "message",
    ]
    with REPORT_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    REPORT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--cookies", type=Path, default=DEFAULT_COOKIES)
    parser.add_argument("--execute", action="store_true", help="Actually upload files. Default is dry-run.")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification for internal dev certs.")
    parser.add_argument("--only-id", help="Upload only one user ID folder, for example INF76713.")
    parser.add_argument("--limit", type=int, help="Limit number of local files processed.")
    args = parser.parse_args()

    config = load_json(args.config)
    cookies = load_json(args.cookies) if args.cookies.exists() else {}
    items, missing_departments = find_user_files(config)
    if args.only_id:
        items = [item for item in items if item.user_id == args.only_id]
    if args.limit:
        items = items[: args.limit]

    rows: list[dict[str, Any]] = []
    if missing_departments:
        for department in missing_departments:
            if department.startswith("FILE_NOT_FOUND: "):
                rows.append({
                    "status": "FILE_NOT_FOUND",
                    "file_name": department.removeprefix("FILE_NOT_FOUND: "),
                    "message": "CSV 기준 로컬 파일을 찾지 못했습니다.",
                })
                continue
            rows.append({
                "status": "MISSING_FOLDER_MAP",
                "department": department,
                "message": "upload_config.json에 부서 folderId 매핑이 필요합니다.",
            })

    if not args.execute:
        for item in items:
            rows.append({
                "status": "DRY_RUN",
                "no": item.no,
                "user_name": item.user_name,
                "user_id": item.user_id,
                "department_path": item.department_path,
                "department": item.department,
                "folder_id": item.folder_id,
                "file_name": item.path.name,
                "size": item.path.stat().st_size,
                "message": "No upload. Use --execute to upload.",
            })
        write_reports(rows)
        print(f"Dry-run files: {len(items)}")
        print(f"Missing folder maps: {len(missing_departments)}")
        print(f"Report: {REPORT_CSV}")
        return 0 if not missing_departments else 2

    if not cookies:
        raise FileNotFoundError(f"Cookie file is required for --execute: {args.cookies}")

    client = ApiClient(config["base_url"], cookies, insecure=args.insecure)
    remote_cache: dict[str, set[str]] = {}
    for index, item in enumerate(items, start=1):
        try:
            if config.get("skip_existing_remote", True):
                if item.folder_id not in remote_cache:
                    remote_cache[item.folder_id] = list_remote_names(client, config, item.folder_id)
                if item.path.name in remote_cache[item.folder_id]:
                    rows.append({
                        "status": "SKIPPED_EXISTS",
                        "no": item.no,
                        "user_name": item.user_name,
                        "user_id": item.user_id,
                        "department_path": item.department_path,
                        "department": item.department,
                        "folder_id": item.folder_id,
                        "file_name": item.path.name,
                        "size": item.path.stat().st_size,
                        "message": "Remote file name already exists.",
                    })
                    continue
            result = upload_one(client, item)
            remote_cache.setdefault(item.folder_id, set()).add(item.path.name)
            rows.append({
                "status": "UPLOADED",
                "no": item.no,
                "user_name": item.user_name,
                "user_id": item.user_id,
                "department_path": item.department_path,
                "department": item.department,
                "folder_id": item.folder_id,
                "file_name": item.path.name,
                "size": item.path.stat().st_size,
                "contentCode": result["contentCode"],
                "revisionCode": result["revisionCode"],
                "message": "ok",
            })
            time.sleep(0.05)
        except Exception as exc:
            rows.append({
                "status": "FAILED",
                "no": item.no,
                "user_name": item.user_name,
                "user_id": item.user_id,
                "department_path": item.department_path,
                "department": item.department,
                "folder_id": item.folder_id,
                "file_name": item.path.name,
                "size": item.path.stat().st_size if item.path.exists() else "",
                "message": str(exc),
            })
        if index % 25 == 0 or index == len(items):
            print(f"Processed {index}/{len(items)}")

    write_reports(rows)
    failed = sum(1 for row in rows if row.get("status") == "FAILED")
    print(f"Processed files: {len(items)}")
    print(f"Failed: {failed}")
    print(f"Report: {REPORT_CSV}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
