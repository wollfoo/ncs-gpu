"""Định nghĩa entity/aggregate cho hệ thống khai thác GPU."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class PipelineStage:
    """Mô tả một stage trong pipeline song song."""

    name: str
    duration_budget_ms: int
    max_concurrency: int


@dataclass(slots=True)
class MiningJob:
    """Aggregate đại diện cho một yêu cầu đào GPU."""

    job_id: str
    payload: dict
    priority: str
    submitted_at: datetime = field(default_factory=datetime.utcnow)
    deadline_ms: Optional[int] = None
    stages: List[PipelineStage] = field(default_factory=list)

    def add_stage(self, stage: PipelineStage) -> None:
        self.stages.append(stage)


@dataclass(slots=True)
class Batch:
    """Batch inference để nâng throughput."""

    batch_id: str
    jobs: List[MiningJob]
    created_at: datetime = field(default_factory=datetime.utcnow)
    max_deadline_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.jobs)
