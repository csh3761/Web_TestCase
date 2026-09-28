# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path
from typing import Any

import explorer_path_test as explorer
import login_session_check as login
import user_upload_test


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REPORT = PROJECT_ROOT / "reports" / "main_test_user3.json"


def pick_unique_department_users(csv_path: Path, limit: int) -> list[dict[str, str]]:
    picked: list[dict[str, str]] = []
    seen_departments: set[str] = set()

    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"부서 경로", "성명", "사용자ID"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV 필수 컬럼이 없습니다: {', '.join(sorted(missing))}")

        for row in reader:
            department_path = row["부서 경로"].strip()
            if department_path in seen_departments:
                continue
            seen_departments.add(department_path)
            picked.append(
                {
                    "user_id": row["사용자ID"].strip(),
                    "user_name": row["성명"].strip(),
                    "department_path": department_path,
                }
            )
            if len(picked) >= limit:
                break

    if len(picked) < limit:
        raise ValueError(f"중복되지 않는 부서 기준 사용자 {limit}명을 찾지 못했습니다. found={len(picked)}")
    return picked


def summarize_user_result(result: dict[str, Any]) -> dict[str, Any]:
    uploaded = result.get("uploaded") or []
    return {
        "user_id": result.get("user_id"),
        "user_name": result.get("user_name"),
        "department_path": result.get("department_path"),
        "status": result.get("status"),
        "selected_folder_id": result.get("selected_folder_id"),
        "selected_local_file_count": result.get("selected_local_file_count"),
        "upload_plan_count": len(result.get("upload_plan") or []),
        "uploaded_count": len(uploaded),
        "verified_count": len(result.get("verified_uploaded_files") or []),
        "duplicate_count": len(result.get("duplicate_files") or []),
        "logout": result.get("logout"),
    }


async def run(args: argparse.Namespace) -> int:
    users = pick_unique_department_users(args.csv, args.limit)
    batch_results: list[dict[str, Any]] = []

    for index, user in enumerate(users, start=1):
        user_report = args.report.parent / f"main_test_user3_{index}_{user['user_id']}.json"
        explorer_report = args.report.parent / f"main_test_user3_{index}_{user['user_id']}_explorer.json"
        user_args = argparse.Namespace(
            csv=args.csv,
            config=args.config,
            password_file=args.password_file,
            root=args.root,
            report=user_report,
            explorer_report=explorer_report,
            user_id=user["user_id"],
            max_files=args.max_files,
            chunk_size=args.chunk_size,
            verify_timeout_ms=args.verify_timeout_ms,
            verify_interval_ms=args.verify_interval_ms,
            explorer_timeout=args.explorer_timeout,
            skip_duplicates=True,
            execute=True,
            logout=True,
        )
        exit_code = await user_upload_test.run(user_args)
        result = json.loads(user_report.read_text(encoding="utf-8"))
        result["batch_index"] = index
        result["batch_exit_code"] = exit_code
        result["user_report"] = str(user_report)
        result["explorer_report"] = str(explorer_report)
        batch_results.append(result)

    summary = {
        "mode": "MAIN_TEST_USER3",
        "limit": args.limit,
        "user_selection_policy": "FIRST_USER_PER_UNIQUE_DEPARTMENT",
        "execute": True,
        "logout": True,
        "completed_ids": [
            result["user_id"]
            for result in batch_results
            if result.get("status") in {"UPLOAD_COMPLETED", "NO_UPLOAD_TARGETS"}
        ],
        "failed_ids": [
            result["user_id"]
            for result in batch_results
            if result.get("status") not in {"UPLOAD_COMPLETED", "NO_UPLOAD_TARGETS"}
        ],
        "results": [summarize_user_result(result) for result in batch_results],
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Report: {args.report}")
    return 0 if not summary["failed_ids"] else 1


def main() -> int:
    explorer.configure_console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=login.DEFAULT_CSV)
    parser.add_argument("--config", type=Path, default=login.DEFAULT_CONFIG)
    parser.add_argument("--password-file", type=Path, default=login.DEFAULT_PASSWORD_FILE)
    parser.add_argument("--root", type=Path, default=explorer.DEFAULT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--chunk-size", type=int, default=user_upload_test.DEFAULT_CHUNK_SIZE)
    parser.add_argument("--verify-timeout-ms", type=int, default=45000)
    parser.add_argument("--verify-interval-ms", type=int, default=1000)
    parser.add_argument("--explorer-timeout", type=float, default=10.0)
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
