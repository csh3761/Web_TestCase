# -*- coding: utf-8 -*-
"""대상(target) 설정 로딩.

config/<target>_api.json  : base_url, api_prefix, verify_tls, headers(API key 등), accounts_file ...
config/<target>_accounts.json : 계정 목록 ({"accounts": [{"username","password"}]})

headers 값이 "env:NAME" 형식이면 환경변수에서 읽는다 (비밀값을 파일에 두지 않으려는 용도).
설정 파일은 git에서 제외되고(config/*.json), *.example.json 템플릿만 추적된다.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
REPORT_DIR = REPO_ROOT / "reports"


@dataclass(frozen=True)
class Account:
    username: str
    password: str


@dataclass
class TargetConfig:
    name: str
    base_url: str
    api_prefix: str = "/api/v1"
    verify_tls: bool = False
    timeout_s: float = 30.0
    max_connections: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    accounts: list[Account] = field(default_factory=list)

    def url(self, path: str) -> str:
        return f"{self.api_prefix}{path}"


def _resolve_env(value: str) -> str:
    if value.startswith("env:"):
        name = value[4:]
        resolved = os.environ.get(name)
        if resolved is None:
            raise KeyError(f"환경변수 {name} 이(가) 설정되지 않았습니다.")
        return resolved
    return value


def parse_header_args(items: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep:
            raise ValueError(f"--header 는 NAME=VALUE 형식이어야 합니다: {item}")
        headers[key.strip()] = _resolve_env(value.strip())
    return headers


def load_accounts(path: Path) -> list[Account]:
    if not path.exists():
        raise FileNotFoundError(f"계정 설정 파일이 없습니다: {path}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return [Account(str(a["username"]), str(a["password"])) for a in data["accounts"]]


def load_target(
    name: str,
    *,
    base_url: str = "",
    extra_headers: dict[str, str] | None = None,
    accounts_file: Path | None = None,
) -> TargetConfig:
    raw: dict[str, Any] = {}
    config_path = CONFIG_DIR / f"{name}_api.json"
    if config_path.exists():
        raw = json.loads(config_path.read_text(encoding="utf-8-sig"))
    elif not base_url:
        raise FileNotFoundError(
            f"대상 설정이 없습니다: {config_path} (config/{name}_api.example.json 을 복사하거나 --base-url 지정)"
        )

    headers = {k: _resolve_env(str(v)) for k, v in (raw.get("headers") or {}).items()}
    headers.update(extra_headers or {})

    accounts_path = accounts_file or (REPO_ROOT / raw.get("accounts_file", f"config/{name}_accounts.json"))
    return TargetConfig(
        name=name,
        base_url=(base_url or raw["base_url"]).rstrip("/"),
        api_prefix=raw.get("api_prefix", "/api/v1"),
        verify_tls=bool(raw.get("verify_tls", False)),
        timeout_s=float(raw.get("timeout_s", 30.0)),
        max_connections=int(raw.get("max_connections", 200)),
        headers=headers,
        accounts=load_accounts(accounts_path),
    )
