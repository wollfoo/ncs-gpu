"""Helper xây dựng pipeline đa stage với feature flag."""

from __future__ import annotations

from typing import Callable, Iterable

from ..gpu_adapter import GPUAdapter


def build_gpu_pipeline(adapter: GPUAdapter, enable_postprocess: bool = True) -> Iterable[Callable]:
    async def stage_preprocess(batch):
        return [len(job.payload) for job in batch.jobs]

    async def stage_inference(batch):
        return await adapter.run_batch([job.payload for job in batch.jobs])

    async def stage_postprocess(batch):
        return [metric * 1.0 for metric in await stage_inference(batch)]

    stages = [stage_preprocess, stage_inference]
    if enable_postprocess:
        stages.append(stage_postprocess)
    return stages
