.PHONY: help build test clean run docker bench fmt lint audit

# Variables
CARGO = cargo
DOCKER = docker
PROJECT_NAME = opus-gpu
VERSION = $(shell grep version core/Cargo.toml | head -1 | cut -d'"' -f2)

# Colors for output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[0;33m
NC = \033[0m # No Color

help: ## Show this help message
	@echo "OPUS-GPU v2.0 Build System"
	@echo "=========================="
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

# Development
build: ## Build the project in debug mode
	@echo "$(GREEN)Building OPUS-GPU...$(NC)"
	$(CARGO) build
	@echo "$(GREEN)✅ Build complete$(NC)"

release: ## Build the project in release mode
	@echo "$(GREEN)Building OPUS-GPU (release)...$(NC)"
	$(CARGO) build --release
	@strip target/release/opus-gpu
	@echo "$(GREEN)✅ Release build complete$(NC)"

test: ## Run all tests
	@echo "$(YELLOW)Running tests...$(NC)"
	$(CARGO) test --all --verbose

test-coverage: ## Run tests with coverage
	@echo "$(YELLOW)Running tests with coverage...$(NC)"
	$(CARGO) tarpaulin --out Html --output-dir coverage
	@echo "$(GREEN)✅ Coverage report generated in coverage/index.html$(NC)"

bench: ## Run benchmarks
	@echo "$(YELLOW)Running benchmarks...$(NC)"
	$(CARGO) bench

run: ## Run the application
	@echo "$(GREEN)Starting OPUS-GPU...$(NC)"
	RUST_LOG=info $(CARGO) run

clean: ## Clean build artifacts
	@echo "$(YELLOW)Cleaning...$(NC)"
	$(CARGO) clean
	rm -rf coverage/
	@echo "$(GREEN)✅ Clean complete$(NC)"

# Code quality
fmt: ## Format code
	@echo "$(YELLOW)Formatting code...$(NC)"
	$(CARGO) fmt --all
	@echo "$(GREEN)✅ Code formatted$(NC)"

fmt-check: ## Check code formatting
	@echo "$(YELLOW)Checking code format...$(NC)"
	$(CARGO) fmt --all -- --check

lint: ## Run clippy linter
	@echo "$(YELLOW)Running clippy...$(NC)"
	$(CARGO) clippy --all-targets --all-features -- -D warnings

audit: ## Security audit
	@echo "$(YELLOW)Running security audit...$(NC)"
	$(CARGO) audit

# Docker
docker-build: ## Build Docker image
	@echo "$(GREEN)Building Docker image...$(NC)"
	$(DOCKER) build -t $(PROJECT_NAME):$(VERSION) .
	$(DOCKER) tag $(PROJECT_NAME):$(VERSION) $(PROJECT_NAME):latest
	@echo "$(GREEN)✅ Docker image built: $(PROJECT_NAME):$(VERSION)$(NC)"

docker-run: ## Run Docker container
	@echo "$(GREEN)Running Docker container...$(NC)"
	$(DOCKER) run --gpus all \
		-p 9090:9090 \
		-v $(PWD)/config:/app/config \
		--name $(PROJECT_NAME) \
		$(PROJECT_NAME):latest

docker-stop: ## Stop Docker container
	@echo "$(YELLOW)Stopping Docker container...$(NC)"
	$(DOCKER) stop $(PROJECT_NAME)
	$(DOCKER) rm $(PROJECT_NAME)

docker-push: ## Push Docker image to registry
	@echo "$(GREEN)Pushing Docker image...$(NC)"
	$(DOCKER) push $(PROJECT_NAME):$(VERSION)
	$(DOCKER) push $(PROJECT_NAME):latest

# Installation
install: release ## Install the binary
	@echo "$(GREEN)Installing OPUS-GPU...$(NC)"
	sudo cp target/release/opus-gpu /usr/local/bin/
	sudo chmod +x /usr/local/bin/opus-gpu
	@echo "$(GREEN)✅ OPUS-GPU installed to /usr/local/bin/$(NC)"

uninstall: ## Uninstall the binary
	@echo "$(YELLOW)Uninstalling OPUS-GPU...$(NC)"
	sudo rm -f /usr/local/bin/opus-gpu
	@echo "$(GREEN)✅ OPUS-GPU uninstalled$(NC)"

# CI/CD
ci: fmt-check lint test ## Run CI checks
	@echo "$(GREEN)✅ All CI checks passed$(NC)"

pre-commit: fmt lint test ## Pre-commit hook
	@echo "$(GREEN)✅ Pre-commit checks passed$(NC)"

# Documentation
docs: ## Generate documentation
	@echo "$(YELLOW)Generating documentation...$(NC)"
	$(CARGO) doc --no-deps --open

# Utilities
version: ## Show version
	@echo "OPUS-GPU version: $(VERSION)"

deps: ## Update dependencies
	@echo "$(YELLOW)Updating dependencies...$(NC)"
	$(CARGO) update
	@echo "$(GREEN)✅ Dependencies updated$(NC)"

check: ## Check if project compiles
	@echo "$(YELLOW)Checking compilation...$(NC)"
	$(CARGO) check --all
	@echo "$(GREEN)✅ Compilation check passed$(NC)"

watch: ## Watch for changes and rebuild
	@echo "$(YELLOW)Watching for changes...$(NC)"
	$(CARGO) watch -x build

# Complete workflow
all: clean fmt lint test release docker-build ## Complete build pipeline
	@echo "$(GREEN)✅ Complete build pipeline finished$(NC)"
	@echo ""
	@echo "Binary: target/release/opus-gpu"
	@echo "Docker: $(PROJECT_NAME):$(VERSION)"
