# -*- coding: utf-8 -*-
"""skmr 청크 업로드 API 동시 접근 테스트 (다중 계정 병렬 업로드).

사용하는 API
  POST   /api/v1/document-uploads                      청크 업로드 세션 생성
  PUT    /api/v1/document-uploads/{uploadId}/chunks/{i} 청크 업로드
  GET    /api/v1/document-uploads/{uploadId}           진행 상태 조회
  POST   /api/v1/document-uploads/{uploadId}/complete  청크 조립 및 문서 등록
  DELETE /api/v1/document-uploads/{uploadId}           업로드 취소 (실패 시 세션 정리용)

병렬 구조
  - 계정마다 독립된 브라우저 컨텍스트로 로그인 -> barrier에서 대기 -> 동시에 업로드 시작
  - 계정 안에서는 --file-concurrency 개 파일, 파일 안에서는 --chunk-concurrency 개 청크를 동시에 전송

안전장치
  - 기본은 dry-run(계획만 출력). 실제 업로드는 --execute 일 때만 수행한다.
  - 업로드 파일명에 실행 식별 접두사(ct<시각>_<계정>_)를 붙여, 테스트 문서를 구분/정리하기 쉽게 한다.
  - 실패한 업로드 세션은 DELETE로 best-effort 정리한다.

사용 예
  python skmr/concurrent_upload_test.py                                  # 계획만 출력
  python skmr/concurrent_upload_test.py --discover                       # 폴더 ID 확인 (읽기 전용)
  python skmr/concurrent_upload_test.py --execute --folder-id fld_xxx --files-per-user 3
"""
from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, async_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://skmr.ifns.work/"
DEFAULT_ACCOUNTS = PROJECT_ROOT / "config" / "skmr_accounts.json"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "skmr_concurrent_upload.json"
DEFAULT_SOURCE = Path.home() / "Downloads"

USERNAME_SELECTOR = "input[type='text']"
PASSWORD_SELECTOR = "input[type='password']"
SUBMIT_SELECTOR = "button[type='submit'].login-form__submit"

API_PREFIX = "/api/v1"
DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024
DEFAULT_EXTENSIONS = "pdf,docx,doc,xlsx,xls,pptx,ppt,txt,csv,md,jpg,jpeg,png,gif,hwp,hwpx"
DEFAULT_MAX_FILE_MB = 20
NAME_KEYS = ("fileName", "documentName", "name", "title", "contentName", "originalFileName", "orgFileName")


def configure_console_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(line_buffering=True, write_through=True)
        except Exception:
            pass


def log(tag: str, message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] [{tag}] {message}", flush=True)


