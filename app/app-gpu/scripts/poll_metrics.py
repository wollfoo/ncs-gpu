#!/usr/bin/env python3
"""Script đơn giản để poll số liệu Prometheus khi chạy shadow traffic."""

from __future__ import annotations

import argparse
import sys
import time
from typing import Iterable

import httpx


def parse_metrics(text: str, targets: Iterable[str]) -> dict[str, float]:
    lines = text.splitlines()
    result: dict[str, float] = {}
    for metric in targets:
        for line in lines:
            if line.startswith(metric) and not line.startswith(metric + "{"):
                try:
                    result[metric] = float(line.split(" ")[-1])
                except ValueError:
                    continue
                break
    return result


def poll(endpoint: str, interval: float, iterations: int, metrics: list[str]) -> None:
    client = httpx.Client(timeout=2.0)
    try:
        for idx in range(1, iterations + 1):
            try:
                response = client.get(endpoint)
                response.raise_for_status()
                data = parse_metrics(response.text, metrics)
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                values = " ".join(f"{key}={value}" for key, value in data.items())
                print(f"[{timestamp}] sample={idx} {values}")
            except Exception as err:  # pragma: no cover
                print(f"Lỗi lấy metrics: {err}", file=sys.stderr)
            time.sleep(interval)
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll metrics Prometheus cho shadow traffic")
    parser.add_argument("--endpoint", default="http://localhost:9464/metrics", help="URL metrics")
    parser.add_argument(
        "--interval", type=float, default=5.0, help="Khoảng thời gian lấy mẫu (giây)"
    )
    parser.add_argument("--iterations", type=int, default=12, help="Số mẫu thu thập")
    parser.add_argument(
        "--metrics",
        nargs="*",
        default=["jobs_total", "job_latency_ms_sum", "job_latency_ms_count"],
        help="Danh sách metric cần lấy",
    )
    args = parser.parse_args()
    poll(args.endpoint, args.interval, args.iterations, list(args.metrics))


if __name__ == "__main__":
    main()
