"""mining_environment.config

JSON configuration files for runtime tuning. Do not hardcode limits or thresholds in code; prefer reading from these files or environment variables.

Files (typical usage):
- `system_params.json`: System-wide defaults; safety thresholds.
- `resource_config.json`: Process-level budgets and resource caps.
- `gpu_optimization_config.json`: GPU optimization tuning knobs.
- `hardware_optimization.json`: Low-level hardware policy hints.
- `environmental_limits.json`: External constraints (thermal/power/cooling).
- `threading_config.json`: Concurrency and scheduling intervals.
- `coordination.json`: Hook/coordination toggles and defaults.
"""

__all__ = []
