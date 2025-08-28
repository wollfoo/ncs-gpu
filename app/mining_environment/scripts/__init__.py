"""mining_environment.scripts

Core orchestration and utilities for the GPU mining runtime.

Includes:
- Resource manager and shared resource helpers
- Unified logging configuration and module loggers
- Optimization/coordinator components and strategy cache
- Utilities, profiling, error management, and guards

Prefer importing stable entrypoints:
- Resource manager: `from mining_environment.scripts.resource_manager import ResourceManager`
- Logging: `from mining_environment.scripts.logging_config import setup_logging`
- Module loggers: `from mining_environment.scripts.module_loggers import get_gpu_resource_manager_logger`
"""

__all__ = []
