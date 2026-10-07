# -*- coding: utf-8 -*-
"""apitest 실행 진입점.

  python -m apitest <scenario> [공통옵션] [시나리오옵션]
  python -m apitest list

공통옵션: --target(기본 skmr) --users --iterations --duration --ramp-up --no-sync
          --base-url --header NAME=VALUE(반복 가능) --report --execute
쓰기 동작이 있는 시나리오(upload)는 --execute 가 없으면 실행하지 않는다.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .core.config import load_target, parse_header_args
from .core.metrics import Recorder
from .core.report import checks_passed, print_summary, write_report
from .core.runner import run_scenario
from .targets.skmr.scenarios import SCENARIOS


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(line_buffering=True, write_through=True)
            except Exception:
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apitest", description="순수 API 자동 테스트 (기능/부하)")
    sub = parser.add_subparsers(dest="scenario", required=True)
    sub.add_parser("list", help="시나리오 목록")
    for name, cls in SCENARIOS.items():
        p = sub.add_parser(name, help=cls.description)
        p.add_argument("--target", default="skmr")
        p.add_argument("--users", type=int, default=0, help="가상 유저 수 (0=계정 수). 계정보다 많으면 순환 배정")
        p.add_argument("--iterations", type=int, default=1, help="유저당 반복 횟수")
        p.add_argument("--duration", type=float, default=0, help="초. 지정하면 iterations 대신 이 시간 동안 반복")
        p.add_argument("--ramp-up", type=float, default=0, help="유저 시작을 이 시간(초)에 걸쳐 분산")
        p.add_argument("--no-sync", action="store_true", help="로그인 완료 후 동시 시작 게이트를 쓰지 않음")
        p.add_argument("--base-url", default="", help="설정 파일의 base_url 대신 사용 (모의 서버 등)")
        p.add_argument("--header", action="append", default=[], metavar="NAME=VALUE",
                       help="추가 요청 헤더 (API key 등). VALUE 가 env:NAME 이면 환경변수에서 읽음")
        p.add_argument("--accounts", type=Path, default=None, help="계정 파일 (기본 config/<target>_accounts.json)")
        p.add_argument("--report", type=Path, default=None)
        p.add_argument("--execute", action="store_true", help="서버에 쓰기(업로드 등)가 있는 시나리오 실행 허용")
        cls.add_args(p)
    return parser


async def amain(args: argparse.Namespace) -> int:
    cls = SCENARIOS[args.scenario]
    if getattr(cls, "writes", False) and not args.execute:
        print(f"[{args.scenario}] 서버에 데이터를 만드는 시나리오입니다. 실행하려면 --execute 를 지정하세요. (dry-run: 실행 안 함)")
        return 0

    cfg = load_target(
        args.target, base_url=args.base_url, extra_headers=parse_header_args(args.header), accounts_file=args.accounts
    )
    users = args.users or len(cfg.accounts)
    scenario = cls(args)
    recorder = Recorder()
    print(f"target={cfg.name} base_url={cfg.base_url} scenario={scenario.name} users={users} "
          f"iterations={args.iterations} duration={args.duration}s ramp_up={args.ramp_up}s "
          f"headers={sorted(cfg.headers)}", flush=True)

    vus, checks = await run_scenario(
        scenario, cfg, recorder,
        users=users, iterations=args.iterations, duration_s=args.duration,
        ramp_up_s=args.ramp_up, sync_start=not args.no_sync,
    )
    summary = recorder.summary()
    print_summary(summary, checks)
    meta = {
        "target": cfg.name, "base_url": cfg.base_url, "users": users, "iterations": args.iterations,
        "duration": args.duration, "ramp_up": args.ramp_up, "sync_start": not args.no_sync,
        "setup_failed_vus": [v.name for v in vus if not v.ready],
    }
    path = write_report(args.report, scenario.name, meta, summary, checks, recorder.samples)
    print(f"\nReport: {path}")
    healthy = summary["overall"]["fail"] == 0 and checks_passed(checks) and all(v.ready for v in vus)
    return 0 if healthy else 1


def main(argv: list[str] | None = None) -> int:
    configure_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.scenario == "list":
        for name, cls in SCENARIOS.items():
            print(f"{name:<8} {cls.description}")
        return 0
    return asyncio.run(amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
