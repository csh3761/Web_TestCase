# -*- coding: utf-8 -*-
"""skmr 엔드포인트 래퍼 + 청크 업로드 헬퍼. 지표 이름은 논리 이름(경로의 가변 id 제외)으로 기록된다."""
from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...core.client import ApiClient, Resp

DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024
NAME_KEYS = ("fileName", "documentName", "name", "title", "contentName", "originalFileName", "orgFileName")


class SkmrApi:
    def __init__(self, client: ApiClient) -> None:
        self.c = client

    # ---- 인증/탐색
    async def me(self) -> Resp:
        return await self.c.request("auth.me", "GET", "/auth/me")

    async def roots(self) -> Resp:
        return await self.c.request("folders.roots", "GET", "/folders/roots")

    async def children(self, folder_id: str) -> Resp:
        return await self.c.request("folders.children", "GET", f"/folders/{folder_id}/children")

    async def documents(self, box_id: str, page: int = 1, size: int = 100) -> Resp:
        return await self.c.request(
            "documents.list", "GET", "/documents", params={"boxId": box_id, "page": page, "size": size}
        )

    # ---- 청크 업로드 5개 API
    async def upload_create(
        self, folder_id: str, name: str, size: int, sha256: str, mime: str = "", operation: str = "UPLOAD"
    ) -> Resp:
        """프론트엔드(index-*.js)와 동일한 본문. expectedFileSha256 은 파일 전체의 SHA-256(hex)."""
        body = {
            "operation": operation,
            "folderId": folder_id,
            "fileName": name,
            "fileSize": size,
            "mimeType": mime or mimetypes.guess_type(name)[0] or "application/octet-stream",
            "expectedFileSha256": sha256,
        }
        return await self.c.request("upload.create", "POST", "/document-uploads", json=body)

    async def upload_chunk(self, upload_id: str, index: int, data: bytes) -> Resp:
        """청크마다 X-Chunk-SHA256(hex) 헤더가 필요하다 (프론트엔드 동일)."""
        return await self.c.request(
            "upload.chunk", "PUT", f"/document-uploads/{upload_id}/chunks/{index}", content=data,
            headers={"Content-Type": "application/octet-stream", "X-Chunk-SHA256": hashlib.sha256(data).hexdigest()},
        )

    async def upload_status(self, upload_id: str) -> Resp:
        return await self.c.request("upload.status", "GET", f"/document-uploads/{upload_id}")

    async def upload_complete(self, upload_id: str) -> Resp:
        return await self.c.request("upload.complete", "POST", f"/document-uploads/{upload_id}/complete")

    async def upload_cancel(self, upload_id: str) -> Resp:
        return await self.c.request("upload.cancel", "DELETE", f"/document-uploads/{upload_id}")


@dataclass
class Payload:
    """업로드할 내용. 로컬 파일(path) 또는 메모리 데이터(data, 합성 포함)."""

    name: str
    size: int
    path: Path | None = None
    data: bytes | None = None
    _sha256: str = ""

    @classmethod
    def synthetic(cls, name: str, size: int) -> "Payload":
        """무작위 내용 -> 파일마다 해시가 달라 서버의 동일 내용 중복 처리에 걸리지 않는다."""
        return cls(name=name, size=size, data=os.urandom(size))

    def sha256(self) -> str:
        if not self._sha256:
            digest = hashlib.sha256()
            if self.data is not None:
                digest.update(self.data)
            else:
                with self.path.open("rb") as handle:  # type: ignore[union-attr]
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(block)
            self._sha256 = digest.hexdigest()
        return self._sha256

    def read(self, index: int, chunk_size: int) -> bytes:
        offset = index * chunk_size
        length = min(chunk_size, self.size - offset)
        if self.data is not None:
            return self.data[offset:offset + length]
        with self.path.open("rb") as handle:  # type: ignore[union-attr]
            handle.seek(offset)
            return handle.read(length)


