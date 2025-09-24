"""Worker CLI giúp chạy orchestrator ngoài FastAPI."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ...application import (
    SubmitJobCommand,
    JobService,
    MetricsService,
    CommandHandler,
    MetricsRecorder,
)
from ...domain import PipelineStage, StageCompleted
from ...config import load_config
from ..gpu_adapter import GPUAdapter
from ..scheduler import Scheduler
from ..message_bus import MessageBus


async def main(batch_payload_path: str) -> None:
    config = load_config()
    message_bus = MessageBus()
    stage_templates = [
        PipelineStage(name="preprocess", duration_budget_ms=10, max_concurrency=4),
        PipelineStage(name="inference", duration_budget_ms=40, max_concurrency=4),
        PipelineStage(name="postprocess", duration_budget_ms=20, max_concurrency=4),
    ]
    job_service = JobService(stage_templates)
    metrics_recorder = MetricsRecorder()
    handler = CommandHandler(job_service, MetricsService(metrics_recorder))
    adapter = GPUAdapter()

    async def stage_pre(batch):
        await asyncio.sleep(0.005)
        return [len(job.payload) for job in batch.jobs]

    async def stage_inf(batch):
        return await adapter.run_batch([job.payload for job in batch.jobs])

    async def stage_post(batch):
        return [1.0 for _ in batch.jobs]

    scheduler = Scheduler(
        stages=[stage_pre, stage_inf, stage_post],
        batch_dispatch=message_bus.publish,
        stage_complete=message_bus.publish,
    )

    async def on_stage_completed(event: StageCompleted) -> None:
        if event.is_final and event.duration_ms is not None:
            metrics_recorder.record(event.duration_ms)

    message_bus.subscribe(StageCompleted, on_stage_completed)

    bus_task = asyncio.create_task(message_bus.start())

    payload = json.loads(Path(batch_payload_path).read_text())
    jobs = [
        handler.dispatch(
            SubmitJobCommand(
                job_id=item["job_id"],
                payload=item["payload"],
                priority=item.get("priority", "green"),
                deadline_ms=item.get("deadline_ms", 600),
            )
        )
        for item in payload
    ]
    batch = job_service.batch(jobs, batch_size=config.batch_size)
    await scheduler.run(batch)
    await message_bus.stop()
    await bus_task


if __name__ == "__main__":  # pragma: no cover - CLI entry
    import argparse

    parser = argparse.ArgumentParser(description="Run orchestrator batch offline")
    parser.add_argument("file", help="Đường dẫn JSON chứa danh sách payload")
    args = parser.parse_args()
    asyncio.run(main(args.file))
