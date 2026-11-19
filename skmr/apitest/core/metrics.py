# -*- coding: utf-8 -*-
"""요청 지표 수집/집계 (평균, p50/p95/p99, 오류율, 처리량)."""
from __future__ import annotations

import time
from collections import Counter, defaultdict
from dataclasses import dataclass


@dataclass
class Sample:
    name: str
    status: int
    ms: float
    ok: bool
    user: str = ""
    error: str = ""
    t: float = 0.0  # 측정 시작 기준 상대 시각(초)
    nbytes: int = 0


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, max(0, round(pct / 100 * (len(sorted_values) - 1))))
    return sorted_values[index]


class Recorder:
    def __init__(self) -> None:
        self.samples: list[Sample] = []
        self.counters: Counter[str] = Counter()
        self._t0 = time.perf_counter()

    def reset_clock(self) -> None:
        self._t0 = time.perf_counter()

    def now(self) -> float:
        return time.perf_counter() - self._t0

    def add(self, name: str, status: int, ms: float, ok: bool, *, user: str = "", error: str = "", nbytes: int = 0) -> None:
        self.samples.append(Sample(name, status, ms, ok, user, error, round(self.now(), 4), nbytes))

    def count(self, key: str, amount: int = 1) -> None:
        self.counters[key] += amount

    @staticmethod
    def _stats(samples: list[Sample], duration: float) -> dict:
        times = sorted(s.ms for s in samples)
        fails = [s for s in samples if not s.ok]
        statuses = Counter(s.status for s in samples)
        return {
            "count": len(samples),
            "ok": len(samples) - len(fails),
            "fail": len(fails),
            "error_rate": round(len(fails) / len(samples), 4) if samples else 0.0,
            "avg_ms": round(sum(times) / len(times), 1) if times else 0.0,
            "p50_ms": round(percentile(times, 50), 1),
            "p95_ms": round(percentile(times, 95), 1),
            "p99_ms": round(percentile(times, 99), 1),
            "max_ms": round(times[-1], 1) if times else 0.0,
            "rps": round(len(samples) / duration, 2) if duration > 0 else 0.0,
            "bytes": sum(s.nbytes for s in samples),
            "status": dict(sorted(statuses.items())),
        }

    def summary(self) -> dict:
        samples = self.samples
        duration = max((s.t + s.ms / 1000 for s in samples), default=0.0)
        by_name: dict[str, list[Sample]] = defaultdict(list)
        for sample in samples:
            by_name[sample.name].append(sample)
        errors = Counter(f"{s.name} [{s.status}] {s.error}"[:200] for s in samples if not s.ok)
        return {
            "duration_s": round(duration, 2),
            "overall": self._stats(samples, duration),
            "by_endpoint": {name: self._stats(items, duration) for name, items in sorted(by_name.items())},
            "counters": dict(self.counters),
            "top_errors": [{"error": e, "count": c} for e, c in errors.most_common(10)],
        }
