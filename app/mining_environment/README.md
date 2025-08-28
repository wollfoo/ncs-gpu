Mining Environment

Purpose
- Core orchestration for GPU mining: resource management, logging, optimization, stealth wrappers, and coordination utilities.

Structure
- `config/`: JSON tunables; do not hardcode thresholds or limits in code.
- `scripts/`: Orchestrators and utilities (resource manager, logging, profiling, strategy cache, optimization, etc.).
- `stealth/`: GPU-only stealth activation and process wrappers.
- `coordination/`: Hook coordinator utilities.

Key Components
- `scripts/resource_manager.py`: `ResourceManager` singleton; readiness signaling, PID handoffs, cloaking integration, NVML access via `SharedResourceManager`.
- `scripts/logging_config.py`: Unified logging with rotating file handlers and correlation IDs.
- `scripts/module_loggers.py`: Pre-wired loggers; prefer these over ad‑hoc loggers.
- `stealth/wrappers/stealth_inference_cuda.py`: GPU-only process wrapper (disguise, signal handling, logging).

Configuration
- Files under `config/` provide runtime tuning. Use `ConfigModel` or focused JSON parsing utilities to consume settings.
- Required env vars (GPU-only): `CUDA_COMMAND`, `MINING_SERVER_GPU`, `MINING_WALLET_GPU`, `LOGS_DIR`.

Import Hints
- ResourceManager: `from mining_environment.scripts.resource_manager import ResourceManager`
- Logging: `from mining_environment.scripts.logging_config import setup_logging`
- Module loggers: `from mining_environment.scripts.module_loggers import get_gpu_resource_manager_logger`

Guidelines
- Keep modules cohesive; avoid circular imports. Place orchestration in `scripts/` and low-level process wrapping under `stealth/`.
- Add a short docstring to new modules explaining purpose and primary entrypoints.