def collect_names(value: Any, out: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in NAME_KEYS and isinstance(item, str):
                out.add(item)
            collect_names(item, out)
    elif isinstance(value, list):
        for item in value:
            collect_names(item, out)


IN_PROGRESS_STATUSES = {"ASSEMBLING", "VERIFYING", "READY_TO_STORE", "STORING"}  # complete 이후 서버 조립 단계


async def wait_completed(api: SkmrApi, upload_id: str, timeout_s: float) -> dict[str, Any]:
    """complete 이후 서버가 조립/검증/저장을 끝내 COMPLETED 가 될 때까지 상태를 폴링한다."""
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        status = await api.upload_status(upload_id)
        state = status.get("status") if status.ok else None
        if state == "COMPLETED":
            return {"completed": True, "status": state}
        if status.ok and state not in IN_PROGRESS_STATUSES and state != "UPLOADING":
            return {"completed": False, "status": state, "body": status.body}
        if asyncio.get_running_loop().time() >= deadline:
            return {"completed": False, "status": state, "body": status.body, "timeout": True}
        await asyncio.sleep(0.5)


async def upload_payload(
    api: SkmrApi, folder_id: str, payload: Payload, *, chunk_concurrency: int = 3, complete_timeout_s: float = 60.0,
    chunk_size: int = 0,
) -> dict[str, Any]:
    """프론트엔드와 같은 흐름: create -> (미전송 청크만) 병렬 PUT -> complete -> COMPLETED 대기.

    - create 응답 status 가 COMPLETED 면 서버가 이미 같은 내용을 갖고 있는 것(중복 제거) -> 청크 전송 생략
    - 청크 크기/개수/이미 올라간 청크(uploadedChunks)는 서버 응답을 따른다 (chunk_size 인자는 응답에 없을 때만 사용)
    - 실패하면 업로드 세션을 DELETE 로 취소하고 error 를 담는다
    """
    result: dict[str, Any] = {"name": payload.name, "size": payload.size, "ok": False}
    upload_id = ""
    try:
        sha = await asyncio.to_thread(payload.sha256)
        created = await api.upload_create(folder_id, payload.name, payload.size, sha)
        if not created.ok or not isinstance(created.body, dict):
            raise RuntimeError(f"create 실패 [{created.status}] {str(created.body)[:200]}")
        body = created.body
        result["create_status"] = body.get("status")
        upload_id = str(body.get("uploadId") or "")
        result["upload_id"] = upload_id

        if body.get("status") == "COMPLETED":
            result.update(ok=True, deduped=True)
            return result
        if not upload_id:
            raise RuntimeError(f"create 응답에 uploadId 없음: {str(body)[:200]}")

        size_per_chunk = int(body.get("chunkSize") or 0) or chunk_size or DEFAULT_CHUNK_SIZE
        total = int(body.get("totalChunks") or 0) or max(1, -(-payload.size // size_per_chunk))
        already = set(body.get("uploadedChunks") or [])
        pending_indexes = [i for i in range(total) if i not in already]
        result.update(chunk_size=size_per_chunk, chunk_count=total, resumed_chunks=len(already))
        semaphore = asyncio.Semaphore(chunk_concurrency)

        async def send(index: int) -> None:
            async with semaphore:
                data = await asyncio.to_thread(payload.read, index, size_per_chunk)
                resp = await api.upload_chunk(upload_id, index, data)
                if not resp.ok:
                    raise RuntimeError(f"chunk {index} 실패 [{resp.status}] {str(resp.body)[:200]}")

        tasks = [asyncio.create_task(send(i)) for i in pending_indexes]
        if tasks:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
            for task in pending:  # 첫 실패 시 남은 청크 전송을 즉시 중단
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                task.result()

        completed = await api.upload_complete(upload_id)
        result["complete_http"] = completed.status
        if not completed.ok:
            raise RuntimeError(f"complete 실패 [{completed.status}] {str(completed.body)[:200]}")
        waited = await wait_completed(api, upload_id, complete_timeout_s)
        result["final_status"] = waited.get("status")
        if not waited["completed"]:
            raise RuntimeError(f"완료 확인 실패: {str(waited)[:200]}")
        result["ok"] = True
    except Exception as exc:
        result["error"] = str(exc)
        if upload_id:
            await api.upload_cancel(upload_id)
            result["cancelled"] = True
    return result
