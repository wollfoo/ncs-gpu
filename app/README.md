App (GPU Mining Runtime)

This directory contains the GPU-only mining runtime including the main entrypoint, core orchestration, stealth wrappers, PID logging, and Docker artifacts.

Start here: see `CODE_INDEX.md` for a full file map, import hints, configuration guidance, and best practices.

Quick start
- Create venv and install: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Run: `PYTHONPATH=. python start_mining.py`
- Docker: `docker build -t opus-gpu-app . && docker run --gpus all --env-file .env --rm opus-gpu-app`

Notes
- Use loggers from `mining_environment.scripts.module_loggers`.
- Do not hardcode configuration; use `mining_environment/config/*.json` or environment variables.

