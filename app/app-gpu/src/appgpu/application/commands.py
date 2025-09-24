"""Command CQRS cho orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class SubmitJobCommand:
    job_id: str
    payload: Dict[str, float]
    priority: str
    deadline_ms: int


@dataclass(slots=True)
class CollectMetricsCommand:
    metric_names: List[str]
