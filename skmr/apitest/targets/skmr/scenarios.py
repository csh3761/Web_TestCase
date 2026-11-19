# -*- coding: utf-8 -*-
"""skmr 시나리오: smoke(기능), login(동시 로그인/부하), upload(동시 업로드/부하), survey(조회 API 과부하/스트레스)."""
from __future__ import annotations

import asyncio
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ...core.runner import VU, Scenario
from . import auth
from .api import Payload, SkmrApi, collect_names, upload_payload

DEFAULT_EXTENSIONS = "pdf,docx,doc,xlsx,xls,pptx,ppt,txt,csv,md,jpg,jpeg,png,gif,hwp,hwpx"


async def _login(vu: VU) -> SkmrApi:
    auth.install_refresh_handler(vu.client, vu.account)
    response = await auth.login(vu.client, vu.account)
    vu.state["login_username"] = response.get("username")
    api = SkmrApi(vu.client)
    vu.state["api"] = api
    return api


async def _check_identity(vu: VU) -> dict[str, Any]:
    """/auth/me 가 본인 계정을 돌려주는지 확인 (세션 섞임 감지)."""
    me = await vu.state["api"].me()
    actual = me.get("username")
    return {"status": me.status, "username": actual, "ok": me.ok and actual == vu.account.username}


def _identity_check(vus: list[VU]) -> dict[str, Any]:
    ready = [v for v in vus if v.ready]
    ok = bool(ready) and all(
        v.state.get("login_username") == v.account.username
        and v.state.get("identity_before", {}).get("ok")
        and v.state.get("identity_after", {}).get("ok")
        for v in ready
    )
    return {"session_identity": ok}


# ------------------------------------------------------------------ smoke (기능 테스트)

class SmokeScenario(Scenario):
    name = "smoke"
    description = "기능 점검: 로그인 -> me -> 폴더/문서 조회 (--with-upload 시 업로드 세션 create/status/cancel)"

    @classmethod
    def add_args(cls, parser: Any) -> None:
        parser.add_argument("--folder-id", default="", help="--with-upload 용 대상 폴더 ID")
        parser.add_argument("--with-upload", action="store_true", help="업로드 세션 create/status/cancel 점검 (문서는 만들지 않음)")

    async def setup(self, vu: VU) -> None:
        await _login(vu)

    async def run(self, vu: VU, iteration: int) -> None:
        api: SkmrApi = vu.state["api"]
        steps: dict[str, bool] = {}

        me = await api.me()
        steps["me"] = me.ok and me.get("username") == vu.account.username

        roots = await api.roots()
        steps["roots"] = roots.ok and isinstance(roots.body, list) and len(roots.body) > 0
        first_root = roots.body[0].get("id") if steps["roots"] else ""

        if first_root:
            children = await api.children(first_root)
            steps["children"] = children.ok
            docs = await api.documents(first_root)
            steps["documents"] = docs.ok

        if self.args.with_upload:
            if not self.args.folder_id:
                raise ValueError("--with-upload 에는 --folder-id 가 필요합니다.")
            dummy = b"smoke-test!"[:10]
            created = await api.upload_create(
                self.args.folder_id, f"smoke_{vu.account.username}.txt", len(dummy), hashlib.sha256(dummy).hexdigest()
            )
            steps["upload.create"] = created.ok and bool(created.get("uploadId"))
            if steps["upload.create"]:
                upload_id = created.get("uploadId")
                steps["upload.status"] = (await api.upload_status(upload_id)).ok
                steps["upload.cancel"] = (await api.upload_cancel(upload_id)).ok

        vu.state.setdefault("steps", []).append(steps)

    async def finalize(self, vus: list[VU]) -> dict[str, Any]:
        merged: dict[str, bool] = {}
        for vu in vus:
            for steps in vu.state.get("steps", []):
                for key, ok in steps.items():
                    merged[key] = merged.get(key, True) and ok
        return {f"step.{k}": v for k, v in merged.items()}


# ------------------------------------------------------------------ login (동시 로그인/부하)

