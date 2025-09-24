"""Exporter Prometheus độc lập cho metrics tổng hợp."""

from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from starlette.responses import Response

app = FastAPI(title="Telemetry Exporter")
registry = CollectorRegistry()
jobs_total = Counter("jobs_total", "Tổng số job xử lý", registry=registry)
latency_hist = Histogram(
    "job_latency_ms",
    "Phân phối độ trễ job",
    buckets=(10, 25, 50, 75, 100, 150, 300),
    registry=registry,
)


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    output = generate_latest(registry)
    return Response(content=output, media_type="text/plain; version=0.0.4")
