import asyncio

import pytest

from appgpu.application import (
    SubmitJobCommand,
    JobService,
    MetricsService,
    CommandHandler,
    MetricsRecorder,
)
from appgpu.domain import PipelineStage
from appgpu.infrastructure import MessageBus, Scheduler, GPUAdapter


@pytest.mark.asyncio
async def test_pipeline_complete():
    message_bus = MessageBus()
    stages = [
        PipelineStage(name="pre", duration_budget_ms=10, max_concurrency=2),
        PipelineStage(name="infer", duration_budget_ms=40, max_concurrency=2),
    ]
    job_service = JobService(stages)
    metrics_recorder = MetricsRecorder()
    handler = CommandHandler(job_service, MetricsService(metrics_recorder))
    adapter = GPUAdapter()

    async def stage_pre(batch):
        return [len(job.payload) for job in batch.jobs]

    async def stage_inf(batch):
        return await adapter.run_batch([job.payload for job in batch.jobs])

    scheduler = Scheduler(
        stages=[stage_pre, stage_inf],
        batch_dispatch=message_bus.publish,
        stage_complete=message_bus.publish,
    )

    asyncio.create_task(message_bus.start())

    job = handler.dispatch(
        SubmitJobCommand(
            job_id="job-1",
            payload={"x": 1.0, "y": 2.0},
            priority="red",
            deadline_ms=100,
        )
    )
    batch = job_service.batch([job], batch_size=1)

    await scheduler.run(batch)