class LoginScenario(Scenario):
    name = "login"
    description = "동시 로그인 + 세션 유지 확인. --relogin 이면 매 반복마다 재로그인하여 로그인 API 부하 측정"

    @classmethod
    def add_args(cls, parser: Any) -> None:
        parser.add_argument("--relogin", action="store_true", help="반복마다 새로 로그인 (로그인 API 부하)")
        parser.add_argument("--think-ms", type=int, default=0, help="반복 사이 대기(ms)")

    async def setup(self, vu: VU) -> None:
        await _login(vu)
        vu.state["identity_before"] = await _check_identity(vu)

    async def run(self, vu: VU, iteration: int) -> None:
        if self.args.relogin and iteration > 0:
            await auth.login(vu.client, vu.account)
        me = await vu.state["api"].me()
        if me.get("username") != vu.account.username:
            vu.state["identity_mismatch"] = vu.state.get("identity_mismatch", 0) + 1
        if self.args.think_ms:
            await asyncio.sleep(self.args.think_ms / 1000)

    async def teardown(self, vu: VU) -> None:
        vu.state["identity_after"] = await _check_identity(vu)

    async def finalize(self, vus: list[VU]) -> dict[str, Any]:
        checks = _identity_check(vus)
        checks["no_identity_mismatch"] = not any(v.state.get("identity_mismatch") for v in vus)
        return checks


# ------------------------------------------------------------------ upload (동시 업로드/부하)

class UploadScenario(Scenario):
    name = "upload"
    description = "청크 업로드 5개 API 동시 접근. 합성 데이터(기본) 또는 로컬 문서 폴더(--source) 사용"
    writes = True  # 서버에 문서를 만든다 -> --execute 필요

    @classmethod
    def add_args(cls, parser: Any) -> None:
        parser.add_argument("--folder-id", default="", help="업로드 대상 폴더 ID (필수)")
        parser.add_argument("--files-per-iteration", type=int, default=2)
        parser.add_argument("--size-kb", type=int, default=256, help="합성 데이터 파일 크기(KB). --source 가 없을 때")
        parser.add_argument("--source", type=Path, default=None, help="로컬 문서 폴더 (예: 다운로드). 지정하면 실제 파일 사용")
        parser.add_argument("--extensions", default=DEFAULT_EXTENSIONS)
        parser.add_argument("--max-file-mb", type=float, default=20)
        parser.add_argument("--chunk-size", type=int, default=0, help="바이트. 서버 응답의 chunkSize 가 우선이며 응답에 없을 때만 사용")
        parser.add_argument("--chunk-concurrency", type=int, default=3, help="파일 안 동시 청크 수 (프론트엔드 기본 3)")
        parser.add_argument("--file-concurrency", type=int, default=2, help="계정 안 동시 파일 수 (프론트엔드 기본 2)")
        parser.add_argument("--prefix", default="", help="파일명 접두사 (기본: ct<시각>_)")
        parser.add_argument("--keep-names", action="store_true", help="--source 파일명을 그대로 사용 (동일명 충돌 시나리오)")
        parser.add_argument("--no-verify", action="store_true")
        parser.add_argument("--verify-timeout", type=float, default=30.0)

    def __init__(self, args: Any) -> None:
        super().__init__(args)
        if not args.folder_id:
            raise SystemExit("--folder-id 가 필요합니다. (smoke/discover 로 폴더 ID 확인)")
        self.prefix = args.prefix or f"ct{datetime.now().strftime('%m%d%H%M%S')}_"
        self.local_files: list[Path] = []
        if args.source:
            exts = {e.strip().lower() for e in args.extensions.split(",") if e.strip()}
            limit = int(args.max_file_mb * 1024 * 1024)
            self.local_files = sorted(
                (p for p in args.source.iterdir()
                 if p.is_file() and p.suffix.lower().lstrip(".") in exts and 0 < p.stat().st_size <= limit),
                key=lambda p: p.name.lower(),
            )
            if not self.local_files:
                raise SystemExit(f"업로드할 파일이 없습니다: {args.source}")

    def _payloads(self, vu: VU, iteration: int) -> list[Payload]:
        payloads: list[Payload] = []
        for k in range(self.args.files_per_iteration):
            if self.local_files:
                src = self.local_files[(vu.index * self.args.files_per_iteration + iteration * 7 + k) % len(self.local_files)]
                name = src.name if self.args.keep_names else f"{self.prefix}vu{vu.index}_i{iteration}_{src.name}"
                payloads.append(Payload(name, src.stat().st_size, src))
            else:
                name = f"{self.prefix}vu{vu.index}_{vu.account.username}_i{iteration}_f{k}.bin"
                payloads.append(Payload.synthetic(name, self.args.size_kb * 1024))
        return payloads

    async def setup(self, vu: VU) -> None:
        await _login(vu)
        vu.state["identity_before"] = await _check_identity(vu)
        vu.state["uploads"] = []

    async def run(self, vu: VU, iteration: int) -> None:
        api: SkmrApi = vu.state["api"]
        semaphore = asyncio.Semaphore(self.args.file_concurrency)

        async def one(payload: Payload) -> dict[str, Any]:
            async with semaphore:
                started = time.perf_counter()
                result = await upload_payload(
                    api, self.args.folder_id, payload,
                    chunk_size=self.args.chunk_size, chunk_concurrency=self.args.chunk_concurrency,
                )
                result["total_ms"] = round((time.perf_counter() - started) * 1000)
                vu.recorder.add(
                    "upload.total", 200 if result["ok"] else 0, result["total_ms"], result["ok"],
                    user=vu.name, error=result.get("error", ""), nbytes=payload.size,
                )
                return result

        results = await asyncio.gather(*(one(p) for p in self._payloads(vu, iteration)))
        vu.state["uploads"].extend(results)

    async def teardown(self, vu: VU) -> None:
        vu.state["identity_after"] = await _check_identity(vu)
        ok_names = {u["name"] for u in vu.state["uploads"] if u["ok"]}
        if ok_names and not self.args.no_verify:
            api: SkmrApi = vu.state["api"]
            deadline = time.perf_counter() + self.args.verify_timeout
            missing = set(ok_names)
            while time.perf_counter() < deadline:
                listed = await api.documents(self.args.folder_id)
                names: set[str] = set()
                collect_names(listed.body, names)
                missing = ok_names - names
                if not missing:
                    break
                await asyncio.sleep(1)
            vu.state["verify"] = {"expected": len(ok_names), "missing": sorted(missing)}

    async def finalize(self, vus: list[VU]) -> dict[str, Any]:
        uploads = [u for v in vus for u in v.state.get("uploads", [])]
        ids = [u["upload_id"] for u in uploads if "upload_id" in u]
        failed = [u for u in uploads if not u["ok"]]
        checks = _identity_check(vus)
        checks["all_uploaded"] = not failed and bool(uploads)
        checks["upload_ids_unique"] = len(ids) == len(set(ids))
        if not self.args.no_verify:
            checks["all_visible_in_list"] = all(not v.state.get("verify", {}).get("missing") for v in vus)
        checks["name_prefix"] = self.prefix
        checks["uploaded_files"] = len(uploads) - len(failed)
        return checks


