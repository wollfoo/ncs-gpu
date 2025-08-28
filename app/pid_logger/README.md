PID Logger

Purpose
- Tracks mining process PIDs and streams runtime output to dedicated logs. Bridges miners to `ResourceManager` through a direct registry handoff.

Public API (`pid_logger/__init__.py`)
- `start_worker()`: Starts PID writer, output monitor, and output writer threads.
- `log_pid(pid, is_gpu)`: Legacy PID logging (GPU-only accepted).
- `register_process(pid, process_type, process_obj, process_name=None)`: Registers a process (subprocess.Popen or psutil.Process) for monitoring.
- Diagnostics: `debug_registry_status()`, `force_test_output()`, `manual_register_real_pids()`.

Files
- `worker.py`: PID queue writer + real-time output monitor producing `pid_gpu.log` and streaming runtime lines.
- `direct_registry.py`: In-process registry; supports `ResourceManager` handoff and queue status.
- `mining_output_bridge.py`: Utilities for output/registration bridging.

Usage
- Import: `from pid_logger import start_worker, register_process`
- Ensure `LOGS_DIR` is set. The logger rotates files and writes under `mining_environment/logs` by default.

