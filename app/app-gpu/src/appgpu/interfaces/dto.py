"""Data transfer objects cho layer ngoài."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class JobDTO:
    job_id: str
    payload: Dict[str, float]
    priority: str
    deadline_ms: int
