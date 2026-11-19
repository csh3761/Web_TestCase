# -*- coding: utf-8 -*-
"""콘솔 요약 출력 + JSON 리포트 저장."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import REPORT_DIR


def print_summary(summary: dict[str, Any], checks: dict[str, Any]) -> None:
    overall = summary["overall"]
    print("\n=== 결과 요약 ===")
    print(
        f"총 {overall['count']}건 / 성공 {overall['ok']} / 실패 {overall['fail']} "
        f"(오류율 {overall['error_rate'] * 100:.1f}%) / {summary['duration_s']}s / {overall['rps']} req/s"
    )
    header = f"{'endpoint':<22}{'count':>7}{'fail':>6}{'avg':>8}{'p50':>8}{'p95':>8}{'p99':>8}{'max':>9}  status"
    print(header)
    print("-" * len(header))
    for name, st in summary["by_endpoint"].items():
        print(
            f"{name:<22}{st['count']:>7}{st['fail']:>6}{st['avg_ms']:>8}{st['p50_ms']:>8}"
            f"{st['p95_ms']:>8}{st['p99_ms']:>8}{st['max_ms']:>9}  {st['status']}"
        )
    if summary["counters"]:
        print(f"counters: {summary['counters']}")
    if summary["top_errors"]:
        print("주요 오류:")
        for item in summary["top_errors"][:5]:
            print(f"  x{item['count']}  {item['error']}")
    if checks:
        print("검증:")
        for key, value in checks.items():
            mark = "OK  " if value is True else ("FAIL" if value is False else "    ")
            print(f"  [{mark}] {key}: {value}")


def checks_passed(checks: dict[str, Any]) -> bool:
    return all(v is not False for v in checks.values())


def write_report(path: Path | None, scenario: str, meta: dict[str, Any], summary: dict[str, Any],
                 checks: dict[str, Any], samples: list[Any]) -> Path:
    if path is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = REPORT_DIR / f"apitest_{scenario}_{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scenario": scenario,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "meta": meta,
        "summary": summary,
        "checks": checks,
        "samples": [s.__dict__ for s in samples],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path
