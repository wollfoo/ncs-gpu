# Makefile cho GPU Mining System với Obfuscation Support
# Triển khai build automation và deployment workflows

.PHONY: all build clean test bench deploy obfuscate verify help

# Default target
all: build

# Standard release build
build:
	@echo "🔧 Building standard release..."
	cargo build --release

# Clean build artifacts
clean:
	@echo "🧹 Cleaning build artifacts..."
	cargo clean
	rm -rf target/release-obfuscated
	rm -f obfuscation-report.md

# Run tests
test: build
	@echo "🧪 Running tests..."
	cargo test

# Run benchmark
bench: build
	@echo "⚡ Running benchmark..."
	cargo run --release -- --benchmark

# Build obfuscated binary with all obfuscation techniques
obfuscate:
	@echo "🔒 Building obfuscated binary..."
	./scripts/build-obfuscated.sh

# Verify deployment readiness
verify:
	@echo "🔍 Verifying deployment..."
	./scripts/verify-deployment.sh

# Deploy obfuscated binary
deploy: obfuscate verify
	@echo "🚀 Deploying obfuscated binary..."
	./scripts/deploy.sh

# Install development dependencies
setup-dev:
	@echo "🎯 Setting up development environment..."
	cargo install cargo-audit cargo-outdated
	@echo "⚡ Install UPX for binary packing:"
	@echo "   Ubuntu/Debian: sudo apt install upx"
	@echo "   macOS: brew install upx"
	@echo "   Or download from: https://upx.github.io/"

# Security audit
audit:
	@echo "🔐 Running security audit..."
	cargo audit

# Performance comparison
perf-compare: build obfuscate
	@echo "📊 Comparing performance..."
	@echo "Standard build:"
	@ls -lh target/release/gpu-miner
	@echo "Obfuscated build:"
	@ls -lh target/release-obfuscated/gpu-miner

# Development workflow
dev: clean build test bench
	@echo "💻 Development workflow complete"

# Production workflow
prod: obfuscate verify audit
	@echo "🏭 Production build complete"

# Container build
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t gpu-miner:obfuscated .

# Container run
docker-run: docker-build
	@echo "🐳 Running in container..."
	docker run --rm --gpus all gpu-miner:obfuscated --benchmark

# Help
help:
	@echo "GPU Mining System - Obfuscation Build System"
	@echo ""
	@echo "Available targets:"
	@echo "  build      - Build standard release version"
	@echo "  obfuscate  - Build với obfuscation nâng cao"
	@echo "  clean      - Clean tất cả build artifacts"
	@echo "  test       - Run test suite"
	@echo "  bench      - Run performance benchmark"
	@echo "  verify     - Verify deployment readiness"
	@echo "  deploy     - Deploy obfuscated binary"
	@echo "  audit      - Run security audit"
	@echo "  perf-compare - Compare standard vs obfuscated builds"
	@echo "  setup-dev  - Setup development environment"
	@echo "  dev        - Full development workflow"
	@echo "  prod       - Full production build workflow"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run  - Run in Docker container"
	@echo ""
	@echo "Examples:"
	@echo "  make prod          # Build for production"
	@echo "  make perf-compare  # Compare performance"
	@echo "  make deploy        # Deploy obfuscated version"