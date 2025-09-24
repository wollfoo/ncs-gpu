"""Metric utilities cho orchestrator."""

from __future__ import annotations

from collections import deque
from threading import RLock
from typing import Deque, Dict, Iterable


class MetricsRecorder:
    """Lưu trữ độ trễ và sinh percentiles cho báo cáo."""

    def __init__(self, max_samples: int = 1000) -> None:
        self._durations_ms: Deque[float] = deque(maxlen=max_samples)
        self._lock = RLock()
        self._total_jobs = 0

    def record(self, duration_ms: float) -> None:
        with self._lock:
            self._durations_ms.append(duration_ms)
            self._total_jobs += 1

    def summary(self) -> Dict[str, float]:
        with self._lock:
            if not self._durations_ms:
                return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0.0}
            samples = sorted(self._durations_ms)
            return {
                "p50": _percentile(samples, 0.50),
                "p95": _percentile(samples, 0.95),
                "p99": _percentile(samples, 0.99),
                "count": float(self._total_jobs),
            }


def _percentile(sorted_samples: Iterable[float], percentile: float) -> float:
    sample_list = list(sorted_samples)
    if not sample_list:
        return 0.0
    if len(sample_list) == 1:
        return sample_list[0]
    k = (len(sample_list) - 1) * percentile
    f = int(k)
    c = min(f + 1, len(sample_list) - 1)
    if f == c:
        return sample_list[f]
    return sample_list[f] + (sample_list[c] - sample_list[f]) * (k - f)
