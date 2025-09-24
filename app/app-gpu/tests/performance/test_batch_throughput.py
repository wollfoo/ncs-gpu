import asyncio

import numpy as np

from appgpu.application import SubmitJobCommand, JobService, MetricsService, CommandHandler
from appgpu.domain import PipelineStage
from appgpu.infrastructure import MessageBus, Scheduler, GPUAdapter


def _build_pipeline(batch_size: int = 32):
    message_bus = MessageBus()
    stages = [
        PipelineStage(name="pre", duration_budget_ms=10, max_concurrency=4),
        PipelineStage(name="infer", duration_budget_ms=40, max_concurrency=4),
        PipelineStage(name="post", duration_budget_ms=20, max_concurrency=4),
    ]
    job_service = JobService(stages)
    handler = CommandHandler(job_service, MetricsService())
    adapter = GPUAdapter()

    async def stage_pre(batch):
        await asyncio.sleep(0.001)
        return [len(job.payload) for job in batch.jobs]

    async def stage_inf(batch):
        return await adapter.run_batch([job.payload for job in batch.jobs])

    async def stage_post(batch):
        return [metric * 1.1 for metric in await stage_inf(batch)]

    scheduler = Scheduler(
        stages=[stage_pre, stage_inf, stage_post],
        batch_dispatch=message_bus.publish,
        stage_complete=message_bus.publish,
    )

    return message_bus, job_service, handler, scheduler


def test_batch_throughput_benchmark(benchmark):
    async def run_once():
        message_bus, job_service, handler, scheduler = _build_pipeline()
        asyncio.create_task(message_bus.start())
        payload = np.random.rand(32, 8).astype(float)
        jobs = [
            handler.dispatch(
                SubmitJobCommand(
                    job_id=f"job-{i}",
                    payload={str(idx): float(value) for idx, value in enumerate(row)},
                    priority="orange",
                    deadline_ms=150,
                )
            )
            for i, row in enumerate(payload)
        ]
        batch = job_service.batch(jobs, batch_size=32)
        await scheduler.run(batch)

    def runner():
        asyncio.run(run_once())

    benchmark(runner)
