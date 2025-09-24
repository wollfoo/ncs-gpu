#!/usr/bin/env python3
"""Probe mô phỏng để thu thập phân phối latency cho monolith."""

from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from pathlib import Path


def simulate_latency(samples: int, mean_ms: float, std_ms: float) -> list[float]:
    latencies_ms: list[float] = []
    for _ in range(samples):
        target_ms = max(random.gauss(mean_ms, std_ms), 1.0)
        start = time.perf_counter()
        time.sleep(target_ms / 1000.0)
        duration_ms = (time.perf_counter() - start) * 1000.0
        latencies_ms.append(duration_ms)
    return latencies_ms


def compute_percentiles(latencies: list[float]) -> dict[str, float]:
    latencies_sorted = sorted(latencies)

    def percentile(p: float) -> float:
        k = (len(latencies_sorted) - 1) * p
        f = int(k)
        c = min(f + 1, len(latencies_sorted) - 1)
        if f == c:
            return latencies_sorted[f]
        return latencies_sorted[f] + (latencies_sorted[c] - latencies_sorted[f]) * (k - f)

    return {
        "p50": percentile(0.50),
        "p95": percentile(0.95),
        "p99": percentile(0.99),
        "mean": statistics.fmean(latencies_sorted),
        "min": latencies_sorted[0],
        "max": latencies_sorted[-1],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate monolith latency measurements")
    parser.add_argument("--samples", type=int, default=120, help="Số mẫu mô phỏng")
    parser.add_argument("--mean-ms", type=float, default=22.0, help="Độ trễ trung bình (ms)")
    parser.add_argument("--std-ms", type=float, default=6.0, help="Độ lệch chuẩn (ms)")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/baseline_latency.json"),
        help="Đường dẫn tập tin JSON để lưu kết quả",
    )
    args = parser.parse_args()

    latencies = simulate_latency(args.samples, args.mean_ms, args.std_ms)
    percentiles = compute_percentiles(latencies)
    payload = {
        "samples": args.samples,
        "mean_target_ms": args.mean_ms,
        "std_target_ms": args.std_ms,
        "percentiles": percentiles,
    }

    args.output.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
