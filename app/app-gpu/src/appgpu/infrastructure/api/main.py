"""API điều phối nhận yêu cầu và push vào pipeline."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel, Field

from ...config import load_config
from ...application import (
    SubmitJobCommand,
    CollectMetricsCommand,
    JobService,
    MetricsService,
    CommandHandler,
)
from ...application.metrics import MetricsRecorder
from ...domain import PipelineStage, BatchDispatched, StageCompleted
from ..message_bus import MessageBus
from ..scheduler import Scheduler
from ..gpu_adapter import GPUAdapter


class JobRequest(BaseModel):
    payload: dict[str, float]
    priority: str = Field(default="green")
    deadline_ms: int = Field(default=600)


class MetricsResponse(BaseModel):
    metrics: dict[str, dict[str, Any]]


config = load_config()
app = FastAPI(title="GPU Mining Orchestrator", version="0.1.0")
message_bus = MessageBus()

stage_templates = [
    PipelineStage(name="preprocess", duration_budget_ms=10, max_concurrency=4),
    PipelineStage(name="inference", duration_budget_ms=40, max_concurrency=4),
    PipelineStage(name="postprocess", duration_budget_ms=20, max_concurrency=4),
]

job_service = JobService(stage_templates)
metrics_recorder = MetricsRecorder()
metrics_service = MetricsService(recorder=metrics_recorder)
handler = CommandHandler(job_service=job_service, metrics_service=metrics_service)
gpu_adapter = GPUAdapter(endpoint=None)
message_bus_task: Optional[asyncio.Task] = None


async def stage_preprocess(batch):
    await asyncio.sleep(0.005)
    return [len(job.payload) for job in batch.jobs]


async def stage_inference(batch):
    metrics = await gpu_adapter.run_batch([job.payload for job in batch.jobs])
    return metrics


async def stage_postprocess(batch):
    await asyncio.sleep(0.002)
    return [datetime.utcnow().timestamp() for _ in batch.jobs]


scheduler = Scheduler(
    stages=[stage_preprocess, stage_inference, stage_postprocess],
    batch_dispatch=message_bus.publish,
    stage_complete=message_bus.publish,
)


async def on_batch_dispatched(event: BatchDispatched) -> None:
    return None


async def on_stage_completed(event: StageCompleted) -> None:
    if event.is_final and event.duration_ms is not None:
        metrics_recorder.record(event.duration_ms)
    return None


message_bus.subscribe(BatchDispatched, on_batch_dispatched)
message_bus.subscribe(StageCompleted, on_stage_completed)


@app.on_event("startup")
async def startup_event() -> None:
    global message_bus_task
    message_bus_task = asyncio.create_task(message_bus.start())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await message_bus.stop()
    global message_bus_task
    if message_bus_task:
        await message_bus_task
        message_bus_task = None


@app.post("/jobs")
async def submit_job(request: JobRequest) -> dict[str, str]:
    job_id = str(uuid4())
    job = handler.dispatch(
        SubmitJobCommand(
            job_id=job_id,
            payload=request.payload,
            priority=request.priority,
            deadline_ms=request.deadline_ms,
        )
    )
    batch = job_service.batch([job], batch_size=config.batch_size)
    asyncio.create_task(scheduler.run(batch))
    return {"job_id": job_id}


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    metrics = handler.dispatch(CollectMetricsCommand(metric_names=["p50", "p95", "p99", "count"]))
    return MetricsResponse(metrics=metrics)
