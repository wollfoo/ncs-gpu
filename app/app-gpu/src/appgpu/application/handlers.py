"""Command handler ánh xạ command → service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Type

from ..domain import MiningJob
from .commands import SubmitJobCommand, CollectMetricsCommand
from .services import JobService, MetricsService


@dataclass
class CommandHandler:
    job_service: JobService
    metrics_service: MetricsService

    def dispatch(self, command: object) -> object:
        routing: Dict[Type[object], Callable[[object], object]] = {
            SubmitJobCommand: self._handle_submit,
            CollectMetricsCommand: self._handle_metrics,
        }
        handler = routing.get(type(command))
        if not handler:
            raise ValueError(f"Unknown command type: {type(command)!r}")
        return handler(command)

    def _handle_submit(self, command: SubmitJobCommand) -> MiningJob:
        return self.job_service.submit(command)

    def _handle_metrics(self, command: CollectMetricsCommand) -> dict:
        return self.metrics_service.collect(command)
