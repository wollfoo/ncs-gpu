"""Value object chuẩn hoá priority & deadline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PriorityClass:
    name: str
    max_latency_ms: int

    def score(self) -> int:
        mapping = {"red": 4, "orange": 3, "yellow": 2, "green": 1}
        return mapping.get(self.name.lower(), 0)
