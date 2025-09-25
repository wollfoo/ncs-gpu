# Opus GPU - High-Performance GPU Processing System
# Makefile for building, testing, and deploying all components

.PHONY: all build build-rust build-go build-ts test test-rust test-go test-ts clean install deploy benchmark docs help

# Version and build info
VERSION ?= 0.1.0
BUILD_TIME := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
GIT_COMMIT := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
GO_VERSION := $(shell go version | cut -d' ' -f3)
RUST_VERSION := $(shell rustc --version | cut -d' ' -f2)

# Build flags
RUST_BUILD_FLAGS := --release
GO_BUILD_FLAGS := -ldflags "-X main.Version=$(VERSION) -X main.BuildTime=$(BUILD_TIME) -X main.GitCommit=$(GIT_COMMIT)"
TS_BUILD_FLAGS := --build

# Docker settings
DOCKER_REGISTRY ?= localhost:5000
DOCKER_TAG ?= $(VERSION)

# Colors for output
COLOR_GREEN := \033[32m
COLOR_YELLOW := \033[33m
COLOR_RED := \033[31m
COLOR_BLUE := \033[34m
COLOR_RESET := \033[0m

# Default target
all: clean build test

## Build Commands

# Build all components
build: build-rust build-go build-ts
	@echo "$(COLOR_GREEN)✅ All components built successfully$(COLOR_RESET)"

# Build Rust components (scheduler, executor, libs)
build-rust:
	@echo "$(COLOR_BLUE)🦀 Building Rust components...$(COLOR_RESET)"
	cargo build $(RUST_BUILD_FLAGS)
	@echo "$(COLOR_GREEN)✅ Rust build complete$(COLOR_RESET)"

# Build Go components (API gateway)
build-go:
	@echo "$(COLOR_BLUE)🐹 Building Go components...$(COLOR_RESET)"
	@cd control-plane/api-gateway && go build $(GO_BUILD_FLAGS) -o ../../target/api-gateway ./main.go
	@echo "$(COLOR_GREEN)✅ Go build complete$(COLOR_RESET)"

# Build TypeScript SDK
build-ts:
	@echo "$(COLOR_BLUE)📦 Building TypeScript SDK...$(COLOR_RESET)"
	@cd tooling/ts-sdk && npm ci && npm run build
	@echo "$(COLOR_GREEN)✅ TypeScript build complete$(COLOR_RESET)"

## Test Commands

# Run all tests
test: test-rust test-go test-ts
	@echo "$(COLOR_GREEN)✅ All tests passed$(COLOR_RESET)"

# Test Rust components
test-rust:
	@echo "$(COLOR_BLUE)🧪 Running Rust tests...$(COLOR_RESET)"
	cargo test
	@echo "$(COLOR_GREEN)✅ Rust tests passed$(COLOR_RESET)"

# Test Go components
test-go:
	@echo "$(COLOR_BLUE)🧪 Running Go tests...$(COLOR_RESET)"
	@cd control-plane/api-gateway && go test ./...
	@echo "$(COLOR_GREEN)✅ Go tests passed$(COLOR_RESET)"

# Test TypeScript SDK
test-ts:
	@echo "$(COLOR_BLUE)🧪 Running TypeScript tests...$(COLOR_RESET)"
	@cd tooling/ts-sdk && npm test
	@echo "$(COLOR_GREEN)✅ TypeScript tests passed$(COLOR_RESET)"

## Development Commands

# Install dependencies
install:
	@echo "$(COLOR_BLUE)📦 Installing dependencies...$(COLOR_RESET)"
	@echo "Installing Rust dependencies..."
	cargo fetch
	@echo "Installing Go dependencies..."
	@cd control-plane/api-gateway && go mod tidy
	@echo "Installing Node.js dependencies..."
	@cd tooling/ts-sdk && npm ci
	@echo "$(COLOR_GREEN)✅ Dependencies installed$(COLOR_RESET)"

# Format code
fmt:
	@echo "$(COLOR_BLUE)🎨 Formatting code...$(COLOR_RESET)"
	cargo fmt
	@cd control-plane/api-gateway && go fmt ./...
	@cd tooling/ts-sdk && npm run lint:fix
	@echo "$(COLOR_GREEN)✅ Code formatted$(COLOR_RESET)"

# Lint code
lint:
	@echo "$(COLOR_BLUE)🔍 Linting code...$(COLOR_RESET)"
	cargo clippy -- -D warnings
	@cd control-plane/api-gateway && go vet ./...
	@cd tooling/ts-sdk && npm run lint
	@echo "$(COLOR_GREEN)✅ Linting complete$(COLOR_RESET)"

# Clean build artifacts
clean:
	@echo "$(COLOR_BLUE)🧹 Cleaning build artifacts...$(COLOR_RESET)"
	cargo clean
	rm -rf target/
	@cd control-plane/api-gateway && go clean
	@cd tooling/ts-sdk && rm -rf dist/ node_modules/
	@echo "$(COLOR_GREEN)✅ Clean complete$(COLOR_RESET)"

## Docker Commands

# Build Docker images
docker-build:
	@echo "$(COLOR_BLUE)🐳 Building Docker images...$(COLOR_RESET)"
	docker build -t $(DOCKER_REGISTRY)/opus-scheduler:$(DOCKER_TAG) -f docker/Dockerfile.scheduler .
	docker build -t $(DOCKER_REGISTRY)/opus-executor:$(DOCKER_TAG) -f docker/Dockerfile.executor .
	docker build -t $(DOCKER_REGISTRY)/opus-api-gateway:$(DOCKER_TAG) -f docker/Dockerfile.api-gateway .
	@echo "$(COLOR_GREEN)✅ Docker images built$(COLOR_RESET)"

# Push Docker images
docker-push: docker-build
	@echo "$(COLOR_BLUE)🚀 Pushing Docker images...$(COLOR_RESET)"
	docker push $(DOCKER_REGISTRY)/opus-scheduler:$(DOCKER_TAG)
	docker push $(DOCKER_REGISTRY)/opus-executor:$(DOCKER_TAG) 
	docker push $(DOCKER_REGISTRY)/opus-api-gateway:$(DOCKER_TAG)
	@echo "$(COLOR_GREEN)✅ Docker images pushed$(COLOR_RESET)"

## Deployment Commands

# Deploy to development environment
deploy-dev:
	@echo "$(COLOR_BLUE)🚀 Deploying to development...$(COLOR_RESET)"
	kubectl apply -k deployments/dev/
	@echo "$(COLOR_GREEN)✅ Deployed to development$(COLOR_RESET)"

# Deploy to production environment
deploy-prod:
	@echo "$(COLOR_BLUE)🚀 Deploying to production...$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)⚠️ Production deployment requires manual approval$(COLOR_RESET)"
	@read -p "Continue with production deployment? [y/N] " ans && [ $${ans:-N} = y ]
	kubectl apply -k deployments/prod/
	@echo "$(COLOR_GREEN)✅ Deployed to production$(COLOR_RESET)"

## Benchmarking & Performance

# Run performance benchmarks
benchmark:
	@echo "$(COLOR_BLUE)📊 Running performance benchmarks...$(COLOR_RESET)"
	@cd tooling/ts-sdk && npm run benchmark
	cargo bench
	@echo "$(COLOR_GREEN)✅ Benchmarks complete$(COLOR_RESET)"

# Load testing
load-test:
	@echo "$(COLOR_BLUE)⚡ Running load tests...$(COLOR_RESET)"
	@echo "Starting GPU load test..."
	@cd tests/load && ./run_load_test.sh
	@echo "$(COLOR_GREEN)✅ Load test complete$(COLOR_RESET)"

# Stress testing
stress-test:
	@echo "$(COLOR_BLUE)💪 Running stress tests...$(COLOR_RESET)"
	@cd tests/stress && ./run_stress_test.sh
	@echo "$(COLOR_GREEN)✅ Stress test complete$(COLOR_RESET)"

## Documentation

# Generate documentation
docs:
	@echo "$(COLOR_BLUE)📚 Generating documentation...$(COLOR_RESET)"
	cargo doc --no-deps --open
	@cd control-plane/api-gateway && go doc -all > ../../docs/go-api.md
	@cd tooling/ts-sdk && npm run docs
	@echo "$(COLOR_GREEN)✅ Documentation generated$(COLOR_RESET)"

## Utility Commands

# Check system requirements
check-deps:
	@echo "$(COLOR_BLUE)🔍 Checking system dependencies...$(COLOR_RESET)"
	@command -v cargo >/dev/null 2>&1 || { echo "$(COLOR_RED)❌ Rust/Cargo not found$(COLOR_RESET)"; exit 1; }
	@command -v go >/dev/null 2>&1 || { echo "$(COLOR_RED)❌ Go not found$(COLOR_RESET)"; exit 1; }
	@command -v node >/dev/null 2>&1 || { echo "$(COLOR_RED)❌ Node.js not found$(COLOR_RESET)"; exit 1; }
	@command -v npm >/dev/null 2>&1 || { echo "$(COLOR_RED)❌ npm not found$(COLOR_RESET)"; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo "$(COLOR_RED)❌ Docker not found$(COLOR_RESET)"; exit 1; }
	@command -v kubectl >/dev/null 2>&1 || { echo "$(COLOR_YELLOW)⚠️ kubectl not found (deployment disabled)$(COLOR_RESET)"; }
	@echo "$(COLOR_GREEN)✅ All required dependencies found$(COLOR_RESET)"
	@echo "Rust version: $(RUST_VERSION)"
	@echo "Go version: $(GO_VERSION)"
	@echo "Node version: $(shell node --version)"

# Show build info
info:
	@echo "$(COLOR_BLUE)📋 Build Information$(COLOR_RESET)"
	@echo "Version: $(VERSION)"
	@echo "Build Time: $(BUILD_TIME)"
	@echo "Git Commit: $(GIT_COMMIT)"
	@echo "Rust Version: $(RUST_VERSION)"
	@echo "Go Version: $(GO_VERSION)"
	@echo "Node Version: $(shell node --version)"

# Quick setup for new developers
setup: check-deps install build test
	@echo "$(COLOR_GREEN)🎉 Setup complete! You're ready to develop.$(COLOR_RESET)"
	@echo "$(COLOR_BLUE)Next steps:$(COLOR_RESET)"
	@echo "  1. Start infrastructure: docker-compose up -d"
	@echo "  2. Run benchmarks: make benchmark"
	@echo "  3. Check documentation: make docs"

# Show help
help:
	@echo "$(COLOR_BLUE)Opus GPU Build System$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_GREEN)Build Commands:$(COLOR_RESET)"
	@echo "  build        - Build all components"
	@echo "  build-rust   - Build Rust components only"
	@echo "  build-go     - Build Go components only"
	@echo "  build-ts     - Build TypeScript SDK only"
	@echo ""
	@echo "$(COLOR_GREEN)Test Commands:$(COLOR_RESET)"
	@echo "  test         - Run all tests"
	@echo "  test-rust    - Run Rust tests"
	@echo "  test-go      - Run Go tests"
	@echo "  test-ts      - Run TypeScript tests"
	@echo "  benchmark    - Run performance benchmarks"
	@echo "  load-test    - Run load tests"
	@echo "  stress-test  - Run stress tests"
	@echo ""
	@echo "$(COLOR_GREEN)Development Commands:$(COLOR_RESET)"
	@echo "  install      - Install all dependencies"
	@echo "  fmt          - Format code"
	@echo "  lint         - Lint code"
	@echo "  clean        - Clean build artifacts"
	@echo "  docs         - Generate documentation"
	@echo ""
	@echo "$(COLOR_GREEN)Docker Commands:$(COLOR_RESET)"
	@echo "  docker-build - Build Docker images"
	@echo "  docker-push  - Push Docker images"
	@echo ""
	@echo "$(COLOR_GREEN)Deployment Commands:$(COLOR_RESET)"
	@echo "  deploy-dev   - Deploy to development"
	@echo "  deploy-prod  - Deploy to production"
	@echo ""
	@echo "$(COLOR_GREEN)Utility Commands:$(COLOR_RESET)"
	@echo "  check-deps   - Check system dependencies"
	@echo "  info         - Show build information"
	@echo "  setup        - Quick setup for new developers"
	@echo "  help         - Show this help message"

# Set default goal
.DEFAULT_GOAL := help
