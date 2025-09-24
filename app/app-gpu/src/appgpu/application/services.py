"""Service ứng dụng cung cấp use-case domain."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List
from uuid import uuid4

from ..domain import Batch, MiningJob, PipelineStage, PriorityClass
from .commands import SubmitJobCommand, CollectMetricsCommand


class JobService:
    """Điều phối nghiệp vụ liên quan tới MiningJob & Batch."""

    def __init__(self, stage_templates: Iterable[PipelineStage]) -> None:
        self._stage_templates = list(stage_templates)

    def submit(self, cmd: SubmitJobCommand) -> MiningJob:
        job = MiningJob(
            job_id=cmd.job_id,
            payload=cmd.payload,
            priority=cmd.priority,
            deadline_ms=cmd.deadline_ms,
        )
        for template in self._stage_templates:
            job.add_stage(template)
        return job

    def batch(self, jobs: List[MiningJob], batch_size: int) -> Batch:
        batch_jobs = jobs[:batch_size]
        batch = Batch(batch_id=str(uuid4()), jobs=batch_jobs)
        if any(j.deadline_ms for j in batch_jobs):
            batch.max_deadline_ms = max(filter(None, (j.deadline_ms for j in batch_jobs)))
        return batch

    def classify_priority(self, priority: str) -> PriorityClass:
        mapping = {
            "red": PriorityClass("red", 60),
            "orange": PriorityClass("orange", 120),
            "yellow": PriorityClass("yellow", 300),
            "green": PriorityClass("green", 600),
        }
        return mapping.get(priority.lower(), PriorityClass("green", 600))


class MetricsService:
    """Tổng hợp metrics phục vụ SLO/SLA."""

    def collect(self, cmd: CollectMetricsCommand) -> dict:
        timestamp = datetime.utcnow().isoformat() + "Z"
        return {name: {"value": 0.0, "timestamp": timestamp} for name in cmd.metric_names}
