PYTHON?=python3
POETRY?=poetry
VENV?=.venv

.PHONY: deps lint format test integration perf go-build rust-build cpp-build docker

deps:
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install -U pip && pip install -r requirements.txt

lint:
	. $(VENV)/bin/activate && ruff check src tests && black --check src tests

format:
	. $(VENV)/bin/activate && black src tests && ruff check --fix src tests

test:
	. $(VENV)/bin/activate && pytest tests/unit tests/integration

integration:
	. $(VENV)/bin/activate && pytest tests/integration

perf:
	. $(VENV)/bin/activate && pytest tests/performance --benchmark-only

go-build:
	cd go && GOOS=linux GOARCH=amd64 go build ./...

rust-build:
	cd rust && cargo build --release

cpp-build:
	cd cpp && cmake -S . -B build && cmake --build build --config Release

docker:
	docker compose up --build

