# OPUS-GPU Scheduler Makefile
# Go Scheduler for GPU Task Orchestration

.PHONY: all build test clean run deps fmt lint

# Variables
BINARY_NAME=opus-scheduler
MAIN_PATH=cmd/scheduler
BUILD_DIR=build
GOFLAGS=-v

# Build targets
all: deps fmt lint test build

deps:
	@echo "📦 Downloading dependencies..."
	go mod download
	go mod tidy

build:
	@echo "🔨 Building scheduler..."
	@mkdir -p $(BUILD_DIR)
	CGO_ENABLED=1 go build $(GOFLAGS) -o $(BUILD_DIR)/$(BINARY_NAME) ./$(MAIN_PATH)
	@echo "✅ Build complete: $(BUILD_DIR)/$(BINARY_NAME)"

build-static:
	@echo "🔨 Building static binary..."
	@mkdir -p $(BUILD_DIR)
	CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -ldflags '-extldflags "-static"' \
		-o $(BUILD_DIR)/$(BINARY_NAME)-static ./$(MAIN_PATH)

test:
	@echo "🧪 Running tests..."
	go test -v -race -coverprofile=coverage.out ./...
	@echo "📊 Coverage report:"
	@go tool cover -func=coverage.out

test-integration:
	@echo "🧪 Running integration tests..."
	go test -v -tags=integration ./tests/...

bench:
	@echo "⚡ Running benchmarks..."
	go test -bench=. -benchmem ./...

run: build
	@echo "🚀 Starting scheduler..."
	./$(BUILD_DIR)/$(BINARY_NAME) -config=config.yaml

run-dev:
	@echo "🚀 Starting scheduler in dev mode..."
	go run ./$(MAIN_PATH) -config=config.yaml

fmt:
	@echo "🎨 Formatting code..."
	go fmt ./...
	gofmt -s -w .

lint:
	@echo "🔍 Running linter..."
	@which golangci-lint > /dev/null || (echo "Installing golangci-lint..." && \
		go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest)
	golangci-lint run ./...

vet:
	@echo "🔍 Running go vet..."
	go vet ./...

clean:
	@echo "🧹 Cleaning..."
	@rm -rf $(BUILD_DIR)
	@rm -f coverage.out
	@rm -f *.prof
	@go clean -testcache

docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t opus-gpu/scheduler:latest -f Dockerfile .

docker-run:
	@echo "🐳 Running in Docker..."
	docker run --rm \
		--gpus all \
		-v $(PWD)/config.yaml:/app/config.yaml \
		-p 8080:8080 \
		opus-gpu/scheduler:latest

# Development helpers
watch:
	@echo "👀 Watching for changes..."
	@which air > /dev/null || go install github.com/cosmtrek/air@latest
	air -c .air.toml

proto:
	@echo "🔧 Generating protobuf code..."
	protoc --go_out=. --go_opt=paths=source_relative \
		--go-grpc_out=. --go-grpc_opt=paths=source_relative \
		api/proto/*.proto

mod-update:
	@echo "📦 Updating dependencies..."
	go get -u ./...
	go mod tidy

security:
	@echo "🔒 Running security scan..."
	@which gosec > /dev/null || go install github.com/securego/gosec/v2/cmd/gosec@latest
	gosec ./...

profile-cpu:
	@echo "📈 Profiling CPU..."
	go test -cpuprofile=cpu.prof -bench=.
	go tool pprof cpu.prof

profile-mem:
	@echo "📈 Profiling Memory..."
	go test -memprofile=mem.prof -bench=.
	go tool pprof mem.prof

# Help
help:
	@echo "OPUS-GPU Scheduler - Available targets:"
	@echo ""
	@echo "  make build        - Build the scheduler binary"
	@echo "  make test         - Run unit tests"
	@echo "  make run          - Build and run the scheduler"
	@echo "  make clean        - Clean build artifacts"
	@echo "  make docker-build - Build Docker image"
	@echo "  make fmt          - Format code"
	@echo "  make lint         - Run linter"
	@echo "  make help         - Show this help message"