# ------------------------------------------------------------------ survey (조회 API 과부하/스트레스)

# (이름, 경로, 필요한 시드 키들) — 시드가 없으면 그 반복에서 건너뛴다.
# Postman 세트 4("API 전체 루틴")와 같은 읽기 전용 업무 API 묶음. 명세상 서버 데이터를 바꾸지 않는다.
BUSINESS_ENDPOINTS: list[tuple[str, str, tuple[str, ...]]] = [
    ("auth.me", "/auth/me", ()),
    ("common.doc_types", "/common/doc-types", ()),
    ("common.sdms_manager", "/common/sdms-manager", ()),
    ("dashboard.layout", "/dashboard/layout", ()),
    ("dashboard.widgets", "/dashboard/widgets", ()),
    ("folders.roots", "/folders/roots", ()),
    ("folders.children", "/folders/{folder_id}/children", ("folder_id",)),
    ("folders.document_attributes", "/folders/{folder_id}/document-attributes", ("folder_id",)),
    ("folders.capabilities", "/folders/{folder_id}/capabilities?gubun={gubun}", ("folder_id", "gubun")),
    ("folder_favorites.list", "/folder-favorites", ()),
    ("folder_favorites.candidates", "/folder-favorites/candidates", ()),
    ("documents.list", "/documents?boxId={folder_id_root}&page=1&size=30", ("folder_id_root",)),
    ("documents.recent", "/documents/recent", ()),
    ("documents.context_menu", "/documents/context-menu-items?revisionCodes={revision_code}", ("revision_code",)),
    ("documents.versions", "/documents/{revision_code}/versions", ("revision_code",)),
    ("documents.history", "/documents/{revision_code}/history", ("revision_code",)),
    ("documents.move_options", "/documents/{revision_code}/move-options", ("revision_code",)),
    ("documents.copy_options", "/documents/{revision_code}/copy-options", ("revision_code",)),
    ("document_moves.owner_candidates",
     "/document-moves/owner-candidates?folderId={folder_id}&gubun={gubun}&departmentCode={department_code}",
     ("folder_id", "gubun", "department_code")),
    ("approvals.list", "/approvals", ()),
    ("menus.top", "/menus/top", ()),
    ("departments.list", "/departments", ()),
    ("users.search", "/users?q=a", ()),
    ("logs.api", "/logs/api", ()),
]

ADMIN_ENDPOINTS: list[tuple[str, str, tuple[str, ...]]] = [
    ("admin.indices", "/indices", ()),
    ("admin.aliases", "/aliases", ()),
    ("admin.repositories", "/repositories", ()),
    ("admin.index_templates", "/index-templates", ()),
    ("admin.ism_policies", "/ism/policies", ()),
    ("admin.clusters", "/clusters", ()),
    ("admin.cluster_nodes", "/cluster/nodes", ()),
    ("admin.overview", "/overview", ()),
]


