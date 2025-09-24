"""Bộ lập lịch bất đồng bộ áp dụng batching + song song."""

from __future__ import annotations

from datetime import datetime
import time
from typing import Awaitable, Callable, Sequence

from ..domain import Batch, BatchDispatched, StageCompleted


class Scheduler:
    """Đưa batch qua pipeline gồm nhiều stage đồng thời."""

    def __init__(
        self,
        stages: Sequence[Callable[[Batch], Awaitable[list[float]]]],
        batch_dispatch: Callable[[BatchDispatched], Awaitable[None]],
        stage_complete: Callable[[StageCompleted], Awaitable[None]],
    ) -> None:
        self._stages = stages
        self._batch_dispatch = batch_dispatch
        self._stage_complete = stage_complete

    async def run(self, batch: Batch) -> None:
        await self._batch_dispatch(BatchDispatched(batch=batch, dispatched_at=datetime.utcnow()))
        start_monotonic = time.perf_counter()
        current_batch = batch
        for index, stage_callable in enumerate(self._stages):
            metrics = await stage_callable(current_batch)
            is_final_stage = index == len(self._stages) - 1
            duration_ms = None
            if is_final_stage:
                duration_ms = (time.perf_counter() - start_monotonic) * 1000.0
            await self._stage_complete(
                StageCompleted(
                    batch_id=current_batch.batch_id,
                    stage=(
                        current_batch.jobs[0].stages[index]
                        if current_batch.jobs and index < len(current_batch.jobs[0].stages)
                        else None
                    ),
                    completed_at=datetime.utcnow(),
                    metrics=metrics,
                    is_final=is_final_stage,
                    duration_ms=duration_ms,
                )
            )
