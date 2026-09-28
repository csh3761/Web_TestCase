# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

import explorer_path_test as explorer
import login_session_check as login

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hynix_interface"))
from sys_trash import (  # noqa: E402
    DEFAULT_CONFIG,
    append_log_file,
    configure_console_output,
    configure_playwright_browsers_path,
    login_otcs,
    main_frame,
    snapshot_page,
    wait_for_enter_key,
)
from user_trash import read_account_from_user


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EMBEDDED_USERNAME = ""
EMBEDDED_PASSWORD = ""


def runtime_output_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / relative_path
    return PROJECT_ROOT / relative_path


DEFAULT_REPORT = runtime_output_path(r"reports\user_auto_login_report.json")
DEFAULT_LOG = runtime_output_path(r"reports\user_auto_login.log")


def write_outputs(args: argparse.Namespace, result: dict[str, Any], lines: list[str]) -> None:
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.log.exists():
        args.log.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def log_line(lines: list[str], message: str, log_path: Path | None = None) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}"
    lines.append(line)
    print(line, flush=True)
    if log_path is not None:
        append_log_file(log_path, line)


def read_account(args: argparse.Namespace) -> tuple[login.Account, str, bool]:
    if EMBEDDED_USERNAME and EMBEDDED_PASSWORD:
        return (
            login.Account(user_id=EMBEDDED_USERNAME, user_name=EMBEDDED_USERNAME, department_path=""),
            EMBEDDED_PASSWORD,
            True,
        )
    account, password = read_account_from_user(args)
    return account, password, False


async def wait_before_close(args: argparse.Namespace, lines: list[str]) -> None:
    if args.no_final_enter:
        return
    log_line(lines, "화면 확인 대기: 확인 후 Enter 입력 시 웹을 닫고 종료합니다.", args.log)
    wait_for_enter_key()
    args.final_wait_completed = True


async def run_login(args: argparse.Namespace) -> tuple[int, dict[str, Any], list[str], login.Account, str, bool]:
    configure_playwright_browsers_path()
    config = login.load_json(args.config)
    account, password, embedded = read_account(args)
    lines: list[str] = []
    result: dict[str, Any] = {
        "mode": "USER_AUTO_LOGIN",
        "user_id": account.user_id,
        "embedded": embedded,
        "status": "UNKNOWN",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=bool(config.get("headless", False)))
        context = await browser.new_context(base_url=config["site_url"], ignore_https_errors=True)
        page = await context.new_page()
        try:
            log_line(lines, f"자동 로그인 시작: {account.user_id}", args.log)
            login_result = await login_otcs(page, account, password, config)
            result.update(login_result)
            result["after_login_snapshot"] = await snapshot_page(page)
            result["main_frame_url"] = getattr(await main_frame(page), "url", "")
            result["status"] = "LOGIN_OK"
            log_line(lines, "자동 로그인 성공", args.log)
            log_line(lines, f"로그인 프레임: {result['main_frame_url']}", args.log)
            if embedded or args.login_only:
                await wait_before_close(args, lines)
            return 0, result, lines, account, password, embedded
        except Exception as exc:
            result["status"] = "FAILED"
            result["message"] = str(exc)
            try:
                result["failure_snapshot"] = await snapshot_page(page)
            except Exception:
                pass
            log_line(lines, f"자동 로그인 실패: {exc}", args.log)
            await wait_before_close(args, lines)
            return 1, result, lines, account, password, embedded
        finally:
            await context.close()
            await browser.close()


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._-") or "user"


def build_saved_source(source_path: Path, username: str, password: str) -> None:
    original = Path(__file__).read_text(encoding="utf-8")
    original = re.sub(r'^EMBEDDED_USERNAME = ".*"$', f"EMBEDDED_USERNAME = {username!r}", original, flags=re.MULTILINE)
    original = re.sub(r'^EMBEDDED_PASSWORD = ".*"$', f"EMBEDDED_PASSWORD = {password!r}", original, flags=re.MULTILINE)
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(original, encoding="utf-8")


def build_saved_exe(args: argparse.Namespace, username: str, password: str) -> Path:
    python = Path(sys.executable)
    if getattr(sys, "frozen", False):
        python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        raise FileNotFoundError(f"Python 실행 파일을 찾지 못했습니다: {python}")

    build_name = f"User_Auto_Login_{safe_name(username)}"
    generated_source = PROJECT_ROOT / "build" / "user_auto_login_saved" / f"{build_name}.py"
    dist_root = args.dist_dir or (PROJECT_ROOT / "release" / build_name)
    work_root = PROJECT_ROOT / "build" / "user_auto_login_saved" / "work" / build_name
    spec_root = PROJECT_ROOT / "build" / "user_auto_login_saved" / "spec"
    output_exe = dist_root / f"{build_name}.exe"

    build_saved_source(generated_source, username, password)
    dist_root.mkdir(parents=True, exist_ok=True)
    spec_root.mkdir(parents=True, exist_ok=True)

    playright_source = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    if not playright_source.exists():
        subprocess.run([str(python), "-m", "playwright", "install", "chromium"], check=True, cwd=PROJECT_ROOT)

    command = [
        str(python),
        "-m",
        "PyInstaller",
        "--onefile",
        "--console",
        "--name",
        build_name,
        "--distpath",
        str(dist_root),
        "--workpath",
        str(work_root),
        "--specpath",
        str(spec_root),
        "--paths",
        str(PROJECT_ROOT / "HYNIX"),
        "--paths",
        str(PROJECT_ROOT / "hynix_interface"),
        "--add-data",
        f"{playright_source};ms-playwright",
        "--add-data",
        f"{PROJECT_ROOT / 'config'};config",
        str(generated_source),
    ]
    subprocess.run(command, check=True, cwd=PROJECT_ROOT)
    if not output_exe.exists():
        raise FileNotFoundError(f"생성된 EXE를 찾지 못했습니다: {output_exe}")
    return output_exe


async def run(args: argparse.Namespace) -> int:
    exit_code, result, lines, account, password, embedded = await run_login(args)
    if exit_code != 0 or embedded or args.login_only or args.no_build:
        write_outputs(args, result, lines)
        return exit_code

    try:
        log_line(lines, "사용자 고정 자동 로그인 EXE 생성 시작", args.log)
        output_exe = build_saved_exe(args, account.user_id, password)
        result["saved_exe"] = str(output_exe)
        result["status"] = "SAVED_EXE_CREATED"
        log_line(lines, f"사용자 고정 자동 로그인 EXE 생성 완료: {output_exe}", args.log)
        await wait_before_close(args, lines)
        return 0
    except Exception as exc:
        result["status"] = "BUILD_FAILED"
        result["message"] = str(exc)
        log_line(lines, f"EXE 생성 실패: {exc}", args.log)
        await wait_before_close(args, lines)
        return 1
    finally:
        write_outputs(args, result, lines)


def main() -> int:
    explorer.configure_console()
    configure_console_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--dist-dir", type=Path, default=None)
    parser.add_argument("--login-only", action="store_true")
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--no-final-enter", action="store_true")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as exc:
        line = f"{datetime.now().isoformat(timespec='seconds')} 치명 오류: {exc}"
        print(line, flush=True)
        append_log_file(args.log, line)
        return 1
    finally:
        if getattr(sys, "frozen", False) and not args.no_final_enter and not getattr(args, "final_wait_completed", False):
            print("\n프로그램 종료 대기: 로그 확인 후 Enter를 누르세요.")
            wait_for_enter_key()


if __name__ == "__main__":
    raise SystemExit(main())
