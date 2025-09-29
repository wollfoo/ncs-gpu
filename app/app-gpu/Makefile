# OPUS-GPU Makefile for build automation

.PHONY: help build test clean docker-build docker-run install fmt lint audit

# Default target
help:
	@echo "🚀 OPUS-GPU Build Automation"
	@echo ""
	@echo "Available targets:"
	@echo "  build          - Build the project in release mode"
	@echo "  debug          - Build the project in debug mode"
	@echo "  test           - Run all tests"
	@echo "  benchmark      - Run benchmark tests"
	@echo "  clean          - Clean build artifacts"
	@echo "  install        - Install the binary to system"
	@echo "  fmt            - Format code with rustfmt"
	@echo "  lint           - Run clippy linting"
	@echo "  audit          - Run security audit"
	@echo "  docker-build   - Build Docker image"
	@echo "  docker-run     - Run Docker container"
	@echo "  docker-dev     - Run development Docker container"
	@echo "  setup          - Setup development environment"

# Build targets
build:
	@echo "🔨 Building OPUS-GPU (release mode)..."
	cargo build --release --features "cuda,opencl"

debug:
	@echo "🔨 Building OPUS-GPU (debug mode)..."
	cargo build --features "cuda,opencl"

# Test targets
test:
	@echo "🧪 Running tests..."
	cargo test --all-features

benchmark:
	@echo "📊 Running benchmarks..."
	cargo bench --all-features

coverage:
	@echo "📋 Generating test coverage..."
	cargo tarpaulin --all-features --out html --output-dir target/coverage/

# Quality assurance
fmt:
	@echo "🎨 Formatting code..."
	cargo fmt --all

lint:
	@echo "🔍 Running linter..."
	cargo clippy --all-features -- -D warnings

audit:
	@echo "🔒 Running security audit..."
	cargo audit

# Utility targets
clean:
	@echo "🧹 Cleaning build artifacts..."
	cargo clean

install: build
	@echo "📦 Installing OPUS-GPU..."
	cargo install --path . --features "cuda,opencl"

# Docker targets
docker-build:
	@echo "🐳 Building Docker image..."
	docker build --target production -t opus-gpu:latest .

docker-build-dev:
	@echo "🐳 Building development Docker image..."
	docker build --target development -t opus-gpu:dev .

docker-run:
	@echo "🐳 Running Docker container..."
	docker run --runtime=nvidia --gpus all \
		-p 8080:8080 -p 8081:8081 -p 8082:8082 -p 9090:9090 \
		-v $(PWD)/config:/app/config:ro \
		-v $(PWD)/data:/app/data \
		opus-gpu:latest

docker-dev:
	@echo "🐳 Running development Docker container..."
	docker run --runtime=nvidia --gpus all \
		-v $(PWD):/usr/src/opus-gpu \
		-p 8080:8080 -p 8081:8081 -p 8082:8082 -p 9090:9090 \
		-it opus-gpu:dev bash

docker-compose-up:
	@echo "🐳 Starting services with docker-compose..."
	docker-compose up -d

docker-compose-down:
	@echo "🐳 Stopping services..."
	docker-compose down

# Development setup
setup:
	@echo "⚙️ Setting up development environment..."
	@echo "Installing Rust components..."
	rustup component add rustfmt clippy
	@echo "Installing development tools..."
	cargo install cargo-watch cargo-edit cargo-audit cargo-tarpaulin
	@echo "Creating directories..."
	mkdir -p data logs keystore backup plugins
	@echo "✅ Development environment setup complete!"

# Development workflow
dev:
	@echo "👨‍💻 Starting development mode with hot reload..."
	cargo watch -x 'run -- --config config/default.toml --dev-mode'

# Release workflow
release: clean fmt lint test audit build
	@echo "🚀 Release build completed successfully!"

# Quick development cycle
quick: fmt
	@echo "⚡ Quick build and test..."
	cargo check --all-features
	cargo test --lib

# Performance profiling
profile:
	@echo "📈 Running performance profiling..."
	cargo build --release --features "cuda,opencl"
	perf record --call-graph=dwarf ./target/release/opus-gpu --benchmark
	perf report

# Memory profiling with Valgrind (Linux only)
memcheck:
	@echo "🔍 Running memory check..."
	cargo build --features "cuda,opencl"
	valgrind --tool=memcheck --leak-check=full ./target/debug/opus-gpu --config config/default.toml

# Documentation
docs:
	@echo "📚 Building documentation..."
	cargo doc --all-features --no-deps --open

docs-serve:
	@echo "🌐 Serving documentation..."
	cargo doc --all-features --no-deps
	python3 -m http.server 8000 -d target/doc

# CI/CD helpers
ci-test: fmt lint test audit
	@echo "✅ CI tests passed!"

ci-build: clean build
	@echo "✅ CI build completed!"

# Database migrations (placeholder for future use)
migrate:
	@echo "🗄️ Running database migrations..."
	# Add migration commands here when implemented

# Configuration validation
validate-config:
	@echo "⚙️ Validating configuration..."
	./target/release/opus-gpu --config config/default.toml --validate-config

# System information
sysinfo:
	@echo "💻 System Information:"
	@echo "Rust version: $(shell rustc --version)"
	@echo "Cargo version: $(shell cargo --version)"
	@echo "GPU Information:"
	@command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv || echo "NVIDIA GPU not detected"
	@command -v clinfo >/dev/null 2>&1 && clinfo -l || echo "OpenCL not detected"

# Dependency management
deps-update:
	@echo "📦 Updating dependencies..."
	cargo update

deps-audit:
	@echo "🔍 Auditing dependencies..."
	cargo audit
	cargo outdated

# Binary size optimization
optimize-size:
	@echo "📦 Building size-optimized binary..."
	RUSTFLAGS="-C link-arg=-s" cargo build --release --features "cuda,opencl"
	@echo "Binary size: $(shell ls -lh target/release/opus-gpu | awk '{print $$5}')"

# Cross-compilation helpers
build-linux:
	@echo "🐧 Building for Linux..."
	cargo build --release --target x86_64-unknown-linux-gnu --features "cuda,opencl"

build-windows:
	@echo "🪟 Building for Windows..."
	cargo build --release --target x86_64-pc-windows-gnu --features "cuda,opencl"

# Environment checks
check-deps:
	@echo "🔍 Checking dependencies..."
	@command -v rustc >/dev/null 2>&1 || (echo "❌ Rust not found" && exit 1)
	@command -v cargo >/dev/null 2>&1 || (echo "❌ Cargo not found" && exit 1)
	@echo "✅ Core dependencies found"
	@command -v nvidia-smi >/dev/null 2>&1 && echo "✅ NVIDIA drivers found" || echo "⚠️ NVIDIA drivers not found"
	@command -v docker >/dev/null 2>&1 && echo "✅ Docker found" || echo "⚠️ Docker not found"

# All-in-one commands
full-test: setup fmt lint test audit coverage
	@echo "✅ Full test suite completed!"

full-build: clean setup fmt lint test build
	@echo "✅ Full build completed!"