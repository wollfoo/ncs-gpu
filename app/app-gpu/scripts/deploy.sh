#!/bin/bash
# OPUS-GPU v2.0 Deployment Script
# Production deployment with safety checks

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOYMENT_ENV="${1:-production}"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi

    # Check NVIDIA Docker Runtime
    if ! docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
        log_error "NVIDIA Docker runtime is not configured properly"
        exit 1
    fi

    # Check Rust (for local builds)
    if ! command -v cargo &> /dev/null; then
        log_warn "Cargo not found, will use Docker build only"
    fi

    log_info "Prerequisites check passed"
}

build_application() {
    log_info "Building OPUS-GPU application..."

    cd "$PROJECT_ROOT"

    # Build with Docker
    if [ "$DEPLOYMENT_ENV" == "production" ]; then
        docker build -t opus-gpu:2.0.0 -f Dockerfile .
    else
        docker build -t opus-gpu:2.0.0-dev -f Dockerfile.dev .
    fi

    log_info "Build completed successfully"
}

generate_config() {
    log_info "Generating configuration..."

    CONFIG_FILE="$PROJECT_ROOT/configs/config.toml"

    if [ ! -f "$CONFIG_FILE" ]; then
        cp "$PROJECT_ROOT/configs/config.toml.template" "$CONFIG_FILE"

        # Generate secure token
        AUTH_TOKEN=$(openssl rand -hex 32)
        sed -i "s/GENERATE_SECURE_TOKEN/$AUTH_TOKEN/g" "$CONFIG_FILE"

        log_warn "Configuration created at $CONFIG_FILE"
        log_warn "Please update pool settings and wallet address"
    else
        log_info "Configuration already exists"
    fi
}

setup_monitoring() {
    log_info "Setting up monitoring stack..."

    # Create monitoring directories
    mkdir -p "$PROJECT_ROOT/monitoring/dashboards"
    mkdir -p "$PROJECT_ROOT/monitoring/provisioning/datasources"
    mkdir -p "$PROJECT_ROOT/monitoring/provisioning/dashboards"

    # Create Prometheus configuration
    cat > "$PROJECT_ROOT/monitoring/prometheus.yml" <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'opus-gpu'
    static_configs:
      - targets: ['opus-gpu:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
EOF

    # Create Grafana datasource
    cat > "$PROJECT_ROOT/monitoring/provisioning/datasources/prometheus.yml" <<EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
EOF

    log_info "Monitoring configuration created"
}

deploy_services() {
    log_info "Deploying services..."

    cd "$PROJECT_ROOT"

    # Start services
    if [ "$DEPLOYMENT_ENV" == "production" ]; then
        docker-compose up -d
    else
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
    fi

    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    sleep 10

    # Check service status
    docker-compose ps

    log_info "Services deployed successfully"
}

run_health_checks() {
    log_info "Running health checks..."

    # Check OPUS-GPU API
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        log_info "OPUS-GPU API: Healthy"
    else
        log_error "OPUS-GPU API: Not responding"
    fi

    # Check Prometheus
    if curl -f http://localhost:9091/api/v1/query?query=up > /dev/null 2>&1; then
        log_info "Prometheus: Healthy"
    else
        log_warn "Prometheus: Not responding"
    fi

    # Check Grafana
    if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
        log_info "Grafana: Healthy"
    else
        log_warn "Grafana: Not responding"
    fi
}

print_summary() {
    echo ""
    echo "=================================="
    echo "OPUS-GPU v2.0 Deployment Complete"
    echo "=================================="
    echo ""
    echo "Services:"
    echo "  - API: http://localhost:8080"
    echo "  - Metrics: http://localhost:9090"
    echo "  - Grafana: http://localhost:3000 (admin/admin)"
    echo "  - Prometheus: http://localhost:9091"
    echo ""
    echo "Next steps:"
    echo "  1. Update configuration in configs/config.toml"
    echo "  2. Monitor logs: docker-compose logs -f opus-gpu"
    echo "  3. Check GPU status: docker exec opus-gpu-main opus-gpu diagnose"
    echo ""
}

# Main execution
main() {
    log_info "Starting OPUS-GPU deployment for $DEPLOYMENT_ENV environment"

    check_prerequisites
    build_application
    generate_config
    setup_monitoring
    deploy_services
    run_health_checks
    print_summary

    log_info "Deployment completed successfully!"
}

# Run main function
main "$@"