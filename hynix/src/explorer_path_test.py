# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CSV = PROJECT_ROOT / "data" / "업로드목록.csv"
DEFAULT_ROOT = PROJECT_ROOT
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "explorer_path_test.json"

SVSI_SELECT = 0x1
SVSI_DESELECTOTHERS = 0x4
SVSI_ENSUREVISIBLE = 0x8
SVSI_FOCUSED = 0x10


@dataclass(frozen=True)
class UserDocument:
    user_id: str
    user_name: str
    department_path: str
    document_name: str
    extension: str


def configure_console() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def load_user_documents(csv_path: Path, user_id: str) -> list[UserDocument]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 문서를 찾을 수 없습니다: {csv_path}")

    documents: list[UserDocument] = []
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"부서 경로", "성명", "사용자ID", "문서명", "확장자"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV 필수 컬럼이 없습니다: {', '.join(sorted(missing))}")

        for row in reader:
            if row["사용자ID"].strip() != user_id:
                continue
            documents.append(
                UserDocument(
                    user_id=row["사용자ID"].strip(),
                    user_name=row["성명"].strip(),
                    department_path=row["부서 경로"].strip(),
                    document_name=row["문서명"].strip(),
                    extension=row["확장자"].strip().lstrip("."),
                )
            )
    if not documents:
        raise ValueError(f"CSV에서 사용자ID를 찾지 못했습니다: {user_id}")
    return documents


def department_parts(department_path: str) -> list[str]:
    return [part.strip() for part in department_path.split(">") if part.strip()]


def resolve_user_folder(root: Path, document: UserDocument) -> Path:
    parts = department_parts(document.department_path)
    if not parts:
        raise ValueError(f"부서 경로가 비어 있습니다: {document.department_path}")
    return root.joinpath(*parts, document.user_id)


def expected_file_names(documents: list[UserDocument]) -> list[str]:
    return [f"{doc.document_name}.{doc.extension}" for doc in documents]


def existing_files(folder: Path, file_names: list[str]) -> list[Path]:
    return [folder / file_name for file_name in file_names if (folder / file_name).exists()]


def folder_files(folder: Path) -> list[Path]:
    return sorted((path for path in folder.iterdir() if path.is_file()), key=lambda path: path.name.casefold())


def path_from_location_url(location_url: str) -> str:
    parsed = urlparse(location_url)
    if parsed.scheme.lower() != "file":
        return ""
    path = unquote(parsed.path)
    if path.startswith("/") and len(path) >= 3 and path[2] == ":":
        path = path[1:]
    return path.replace("/", "\\")


def folder_matches(left: Path, right: str) -> bool:
    try:
        return left.resolve().samefile(Path(right))
    except Exception:
        return str(left).casefold().rstrip("\\") == right.casefold().rstrip("\\")


def shell_windows(shell: Any) -> list[Any]:
    return [shell.Windows().Item(index) for index in range(shell.Windows().Count)]


def find_explorer_window(shell: Any, folder: Path) -> Any | None:
    for window in shell_windows(shell):
        try:
            if folder_matches(folder, path_from_location_url(window.LocationURL)):
                return window
        except Exception:
            continue
    return None


def open_explorer_and_wait(shell: Any, folder: Path, timeout: float) -> tuple[Any, bool]:
    before_hwnds = {
        int(window.HWND)
        for window in shell_windows(shell)
        if getattr(window, "HWND", 0)
    }
    shell.Open(str(folder))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        window = find_explorer_window(shell, folder)
        if window:
            hwnd = int(window.HWND)
            return window, hwnd not in before_hwnds
        time.sleep(0.2)
    raise TimeoutError(f"Explorer navigation 완료를 기다리다 실패했습니다: {folder}")


def activate_window(hwnd: int) -> str:
    import win32con
    import win32gui

    if not hwnd:
        return "NO_HWND"
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    try:
        win32gui.SetForegroundWindow(hwnd)
        return "FOCUSED"
    except Exception as first_exc:
        try:
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            return f"FOCUSED_WITH_FALLBACK:{first_exc}"
        except Exception as second_exc:
            return f"FOCUS_NOT_CONFIRMED:{first_exc}; fallback={second_exc}"


def select_files_in_explorer(window: Any, files: list[Path]) -> dict[str, Any]:
    selected: list[str] = []
    folder_view = window.Document
    folder = folder_view.Folder

    for index, file_path in enumerate(files):
        item = folder.ParseName(file_path.name)
        if item is None:
            continue
        flags = SVSI_SELECT | SVSI_ENSUREVISIBLE
        if index == 0:
            flags |= SVSI_DESELECTOTHERS | SVSI_FOCUSED
        folder_view.SelectItem(item, flags)
        selected.append(file_path.name)

    return {
        "selected_count": len(selected),
        "selected_files": selected,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        import pythoncom
        import win32com.client
    except ModuleNotFoundError as exc:
        raise RuntimeError("pywin32가 필요합니다. `.venv`에서 `python -m pip install pywin32`를 실행하세요.") from exc

    pythoncom.CoInitialize()
    try:
        documents = load_user_documents(args.csv, args.user_id)
        account = documents[0]
        folder = resolve_user_folder(args.root, account)
        if not folder.exists():
            raise FileNotFoundError(f"사용자 폴더가 없습니다: {folder}")

        file_names = expected_file_names(documents)
        csv_matched_files = existing_files(folder, file_names)
        all_files = folder_files(folder)
        select_targets = all_files if args.max_select <= 0 else all_files[: args.max_select]

        shell = win32com.client.Dispatch("Shell.Application")
        window, new_window_detected = open_explorer_and_wait(shell, folder, args.timeout)
        hwnd = int(window.HWND)
        focus_status = activate_window(hwnd)
        selected = select_files_in_explorer(window, select_targets)

        return {
            "user_id": account.user_id,
            "user_name": account.user_name,
            "department_path": account.department_path,
            "resolved_folder": str(folder),
            "folder_exists": folder.exists(),
            "csv_expected_file_count": len(file_names),
            "csv_matched_file_count": len(csv_matched_files),
            "folder_file_count": len(all_files),
            "missing_files": [name for name in file_names if not (folder / name).exists()],
            "hwnd": hwnd,
            "new_window_detected": new_window_detected,
            "focus_status": focus_status,
            "explorer_location_url": window.LocationURL,
            "explorer_path": path_from_location_url(window.LocationURL),
            "all_files": [path.name for path in all_files],
            **selected,
        }
    finally:
        pythoncom.CoUninitialize()


def main() -> int:
    configure_console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--user-id", default="INF93284")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--max-select", type=int, default=0)
    args = parser.parse_args()

    report = build_report(args)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Report: {args.report}")
    return 0 if report["folder_exists"] and report["selected_count"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
