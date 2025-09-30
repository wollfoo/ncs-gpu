.PHONY: all build test benchmark clean lint fmt docker

all: build

build:
	@echo "🔨 Building Rust workspace..."
	cargo build --release
	@echo "🔨 Building CUDA kernels..."
	cd kernels && cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build

test:
	cargo test --workspace
	cd kernels && ctest --test-dir build

benchmark:
	cargo bench --workspace
	./scripts/gpu_benchmark.sh

clean:
	cargo clean
	rm -rf kernels/build

lint:
	cargo clippy --workspace -- -D warnings

fmt:
	cargo fmt --all --check

docker:
	docker build -t gpu-miner:latest -f Dockerfile .

install:
	cargo install --path crates/cli

dev:
	nix develop
