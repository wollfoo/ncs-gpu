"""Sự kiện hướng sự kiện cho pipeline GPU."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

from .models import MiningJob, Batch, PipelineStage


@dataclass(slots=True)
class JobSubmitted:
    job: MiningJob
    submitted_at: datetime


@dataclass(slots=True)
class BatchDispatched:
    batch: Batch
    dispatched_at: datetime


@dataclass(slots=True)
class StageCompleted:
    batch_id: str
    stage: PipelineStage | None
    completed_at: datetime
    metrics: List[float]
    is_final: bool = False
    duration_ms: float | None = None