class SurveyScenario(Scenario):
    name = "survey"
    description = ("조회(읽기 전용) API 묶음을 과부하/스트레스로 반복 호출. 쓰기 없음. "
                    "서버가 계정당 세션 1개만 허용해(재로그인 시 기존 세션 SESSION_REPLACED) "
                    "--users 로 유저 '수'를 늘리는 대신 --burst 로 세션마다 보내는 동시 요청 '양'을 늘린다 "
                    "(--users 는 계정 수 이하로 유지할 것)")

    @classmethod
    def add_args(cls, parser: Any) -> None:
        parser.add_argument("--include-admin", action="store_true",
                             help="검색엔진/클러스터 관리 API(인덱스·정책 등)도 포함. 공유 클러스터에 부하를 줄 수 있어 기본 비활성")
        parser.add_argument("--endpoints", default="", help="이름을 콤마로 지정해 이 목록만 반복 (기본: 전체)")
        parser.add_argument("--think-ms", type=int, default=0, help="반복 사이 대기(ms). --burst 안 호출들 사이에는 적용 안 됨")
        parser.add_argument("--burst", type=int, default=1,
                             help="한 반복(iteration)에서 엔드포인트 묶음을 동시에 몇 벌 쏠지 (세션 1개당 동시 요청 수 배수)")

    def _endpoint_list(self) -> list[tuple[str, str, tuple[str, ...]]]:
        all_eps = BUSINESS_ENDPOINTS + (ADMIN_ENDPOINTS if self.args.include_admin else [])
        if not self.args.endpoints:
            return all_eps
        wanted = {n.strip() for n in self.args.endpoints.split(",") if n.strip()}
        return [e for e in all_eps if e[0] in wanted]

    async def setup(self, vu: VU) -> None:
        api = await _login(vu)
        vu.state["identity_before"] = await _check_identity(vu)

        seeds: dict[str, str] = {}
        roots = await api.roots()
        root_list = roots.body if isinstance(roots.body, list) else []
        real_root = next((r for r in root_list if r.get("gubun") == "D"), None) or \
            next((r for r in root_list if r.get("gubun") != "Q"), None)
        if real_root:
            seeds["folder_id_root"] = real_root["folderId"]
            children = await api.children(real_root["folderId"])
            kids = children.body if isinstance(children.body, list) else []
            if kids:
                seeds["folder_id"] = kids[0]["folderId"]
                seeds["gubun"] = kids[0].get("gubun", "")
                seeds["department_code"] = kids[0].get("departmentCode", "") or ""

        recent = await vu.client.request("documents.recent", "GET", "/documents/recent")
        if isinstance(recent.body, list) and recent.body:
            seeds["revision_code"] = recent.body[0].get("revisionCode", "")

        vu.state["seeds"] = seeds

    async def _call_one(self, vu: VU, ep_name: str, path: str) -> None:
        try:
            await vu.client.request(ep_name, "GET", path, retry_401=True)
        except Exception:  # noqa: BLE001  네트워크 예외는 client.request 가 이미 status=0 으로 기록함
            pass

    async def run(self, vu: VU, iteration: int) -> None:
        seeds = vu.state["seeds"]
        calls: list[tuple[str, str]] = []
        for ep_name, template, needs in self._endpoint_list():
            if any(not seeds.get(k) for k in needs):
                continue  # 이 VU 에서 시드를 못 구한 엔드포인트는 건너뜀 (오류로 치지 않음)
            calls.append((ep_name, template.format(**seeds)))

        if self.args.burst <= 1 and not self.args.think_ms:
            # burst=1 이고 think-ms 도 없으면 굳이 순차로 늦출 이유가 없어 그냥 동시에 보낸다
            await asyncio.gather(*(self._call_one(vu, n, p) for n, p in calls))
            return

        for _ in range(max(1, self.args.burst)):
            # 세션 1개가 엔드포인트 묶음 전체를 한 번에(동시에) 쏜다 -> 세션 수가 아니라 이 동시 요청량으로 부하를 올린다
            await asyncio.gather(*(self._call_one(vu, n, p) for n, p in calls))
            if self.args.think_ms:
                await asyncio.sleep(self.args.think_ms / 1000)

    async def teardown(self, vu: VU) -> None:
        vu.state["identity_after"] = await _check_identity(vu)

    async def finalize(self, vus: list[VU]) -> dict[str, Any]:
        return _identity_check(vus)


SCENARIOS: dict[str, type[Scenario]] = {s.name: s for s in (SmokeScenario, LoginScenario, UploadScenario, SurveyScenario)}