def ms_since(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def short(value: Any, limit: int = 300) -> Any:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return text if len(text) <= limit else text[:limit] + "...(truncated)"


# ---------------------------------------------------------------- 계획(파일 선정/분배)

def parse_folder_map(raw: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        user, _, folder = pair.partition("=")
        mapping[user.strip()] = folder.strip()
    return mapping


def collect_candidates(source: Path, extensions: set[str], max_bytes: int) -> list[Path]:
    if not source.is_dir():
        raise FileNotFoundError(f"업로드 소스 폴더가 없습니다: {source}")
    files = [
        p for p in source.iterdir()
        if p.is_file() and p.suffix.lower().lstrip(".") in extensions and 0 < p.stat().st_size <= max_bytes
    ]
    return sorted(files, key=lambda p: p.name.lower())


def build_plan(usernames: list[str], candidates: list[Path], per_user: int, mode: str) -> dict[str, list[Path]]:
    plan: dict[str, list[Path]] = {}
    for index, username in enumerate(usernames):
        if mode == "same":
            chosen = candidates[:per_user]
        else:
            chosen = candidates[index * per_user:(index + 1) * per_user]
        plan[username] = chosen
    return plan


def upload_name(path: Path, username: str, prefix: str, keep_names: bool) -> str:
    return path.name if keep_names else f"{prefix}{username}_{path.name}"


# ---------------------------------------------------------------- 세션/로그인

class UserSession:
    def __init__(self, username: str, password: str, context: BrowserContext, page: Page) -> None:
        self.username = username
        self.password = password
        self.context = context
        self.page = page
        self.auth_header = ""

    def watch_auth(self) -> None:
        def on_request(request: Any) -> None:
            header = request.headers.get("authorization", "")
            if API_PREFIX in request.url and header:
                self.auth_header = header  # 토큰 갱신을 따라가도록 항상 최신값 유지

        self.page.on("request", on_request)


def load_accounts(path: Path, limit: int, only: str) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"계정 설정 파일이 없습니다: {path} (config/skmr_accounts.example.json 참고)")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    accounts = [{"username": str(a["username"]), "password": str(a["password"])} for a in data["accounts"]]
    if only:
        wanted = [u.strip() for u in only.split(",") if u.strip()]
        accounts = [a for a in accounts if a["username"] in wanted]
    return accounts[:limit] if limit > 0 else accounts


async def login(browser: Browser, account: dict[str, str], url: str) -> UserSession:
    context = await browser.new_context(ignore_https_errors=True)
    page = await context.new_page()
    session = UserSession(account["username"], account["password"], context, page)
    session.watch_auth()
    await page.goto(url, wait_until="domcontentloaded")
    await page.locator(USERNAME_SELECTOR).first.fill(account["username"])
    await page.locator(PASSWORD_SELECTOR).first.fill(account["password"])
    async with page.expect_response(
        lambda r: r.request.method == "POST" and r.url.split("?", 1)[0].endswith("/auth/login"), timeout=15000
    ) as info:
        await page.locator(SUBMIT_SELECTOR).first.click()
    response = await info.value
    if response.status != 200:
        raise RuntimeError(f"로그인 실패: status={response.status}")
    for _ in range(100):  # 로그인 후 앱이 보내는 API 요청에서 인증 헤더 확보 (최대 10초)
        if session.auth_header:
            break
        await page.wait_for_timeout(100)
    log(session.username, f"로그인 완료 (auth_header={'있음' if session.auth_header else '없음(쿠키 인증 추정)'})")
    return session


# ---------------------------------------------------------------- API 호출

async def api(
    session: UserSession,
    base_url: str,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    data: bytes | None = None,
    content_type: str = "",
    query: dict[str, Any] | None = None,
) -> tuple[int, Any, int]:
    """(status, body, elapsed_ms). 401이면 최신 인증 헤더로 1회 재시도한다."""
    url = f"{base_url}{API_PREFIX}{path}"
    if query:
        url += "?" + "&".join(f"{k}={v}" for k, v in query.items())
    for attempt in (1, 2):
        headers: dict[str, str] = {}
        if session.auth_header:
            headers["Authorization"] = session.auth_header
        payload: Any = None
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(json_body, ensure_ascii=False)
        elif data is not None:
            headers["Content-Type"] = content_type or "application/octet-stream"
            payload = data
        start = time.perf_counter()
        response = await session.context.request.fetch(url, method=method, headers=headers, data=payload)
        elapsed = ms_since(start)
        if response.status == 401 and attempt == 1:
            await session.page.wait_for_timeout(1500)  # 앱이 토큰을 갱신할 시간을 준다
            continue
        try:
            body: Any = await response.json()
        except Exception:
            body = (await response.text())[:500]
        return response.status, body, elapsed
    raise AssertionError("unreachable")


# ---------------------------------------------------------------- 단일 파일 업로드

async def read_chunk(path: Path, index: int, chunk_size: int) -> bytes:
    def _read() -> bytes:
        with path.open("rb") as handle:
            handle.seek(index * chunk_size)
            return handle.read(chunk_size)

    return await asyncio.to_thread(_read)


async def upload_file(
    session: UserSession, base_url: str, folder_id: str, path: Path, name: str, args: argparse.Namespace
) -> dict[str, Any]:
    tag = session.username
    size = path.stat().st_size
    result: dict[str, Any] = {"source": path.name, "upload_name": name, "size": size, "ok": False}
    started = time.perf_counter()
    upload_id = ""
    try:
        create_body = {
            "folderId": folder_id,
            "fileName": name,
            "fileSize": size,
            "mimeType": mimetypes.guess_type(name)[0] or "application/octet-stream",
        }
        status, body, elapsed = await api(session, base_url, "POST", "/document-uploads", json_body=create_body)
        result["create"] = {"status": status, "ms": elapsed, "body": short(body)}
        if not 200 <= status < 300 or not isinstance(body, dict) or not body.get("uploadId"):
            raise RuntimeError(f"세션 생성 실패: status={status} body={short(body)}")
        upload_id = str(body["uploadId"])
        result["upload_id"] = upload_id

        chunk_size = args.chunk_size or int(body.get("chunkSize") or 0) or DEFAULT_CHUNK_SIZE
        chunk_count = max(1, -(-size // chunk_size))
        result["chunk_size"] = chunk_size
        result["chunk_count"] = chunk_count
        log(tag, f"{name}: 세션 생성 {elapsed}ms, chunk {chunk_count}개 x {chunk_size}B")

        semaphore = asyncio.Semaphore(args.chunk_concurrency)
        chunk_results: list[dict[str, Any]] = [{} for _ in range(chunk_count)]

        async def send(index: int) -> None:
            async with semaphore:
                chunk = await read_chunk(path, index, chunk_size)
                c_status, c_body, c_ms = await api(
                    session, base_url, "PUT", f"/document-uploads/{upload_id}/chunks/{index}", data=chunk
                )
                chunk_results[index] = {"index": index, "status": c_status, "ms": c_ms, "size": len(chunk)}
                if not 200 <= c_status < 300:
                    raise RuntimeError(f"chunk {index} 실패: status={c_status} body={short(c_body)}")

        await asyncio.gather(*(send(i) for i in range(chunk_count)))
        result["chunks"] = chunk_results

        s_status, s_body, s_ms = await api(session, base_url, "GET", f"/document-uploads/{upload_id}")
        result["progress"] = {"status": s_status, "ms": s_ms, "body": short(s_body)}

        c_status, c_body, c_ms = await api(session, base_url, "POST", f"/document-uploads/{upload_id}/complete")
        result["complete"] = {"status": c_status, "ms": c_ms, "body": short(c_body)}
        if not 200 <= c_status < 300:
            raise RuntimeError(f"complete 실패: status={c_status} body={short(c_body)}")

        result["ok"] = True
        result["total_ms"] = ms_since(started)
        log(tag, f"{name}: 완료 {result['total_ms']}ms (complete {c_ms}ms)")
    except Exception as exc:
        result["error"] = str(exc)
        result["total_ms"] = ms_since(started)
        log(tag, f"{name}: 실패 - {exc}")
        if upload_id:
            try:
                d_status, d_body, _ = await api(session, base_url, "DELETE", f"/document-uploads/{upload_id}")
                result["cancel"] = {"status": d_status, "body": short(d_body)}
            except Exception as cancel_exc:
                result["cancel"] = {"error": str(cancel_exc)}
    return result


# ---------------------------------------------------------------- 검증

def collect_names(value: Any, out: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in NAME_KEYS and isinstance(item, str):
                out.add(item)
            collect_names(item, out)
    elif isinstance(value, list):
        for item in value:
            collect_names(item, out)


async def verify_visible(
    session: UserSession, base_url: str, folder_id: str, expected: list[str], timeout_s: float
) -> dict[str, Any]:
    deadline = time.perf_counter() + timeout_s
    missing = set(expected)
    attempts, last_status = 0, 0
    while time.perf_counter() < deadline:
        attempts += 1
        status, body, _ = await api(
            session, base_url, "GET", "/documents", query={"boxId": folder_id, "page": 1, "size": 100}
        )
        last_status = status
        names: set[str] = set()
        collect_names(body, names)
        missing = set(expected) - names
        if not missing:
            break
        await asyncio.sleep(1)
    return {
        "verified": len(expected) - len(missing),
        "expected": len(expected),
        "missing": sorted(missing),
        "attempts": attempts,
        "last_status": last_status,
    }


# ---------------------------------------------------------------- 사용자 단위 실행

async def check_identity(session: UserSession, base_url: str) -> dict[str, Any]:
    """/auth/me 가 본인 계정을 돌려주는지 확인한다 (세션 섞임 감지)."""
    status, body, _ = await api(session, base_url, "GET", "/auth/me")
    actual = body.get("username") if isinstance(body, dict) else None
    return {"status": status, "username": actual, "ok": status == 200 and actual == session.username}


async def run_user(
    session: UserSession,
    base_url: str,
    folder_id: str,
    files: list[Path],
    prefix: str,
    barrier: asyncio.Barrier,
    args: argparse.Namespace,
) -> dict[str, Any]:
    out: dict[str, Any] = {"username": session.username, "folder_id": folder_id, "files": []}
    await barrier.wait()
    started = time.perf_counter()
    out["_start"] = started
    out["identity_before"] = await check_identity(session, base_url)
    semaphore = asyncio.Semaphore(args.file_concurrency)

    async def one(path: Path) -> dict[str, Any]:
        async with semaphore:
            return await upload_file(
                session, base_url, folder_id, path, upload_name(path, session.username, prefix, args.keep_names), args
            )

    out["files"] = await asyncio.gather(*(one(p) for p in files))
    out["upload_wall_ms"] = ms_since(started)
    out["identity_after"] = await check_identity(session, base_url)
    if not (out["identity_before"]["ok"] and out["identity_after"]["ok"]):
        log(session.username, f"세션 본인 확인 실패: {out['identity_before']} / {out['identity_after']}")
    ok_names = [f["upload_name"] for f in out["files"] if f["ok"]]
    if ok_names and not args.no_verify:
        out["verify"] = await verify_visible(session, base_url, folder_id, ok_names, args.verify_timeout)
        log(session.username, f"목록 검증: {out['verify']['verified']}/{out['verify']['expected']}")
    return out


def summarize(users: list[dict[str, Any]]) -> dict[str, Any]:
    files = [f for u in users for f in u["files"]]
    ok = [f for f in files if f["ok"]]
    complete_ms = [f["complete"]["ms"] for f in ok if "complete" in f]
    create_ms = [f["create"]["ms"] for f in files if "create" in f]
    starts = [u["_start"] for u in users if "_start" in u]
    upload_ids = [f["upload_id"] for f in files if "upload_id" in f]
    return {
        "users": len(users),
        "files_total": len(files),
        "files_ok": len(ok),
        "files_failed": len(files) - len(ok),
        "bytes_ok": sum(f["size"] for f in ok),
        "start_skew_ms": round((max(starts) - min(starts)) * 1000, 1) if starts else None,
        "create_ms_avg": round(sum(create_ms) / len(create_ms)) if create_ms else None,
        "create_ms_max": max(create_ms) if create_ms else None,
        "complete_ms_avg": round(sum(complete_ms) / len(complete_ms)) if complete_ms else None,
        "complete_ms_max": max(complete_ms) if complete_ms else None,
        "identity_ok": all(u["identity_before"]["ok"] and u["identity_after"]["ok"] for u in users),
        "upload_ids_unique": len(upload_ids) == len(set(upload_ids)),
        "errors": [{"user": u["username"], "file": f["upload_name"], "error": f.get("error")}
                   for u in users for f in u["files"] if not f["ok"]],
        "all_verified": all(
            u.get("verify", {}).get("missing") == [] for u in users if any(f["ok"] for f in u["files"])
        ),
    }


# ---------------------------------------------------------------- 모드: discover

async def discover(browser: Browser, accounts: list[dict[str, str]], args: argparse.Namespace) -> int:
    account = accounts[0]
    session = await login(browser, account, args.url)
    try:
        base_url = args.url.rstrip("/")
        status, roots, _ = await api(session, base_url, "GET", "/folders/roots")
        print(f"\n[{account['username']}] GET /folders/roots -> {status}", flush=True)
        if not isinstance(roots, list):
            print(short(roots, 800))
            return 1
        for root in roots:
            print(f"  ROOT {root.get('id')}  {root.get('name')}  gubun={root.get('gubun')}", flush=True)
            c_status, children, _ = await api(session, base_url, "GET", f"/folders/{root.get('id')}/children")
            items = children if isinstance(children, list) else (children or {}).get("items", []) if isinstance(children, dict) else []
            print(f"    children -> {c_status} ({len(items)}건)", flush=True)
            for child in items[:15]:
                print(f"      {child.get('id')}  {child.get('name')}", flush=True)
        print("\n업로드 대상 폴더 ID를 --folder-id 로 지정하세요. (계정별로 다르게 하려면 --folder-map new1=...,new2=...)", flush=True)
        return 0
    finally:
        await session.context.close()


# ---------------------------------------------------------------- 메인

async def run(args: argparse.Namespace) -> int:
    accounts = load_accounts(args.accounts, args.max_users, args.users)
    if not accounts:
        raise SystemExit("사용할 계정이 없습니다.")
    usernames = [a["username"] for a in accounts]
    extensions = {e.strip().lower() for e in args.extensions.split(",") if e.strip()}
    candidates = collect_candidates(args.source, extensions, int(args.max_file_mb * 1024 * 1024))
    plan = build_plan(usernames, candidates, args.files_per_user, args.file_mode)
    folder_map = parse_folder_map(args.folder_map)
    prefix = args.name_prefix or f"ct{datetime.now().strftime('%m%d%H%M%S')}_"
    base_url = args.url.rstrip("/")

    print(f"계정: {', '.join(usernames)}", flush=True)
    print(f"소스: {args.source} (후보 {len(candidates)}개, 확장자 필터/최대 {args.max_file_mb}MB)", flush=True)
    print(f"분배: {args.file_mode}, 계정당 {args.files_per_user}개 / 파일 동시 {args.file_concurrency}, 청크 동시 {args.chunk_concurrency}", flush=True)
    print(f"파일명 접두사: {'(원본 유지)' if args.keep_names else prefix}", flush=True)
    for username in usernames:
        folder = folder_map.get(username) or args.folder_id or "(미지정)"
        print(f"  [{username}] -> {folder}", flush=True)
        for path in plan[username]:
            print(f"      {upload_name(path, username, prefix, args.keep_names)}  ({path.stat().st_size:,}B)", flush=True)

    if not args.execute and not args.discover:
        print("\ndry-run: 실제 업로드는 하지 않았습니다. 실행하려면 --execute --folder-id <ID> 를 지정하세요.", flush=True)
        return 0

    if args.execute:
        missing = [u for u in usernames if not (folder_map.get(u) or args.folder_id)]
        if missing:
            raise SystemExit(f"업로드 대상 폴더가 지정되지 않은 계정: {missing} (--folder-id 또는 --folder-map)")
        if not any(plan.values()):
            raise SystemExit("업로드할 파일이 없습니다. --source/--extensions/--max-file-mb 를 확인하세요.")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=args.headless)
        try:
            if args.discover:
                return await discover(browser, accounts, args)

            sessions = list(await asyncio.gather(*(login(browser, a, args.url) for a in accounts)))
            barrier = asyncio.Barrier(len(sessions))
            print("\n=== 동시 업로드 시작 ===", flush=True)
            wall_start = time.perf_counter()
            users = await asyncio.gather(
                *(
                    run_user(s, base_url, folder_map.get(s.username) or args.folder_id, plan[s.username], prefix, barrier, args)
                    for s in sessions
                )
            )
            wall_ms = ms_since(wall_start)
            for s in sessions:
                await s.context.close()
        finally:
            await browser.close()

    summary = summarize(list(users))
    summary["wall_ms"] = wall_ms
    report = {
        "mode": "SKMR_CONCURRENT_UPLOAD",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "name_prefix": "" if args.keep_names else prefix,
        "settings": {
            "file_mode": args.file_mode,
            "files_per_user": args.files_per_user,
            "file_concurrency": args.file_concurrency,
            "chunk_concurrency": args.chunk_concurrency,
            "chunk_size": args.chunk_size or "server/default",
        },
        "summary": summary,
        "users": [{k: v for k, v in u.items() if not k.startswith("_")} for u in users],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== 요약 ===", flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    print(f"\nReport: {args.report}", flush=True)
    healthy = summary["identity_ok"] and summary["upload_ids_unique"]
    return 0 if summary["files_failed"] == 0 and summary["all_verified"] and healthy else 1


def main() -> int:
    configure_console_output()
    parser = argparse.ArgumentParser(description="skmr 청크 업로드 API 동시 접근 테스트")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--accounts", type=Path, default=DEFAULT_ACCOUNTS)
    parser.add_argument("--users", default="", help="사용할 계정 이름(쉼표 구분). 기본은 설정 파일의 전체")
    parser.add_argument("--max-users", type=int, default=0)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="업로드할 로컬 문서 폴더 (기본: 다운로드)")
    parser.add_argument("--extensions", default=DEFAULT_EXTENSIONS)
    parser.add_argument("--max-file-mb", type=float, default=DEFAULT_MAX_FILE_MB)
    parser.add_argument("--files-per-user", type=int, default=3)
    parser.add_argument("--file-mode", choices=("distinct", "same"), default="distinct",
                        help="distinct=계정마다 서로 다른 파일, same=모든 계정이 같은 파일")
    parser.add_argument("--folder-id", default="", help="업로드 대상 폴더 ID (전 계정 공통)")
    parser.add_argument("--folder-map", default="", help="계정별 폴더 지정: new1=fld_a,new2=fld_b (공통값보다 우선)")
    parser.add_argument("--name-prefix", default="", help="업로드 파일명 접두사 (기본: ct<시각>_)")
    parser.add_argument("--keep-names", action="store_true", help="파일명을 그대로 사용 (동일 파일명 충돌 시나리오용)")
    parser.add_argument("--file-concurrency", type=int, default=1, help="계정 안에서 동시에 올릴 파일 수")
    parser.add_argument("--chunk-concurrency", type=int, default=1, help="파일 안에서 동시에 보낼 청크 수")
    parser.add_argument("--chunk-size", type=int, default=0, help="바이트. 0이면 서버 응답의 chunkSize, 없으면 5MB")
    parser.add_argument("--no-verify", action="store_true", help="업로드 후 문서 목록 검증 생략")
    parser.add_argument("--verify-timeout", type=float, default=30.0)
    parser.add_argument("--execute", action="store_true", help="실제 업로드 수행 (없으면 dry-run)")
    parser.add_argument("--discover", action="store_true", help="폴더 ID 확인용 읽기 전용 조회 후 종료")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
