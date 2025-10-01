# Makefile cho GPU Mining System
# Build, test và deploy automation

.PHONY: help build test clean docker run stop logs

# Variables
BINARY_NAME := gpu-miner
DOCKER_IMAGE := gpu-miner:latest
RUST_LOG ?= info
CONFIG_FILE ?= config.toml

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

# Default target
help: ## Show this help message
	@echo "$(GREEN)GPU Mining System - Build Automation$(NC)"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "Usage: make [target]"

# Build targets
build: ## Build release binary
	@echo "$(GREEN)Building release binary...$(NC)"
	cargo build --release
	@echo "$(GREEN)✓ Binary built at: target/release/$(BINARY_NAME)$(NC)"

build-debug: ## Build debug binary
	@echo "$(GREEN)Building debug binary...$(NC)"
	cargo build
	@echo "$(GREEN)✓ Debug binary built at: target/debug/$(BINARY_NAME)$(NC)"

# Docker targets
docker-build: ## Build Docker image
	@echo "$(GREEN)Building Docker image...$(NC)"
	docker build -t $(DOCKER_IMAGE) .
	@echo "$(GREEN)✓ Docker image built: $(DOCKER_IMAGE)$(NC)"

docker-run: ## Run Docker container
	@echo "$(GREEN)Starting Docker container...$(NC)"
	@if [ -z "$(WALLET_ADDRESS)" ]; then \
		echo "$(RED)ERROR: WALLET_ADDRESS not set$(NC)"; \
		exit 1; \
	fi
	docker-compose up -d
	@echo "$(GREEN)✓ Container started$(NC)"

docker-stop: ## Stop Docker container
	@echo "$(YELLOW)Stopping Docker container...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Container stopped$(NC)"

docker-logs: ## Show Docker logs
	docker-compose logs -f --tail=100

# Test targets
test: ## Run all tests
	@echo "$(GREEN)Running tests...$(NC)"
	cargo test --all
	@echo "$(GREEN)✓ All tests passed$(NC)"

test-unit: ## Run unit tests only
	@echo "$(GREEN)Running unit tests...$(NC)"
	cargo test --lib
	@echo "$(GREEN)✓ Unit tests passed$(NC)"

test-integration: ## Run integration tests
	@echo "$(GREEN)Running integration tests...$(NC)"
	cargo test --test '*'
	@echo "$(GREEN)✓ Integration tests passed$(NC)"

bench: ## Run benchmarks
	@echo "$(GREEN)Running benchmarks...$(NC)"
	cargo bench
	@echo "$(GREEN)✓ Benchmarks complete$(NC)"

# Development targets
run: ## Run binary locally
	@echo "$(GREEN)Running $(BINARY_NAME)...$(NC)"
	@if [ ! -f "target/release/$(BINARY_NAME)" ]; then \
		$(MAKE) build; \
	fi
	RUST_LOG=$(RUST_LOG) ./target/release/$(BINARY_NAME) --config $(CONFIG_FILE)

dev: ## Run in development mode
	@echo "$(GREEN)Running in development mode...$(NC)"
	RUST_LOG=debug cargo run -- --config $(CONFIG_FILE)

format: ## Format code
	@echo "$(GREEN)Formatting code...$(NC)"
	cargo fmt
	@echo "$(GREEN)✓ Code formatted$(NC)"

lint: ## Run linter
	@echo "$(GREEN)Running linter...$(NC)"
	cargo clippy -- -D warnings
	@echo "$(GREEN)✓ No lint issues$(NC)"

audit: ## Security audit
	@echo "$(GREEN)Running security audit...$(NC)"
	cargo audit
	@echo "$(GREEN)✓ No security issues found$(NC)"

# Monitoring targets
metrics: ## Show current metrics
	@echo "$(GREEN)Fetching metrics...$(NC)"
	@curl -s http://localhost:9090/metrics | grep -E "gpu_|shares_" || echo "$(RED)Metrics endpoint not available$(NC)"

logs: ## Show application logs
	@tail -f logs/gpu-miner.log 2>/dev/null || echo "$(RED)No log file found$(NC)"

gpu-status: ## Show GPU status
	@echo "$(GREEN)GPU Status:$(NC)"
	@nvidia-smi || echo "$(RED)nvidia-smi not available$(NC)"

# Utility targets
clean: ## Clean build artifacts
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	cargo clean
	rm -rf logs/*.log
	@echo "$(GREEN)✓ Cleaned$(NC)"

clean-docker: ## Clean Docker artifacts
	@echo "$(YELLOW)Cleaning Docker artifacts...$(NC)"
	docker-compose down -v
	docker rmi $(DOCKER_IMAGE) 2>/dev/null || true
	@echo "$(GREEN)✓ Docker artifacts cleaned$(NC)"

install-deps: ## Install dependencies
	@echo "$(GREEN)Installing dependencies...$(NC)"
	@which cargo >/dev/null 2>&1 || (echo "$(RED)Cargo not found. Please install Rust$(NC)" && exit 1)
	@which docker >/dev/null 2>&1 || (echo "$(RED)Docker not found. Please install Docker$(NC)" && exit 1)
	@which nvidia-smi >/dev/null 2>&1 || (echo "$(YELLOW)WARNING: nvidia-smi not found$(NC)")
	cargo fetch
	@echo "$(GREEN)✓ Dependencies ready$(NC)"

setup: install-deps ## Initial setup
	@echo "$(GREEN)Setting up project...$(NC)"
	@if [ ! -f "$(CONFIG_FILE)" ]; then \
		cp config.toml.example $(CONFIG_FILE); \
		echo "$(YELLOW)Created $(CONFIG_FILE) from template$(NC)"; \
		echo "$(YELLOW)Please edit $(CONFIG_FILE) with your settings$(NC)"; \
	fi
	@mkdir -p logs
	@echo "$(GREEN)✓ Setup complete$(NC)"

# Release targets
release: ## Build optimized release
	@echo "$(GREEN)Building optimized release...$(NC)"
	cargo build --release
	strip target/release/$(BINARY_NAME)
	@ls -lh target/release/$(BINARY_NAME)
	@echo "$(GREEN)✓ Release binary ready$(NC)"

package: release ## Create distribution package
	@echo "$(GREEN)Creating distribution package...$(NC)"
	@mkdir -p dist
	cp target/release/$(BINARY_NAME) dist/
	cp config.toml.example dist/
	cp README.md dist/
	tar -czf gpu-miner-$(shell git describe --tags --always).tar.gz -C dist .
	@echo "$(GREEN)✓ Package created: gpu-miner-$(shell git describe --tags --always).tar.gz$(NC)"

# CI/CD targets
ci: format lint test audit ## Run CI pipeline
	@echo "$(GREEN)✓ CI pipeline passed$(NC)"

.PHONY: version
version: ## Show version info
	@echo "$(GREEN)Version Information:$(NC)"
	@cargo version
	@rustc --version
	@docker --version 2>/dev/null || echo "Docker not installed"
	@nvidia-smi --version 2>/dev/null | head -1 || echo "NVIDIA driver not installed"
