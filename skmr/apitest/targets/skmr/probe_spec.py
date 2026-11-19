# -*- coding: utf-8 -*-
"""OpenAPI 명세(docs/api/skmr_openapi.json)를 읽어 모든 API 를 긁어오는 도구.

- GET 은 실제로 호출해 실제 응답값까지 기록한다 (서버 데이터를 바꾸지 않는다).
- POST/PUT/PATCH/DELETE 는 호출하지 않는다. 명세의 태그/요약/요청·응답 스키마만 기록한다.
  (쓰기·삭제는 실행 전 별도 허가가 필요하다는 기존 원칙을 따른다.)
- GET 중 경로/쿼리 파라미터가 필요한 것은, 먼저 파라미터 없는 GET들을 호출해 얻은 실제 값
  (folderId, revisionCode, approvalId, indexName 등)으로 채워서 이어서 호출한다.
  값을 구하지 못한 것은 호출하지 않고 사유를 남긴다.

사용법: .venv/Scripts/python.exe -m apitest.targets.skmr.probe_spec [--out-dir docs/api]
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from ...core.client import ApiClient
from ...core.config import load_target
from ...core.metrics import Recorder
from . import auth

SPEC_PATH = Path("docs/api/skmr_openapi.json")

# 알려진 추가 쿼리값 (명세에 optional 이거나 object 로 뭉쳐 있어 일반 규칙으로는 못 채우는 것들)
EXTRA_QUERY = {
    "/api/v1/documents": {"boxId": "DOCBOXM_000000000005", "page": 1, "size": 30},
    "/api/v1/agent/documents": {"boxId": "DOCBOXM_000000000005", "page": 1, "size": 30},
}
EXTRA_PATH = {
    "/api/v1/documents/{boxType}/latest": {"boxType": "MY_DOC"},
}

# 호출하지 않고 넘기는 GET (실행하려면 사전 조건이 필요하거나, 부수효과 위험이 있음)
SKIP_PATHS = {
    "/api/v1/auth/agent-login": "인증 코드(code)가 필요하고, 임의 값으로 시도하면 인증 시도 기록이 남을 수 있어 호출하지 않음",
    "/api/v1/document-uploads/{uploadId}": "업로드 세션 생성(쓰기)이 선행되어야 함. 별도 업로드 테스트에서 확인함",
    "/api/v1/documents/download-jobs/{token}/content": "다운로드 작업 생성(쓰기성 흐름)이 선행되어야 함",
    "/api/v1/documents/download-jobs/{token}/chunks/{chunkIndex}": "다운로드 작업 생성이 선행되어야 함",
}

# 경로/쿼리 파라미터 이름 -> 시드 값을 채워 넣을 때 쓰는 키 이름 매핑
PARAM_ALIASES = {
    "repoName": "repository",
    "deptCode": "departmentCode",
}


def load_spec() -> dict[str, Any]:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def resolve_schema(spec: dict[str, Any], node: Any) -> Any:
    while isinstance(node, dict) and "$ref" in node:
        node = spec["components"]["schemas"][node["$ref"].split("/")[-1]]
    return node


def op_response_schema(spec: dict[str, Any], op: dict[str, Any]) -> Any:
    ok = op.get("responses", {}).get("200") or op.get("responses", {}).get("201")
    if not ok:
        return None
    for ct, v in ok.get("content", {}).items():
        return resolve_schema(spec, v.get("schema"))
    return None


def op_request_schema(spec: dict[str, Any], op: dict[str, Any]) -> Any:
    rb = op.get("requestBody")
    if not rb:
        return None
    for ct, v in rb.get("content", {}).items():
        return resolve_schema(spec, v.get("schema"))
    return None


class Seeds:
    """호출해서 얻은 실제 값을 파라미터 이름별로 모아 두는 저장소."""

    def __init__(self) -> None:
        self.values: dict[str, list[str]] = {}

    def add(self, name: str, value: Any) -> None:
        if value is None:
            return
        value = str(value)
        if not value:
            return
        self.values.setdefault(name, [])
        if value not in self.values[name]:
            self.values[name].append(value)

    def pick(self, name: str) -> str | None:
        name = PARAM_ALIASES.get(name, name)
        vals = self.values.get(name)
        return vals[0] if vals else None


async def call(api: ApiClient, method: str, path: str, **kw) -> dict[str, Any]:
    """명세의 경로는 이미 전체 경로(/api/v1/... 또는 /api/...)다.
    ApiClient.request 는 cfg.api_prefix(/api/v1) 를 자동으로 덧붙이므로,
    접두사가 일치하는 업무 API 는 그 부분을 떼어 넘기고, 접두사가 다른
    검색엔진/클러스터 관리 API(/api/...)는 내부 httpx 클라이언트로 직접 호출한다."""
    prefix = api.cfg.api_prefix
    if path.startswith(prefix):
        r = await api.request(path, method, path[len(prefix):], **kw)
        return {"status": r.status, "body": r.body}
    params = kw.get("params")
    response = await api._http.request(method, path, params=params)  # noqa: SLF001  명세 원본 경로 그대로 호출
    try:
        body = response.json()
    except ValueError:
        body = response.text[:500]
    return {"status": response.status_code, "body": body}


def truncate(obj: Any, limit: int = 600) -> str:
    s = json.dumps(obj, ensure_ascii=False)
    return s[:limit] + ("...(생략)" if len(s) > limit else "")


async def harvest_seeds(api: ApiClient, seeds: Seeds) -> None:
    """파라미터가 필요 없는 핵심 GET 들을 먼저 호출해 이어지는 호출에 쓸 실제 값을 모은다."""
    r = await call(api, "GET", "/api/v1/folders/roots")
    roots = r["body"] if isinstance(r["body"], list) else []
    # 가상 폴더(바로가기 등, gubun=Q)는 일반 폴더 파라미터로 재사용하면 404 가 나서 제외한다.
    for root in roots[:3]:
        r = await call(api, "GET", f"/api/v1/folders/{root.get('folderId')}/children")
        kids = r["body"] if isinstance(r["body"], list) else []
        for k in kids:
            if str(k.get("folderId", "")).startswith("DOCBOXM") and k.get("gubun") not in ("Q",):
                seeds.add("folderId", k.get("folderId"))
                seeds.add("gubun", k.get("gubun"))
                seeds.add("departmentCode", k.get("departmentCode"))
                seeds.add("groupCode", k.get("groupCode"))

    r = await call(api, "GET", "/api/v1/documents/recent")
    docs = r["body"] if isinstance(r["body"], list) else []
    for d in docs[:5]:
        seeds.add("revisionCode", d.get("revisionCode"))

    r = await call(api, "GET", "/api/v1/approvals")
    appr = r["body"] if isinstance(r["body"], list) else []
    for a in appr[:3]:
        seeds.add("approvalId", a.get("approvalCode") or a.get("approvalId"))

    r = await call(api, "GET", "/api/v1/departments")
    deps = r["body"] if isinstance(r["body"], list) else []
    for d in deps[:3]:
        seeds.add("departmentCode", d.get("departmentCode"))

    if seeds.pick("revisionCode"):
        r = await call(api, "GET", f"/api/v1/documents/{seeds.pick('revisionCode')}/shares")
        shares = r["body"] if isinstance(r["body"], list) else []
        for sh in shares[:3]:
            seeds.add("linkCode", sh.get("linkCode"))

    # 검색엔진/클러스터 관리 영역 시드 (별도 base path /api/...)
    def extract_items(body: Any) -> list[Any]:
        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            if isinstance(body.get("items"), list):
                return body["items"]
            data = body.get("data")
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                return data["items"]
            if isinstance(body.get("nodes"), list):
                return body["nodes"]
        return []

    for path, key in [
        ("/api/indices", "indexName"),
        ("/api/aliases", "aliasName"),
        ("/api/repositories", "repo"),
        ("/api/index-templates", "name"),
        ("/api/ism/policies", "policyId"),
        ("/api/clusters", "clusterId"),
        ("/api/cluster/nodes", "nodeId"),
    ]:
        try:
            r = await call(api, "GET", path)
        except Exception as exc:  # noqa: BLE001  연결/권한 문제는 건너뛰고 기록만
            continue
        for it in extract_items(r["body"])[:3]:
            if isinstance(it, dict):
                for cand in ("name", "indexName", "aliasName", "repo", "repository", "policyId", "clusterId", "id"):
                    if cand in it:
                        seeds.add(key, it[cand])
            elif isinstance(it, str):
                seeds.add(key, it)
    seeds.add("repository", seeds.pick("repo"))
    if seeds.pick("repository"):
        r = await call(api, "GET", "/api/snapshot/list/repository", params={"repoName": seeds.pick("repository")})
        body = r["body"]
        snaps = body if isinstance(body, list) else []
        for sn in snaps[:2] if isinstance(snaps, list) else []:
            if isinstance(sn, dict):
                seeds.add("snapshotName", sn.get("snapshot") or sn.get("name"))
                seeds.add("snapshot", sn.get("snapshot") or sn.get("name"))
    seeds.add("repoName", seeds.pick("repository"))


async def probe_get(spec: dict[str, Any], api: ApiClient, path: str, op: dict[str, Any], seeds: Seeds) -> dict[str, Any]:
    tag = (op.get("tags") or ["(태그없음)"])[0]
    base_row = {"tag": tag, "method": "GET", "path": path, "summary": op.get("summary", ""),
                "response_schema": op_response_schema(spec, op)}

    if path in SKIP_PATHS:
        return {**base_row, "called": False, "note": SKIP_PATHS[path]}

    params = op.get("parameters", [])
    path_params = [p for p in params if p.get("in") == "path"]
    query_required = [p for p in params if p.get("in") == "query" and p.get("required")]

    real_path = path
    missing = []
    extra_path = EXTRA_PATH.get(path, {})
    for p in path_params:
        v = extra_path.get(p["name"]) or seeds.pick(p["name"])
        if v is None:
            missing.append(p["name"])
        else:
            real_path = real_path.replace("{" + p["name"] + "}", v)
    query: dict[str, Any] = dict(EXTRA_QUERY.get(path, {}))
    for p in query_required:
        name = p["name"]
        if name in ("q", "text", "param", "pattern", "code"):
            v = {"q": "a", "text": "a", "param": "a", "pattern": "*", "code": None}[name]
            if name == "code":
                missing.append(name)
                continue
        elif name == "query":
            continue  # 업무 API 의 query 는 DTO 필드가 개별 쿼리 파라미터로 풀려 전달됨. EXTRA_QUERY 로 채움
        elif name == "analyzer":
            v = "standard"
        elif name == "revisionCodes":
            v = seeds.pick("revisionCode")
            if v is None:
                missing.append(name)
                continue
        elif name == "index" or name == "indexName":
            v = seeds.pick("indexName")
            if v is None:
                missing.append(name)
                continue
        elif name in ("repository", "snapshot"):
            v = seeds.pick(name)
            if v is None:
                missing.append(name)
                continue
        elif name == "policyName":
            v = seeds.pick("policyId")
            if v is None:
                missing.append(name)
                continue
        else:
            v = seeds.pick(name)
            if v is None:
                missing.append(name)
                continue
        query[name] = v

    if path == "/api/v1/document-moves/owner-candidates" and seeds.pick("gubun") == "D" and seeds.pick("departmentCode"):
        query["departmentCode"] = seeds.pick("departmentCode")  # gubun=D 일 때는 실제로 필수 (명세엔 optional로만 표기됨)

    if missing:
        return {**base_row, "called": False, "note": f"필요한 값 확보 못함: {', '.join(missing)}"}

    try:
        r = await call(api, "GET", real_path, params=query or None)
        return {**base_row, "called": True, "called_path": real_path, "status": r["status"], "sample": truncate(r["body"])}
    except Exception as exc:  # noqa: BLE001
        return {**base_row, "called": True, "called_path": real_path, "status": None, "note": f"예외: {exc}"}


def write_op_row(spec: dict[str, Any], path: str, method: str, op: dict[str, Any]) -> dict[str, Any]:
    tag = (op.get("tags") or ["(태그없음)"])[0]
    return {
        "tag": tag, "method": method.upper(), "path": path, "summary": op.get("summary", ""),
        "called": False, "note": "쓰기/삭제 API 는 이 도구가 호출하지 않음 (명세만 기록)",
        "request_schema": op_request_schema(spec, op),
        "response_schema": op_response_schema(spec, op),
    }


async def run(out_dir: Path) -> None:
    spec = load_spec()
    cfg = load_target("skmr")
    acc = cfg.accounts[0]
    api = ApiClient(cfg, Recorder(), acc.username)
    rows: list[dict[str, Any]] = []
    try:
        await auth.login(api, acc)
        seeds = Seeds()
        await harvest_seeds(api, seeds)

        for path, methods in spec["paths"].items():
            for method, op in methods.items():
                if method == "get":
                    rows.append(await probe_get(spec, api, path, op, seeds))
                else:
                    rows.append(write_op_row(spec, path, method, op))

        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "skmr_api_catalog.json").write_text(
            json.dumps({"seeds": seeds.values, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        write_markdown(out_dir / "skmr_api_catalog.md", rows, seeds)
        called = sum(1 for r in rows if r.get("called"))
        ok = sum(1 for r in rows if r.get("called") and isinstance(r.get("status"), int) and 200 <= r["status"] < 300)
        print(f"총 {len(rows)}개 중 GET 호출 {called}개 (2xx {ok}개). 출력: {out_dir}")
    finally:
        await api.aclose()


def write_markdown(path: Path, rows: list[dict[str, Any]], seeds: Seeds) -> None:
    by_tag: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_tag.setdefault(r["tag"], []).append(r)

    lines = ["# skmr API 카탈로그 (명세 기반 자동 수집)", "",
              "GET 은 실제로 호출한 응답을 기록했습니다 (서버 데이터 변경 없음).",
              "POST/PUT/PATCH/DELETE 는 호출하지 않고 명세의 태그/요약/스키마만 기록했습니다.", "",
              f"- 계정: 테스트 계정(new1) / 생성 시각 기준", ""]
    for tag in sorted(by_tag):
        items = by_tag[tag]
        lines.append(f"## {tag} ({len(items)})")
        lines.append("")
        lines.append("| 메서드 | 경로 | 요약 | 결과 |")
        lines.append("|---|---|---|---|")
        for r in sorted(items, key=lambda x: (x["method"], x["path"])):
            if r.get("called"):
                status = r.get("status")
                mark = f"{status}" if status else "오류"
            else:
                mark = f"호출 안 함 ({r.get('note','')})"
            lines.append(f"| {r['method']} | `{r['path']}` | {r.get('summary','')} | {mark} |")
        lines.append("")

    lines.append("## GET 실제 응답 샘플")
    lines.append("")
    for r in rows:
        if r.get("method") == "GET" and r.get("called") and r.get("status") is not None:
            lines.append(f"### {r['method']} `{r.get('called_path', r['path'])}`")
            lines.append(f"- 상태: {r['status']}")
            lines.append("```json")
            lines.append(r.get("sample", ""))
            lines.append("```")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="docs/api")
    args = parser.parse_args()
    asyncio.run(run(Path(args.out_dir)))


if __name__ == "__main__":
    main()
