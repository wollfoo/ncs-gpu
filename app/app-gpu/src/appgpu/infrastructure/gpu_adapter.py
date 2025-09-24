"""Adapter GPU cung cấp giao diện zero-copy và batch processing."""

from __future__ import annotations

from typing import List

import numpy as np


class GPUAdapter:
    """Giao tiếp với dịch vụ inference Rust hoặc fallback numpy."""

    def __init__(self, endpoint: str | None = None) -> None:
        self._endpoint = endpoint

    async def run_batch(self, payloads: List[dict]) -> List[float]:
        if self._endpoint:
            return await self._call_over_http(payloads)
        return self._simulate(payloads)

    async def _call_over_http(self, payloads: List[dict]) -> List[float]:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{self._endpoint}/infer",
                json={"batch": payloads},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("metrics", [])

    def _simulate(self, payloads: List[dict]) -> List[float]:
        matrix = np.array([list(item.values()) for item in payloads], dtype=np.float32)
        covariance = matrix @ matrix.T
        return [float(np.linalg.norm(row)) for row in covariance]
