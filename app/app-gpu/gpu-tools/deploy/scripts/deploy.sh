#!/bin/bash
#
# OPUS-GPU Deployment Script
# Supports: docker, kubernetes (k8s), systemd
#
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$DEPLOY_ROOT/../.." && pwd)"

# Deployment target
TARGET="${1:-}"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

show_usage() {
    cat <<EOF
OPUS-GPU Deployment Script

Usage: $0 <target>

Targets:
  docker    - Deploy using Docker Compose
  k8s       - Deploy to Kubernetes cluster
  systemd   - Deploy as systemd service (requires sudo)
  help      - Show this help message

Environment Variables:
  DOCKER_TAG         - Docker image tag (default: opus-gpu:latest)
  K8S_NAMESPACE      - Kubernetes namespace (default: opus-gpu)
  SYSTEMD_USER       - Systemd service user (default: miner)

Examples:
  $0 docker                  # Deploy with Docker Compose
  $0 k8s                     # Deploy to Kubernetes
  sudo $0 systemd            # Deploy as systemd service

EOF
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_warning "docker-compose not found, trying docker compose plugin..."
        if ! docker compose version &> /dev/null; then
            log_error "Neither docker-compose nor docker compose plugin found"
            exit 1
        fi
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi
}

deploy_docker() {
    log_info "Deploying OPUS-GPU with Docker Compose..."

    check_docker

    cd "$DEPLOY_ROOT/docker"

    # Check if docker-compose.yml exists
    if [ ! -f "docker-compose.yml" ]; then
        log_error "docker-compose.yml not found"
        exit 1
    fi

    # Create config directory if it doesn't exist
    if [ ! -d "config" ]; then
        log_warning "Config directory not found, creating..."
        mkdir -p config

        # Copy default config
        if [ -f "$PROJECT_ROOT/config/app.toml" ]; then
            cp "$PROJECT_ROOT/config/app.toml" config/
            log_success "Copied default configuration"
        fi
    fi

    # Pull/build images
    log_info "Pulling/building Docker images..."
    $COMPOSE_CMD build

    # Start services
    log_info "Starting services..."
    $COMPOSE_CMD up -d

    # Show status
    log_info "Waiting for services to start..."
    sleep 5

    $COMPOSE_CMD ps

    log_success "Docker Compose deployment completed!"
    log_info "Services running:"
    log_info "  - Miner:      http://localhost:8080"
    log_info "  - Metrics:    http://localhost:9090"
    log_info "  - Prometheus: http://localhost:9091"
    log_info "  - Grafana:    http://localhost:3000 (admin/admin)"

    log_info ""
    log_info "View logs: $COMPOSE_CMD logs -f miner"
    log_info "Stop services: $COMPOSE_CMD down"
}

check_kubernetes() {
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi

    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi

    log_success "Connected to Kubernetes cluster"
}

deploy_kubernetes() {
    log_info "Deploying OPUS-GPU to Kubernetes..."

    check_kubernetes

    cd "$DEPLOY_ROOT/k8s"

    local namespace="${K8S_NAMESPACE:-opus-gpu}"

    # Create namespace
    log_info "Creating namespace: $namespace..."
    kubectl apply -f namespace.yaml

    # Apply ConfigMap
    log_info "Applying ConfigMap..."
    kubectl apply -f configmap.yaml -n "$namespace"

    # Apply Secret (with warning)
    log_warning "Applying Secret (REMEMBER TO UPDATE IN PRODUCTION)..."
    kubectl apply -f secret.yaml -n "$namespace"

    # Apply Deployment
    log_info "Applying Deployment..."
    kubectl apply -f deployment.yaml -n "$namespace"

    # Apply Service
    log_info "Applying Service..."
    kubectl apply -f service.yaml -n "$namespace"

    # Wait for deployment
    log_info "Waiting for deployment to be ready..."
    kubectl rollout status deployment/opus-gpu-miner -n "$namespace" --timeout=5m

    # Show status
    log_info "Deployment status:"
    kubectl get all -n "$namespace"

    log_success "Kubernetes deployment completed!"
    log_info ""
    log_info "Useful commands:"
    log_info "  View pods:    kubectl get pods -n $namespace"
    log_info "  View logs:    kubectl logs -f deployment/opus-gpu-miner -n $namespace"
    log_info "  Port forward: kubectl port-forward svc/opus-gpu-miner 8080:8080 -n $namespace"
    log_info "  Exec shell:   kubectl exec -it deployment/opus-gpu-miner -n $namespace -- /bin/bash"
}

check_systemd() {
    if ! command -v systemctl &> /dev/null; then
        log_error "systemctl is not available (not a systemd system?)"
        exit 1
    fi

    if [ "$EUID" -ne 0 ]; then
        log_error "Systemd deployment requires root privileges"
        log_error "Please run with: sudo $0 systemd"
        exit 1
    fi
}

deploy_systemd() {
    log_info "Deploying OPUS-GPU as systemd service..."

    check_systemd

    local service_user="${SYSTEMD_USER:-miner}"

    # Create user if it doesn't exist
    if ! id "$service_user" &> /dev/null; then
        log_info "Creating user: $service_user..."
        useradd -m -s /bin/bash "$service_user"
        log_success "User created"
    fi

    # Create directories
    log_info "Creating directories..."
    mkdir -p /opt/opus-gpu/{bin,config,data}
    mkdir -p /var/log/opus-gpu
    mkdir -p /etc/opus-gpu

    # Copy binaries
    log_info "Copying binaries..."

    if [ -f "$PROJECT_ROOT/target/release/gpu-miner" ]; then
        cp "$PROJECT_ROOT/target/release/gpu-miner" /usr/local/bin/
        chmod +x /usr/local/bin/gpu-miner
        log_success "Copied gpu-miner"
    else
        log_error "gpu-miner binary not found. Please run build.sh first."
        exit 1
    fi

    if [ -d "$PROJECT_ROOT/gpu-tools/bin" ]; then
        cp "$PROJECT_ROOT/gpu-tools/bin"/* /usr/local/bin/
        chmod +x /usr/local/bin/gpu-*
        log_success "Copied GPU tools"
    fi

    # Copy configuration
    log_info "Copying configuration..."
    if [ -d "$PROJECT_ROOT/config" ]; then
        cp -r "$PROJECT_ROOT/config"/* /etc/opus-gpu/
        log_success "Copied configuration files"
    fi

    # Set permissions
    log_info "Setting permissions..."
    chown -R "$service_user:$service_user" /opt/opus-gpu /var/log/opus-gpu /etc/opus-gpu
    chmod 750 /opt/opus-gpu /var/log/opus-gpu
    chmod 640 /etc/opus-gpu/*.toml

    # Copy systemd service files
    log_info "Installing systemd service files..."
    cp "$DEPLOY_ROOT/systemd/opus-gpu.service" /etc/systemd/system/
    cp "$DEPLOY_ROOT/systemd/opus-gpu-watchdog.service" /etc/systemd/system/

    # Reload systemd
    log_info "Reloading systemd daemon..."
    systemctl daemon-reload

    # Enable services
    log_info "Enabling services..."
    systemctl enable opus-gpu.service
    systemctl enable opus-gpu-watchdog.service

    # Start services
    log_info "Starting services..."
    systemctl start opus-gpu.service
    systemctl start opus-gpu-watchdog.service

    # Show status
    sleep 2
    log_info "Service status:"
    systemctl status opus-gpu.service --no-pager

    log_success "Systemd deployment completed!"
    log_info ""
    log_info "Useful commands:"
    log_info "  Status:  systemctl status opus-gpu"
    log_info "  Logs:    journalctl -u opus-gpu -f"
    log_info "  Stop:    systemctl stop opus-gpu"
    log_info "  Restart: systemctl restart opus-gpu"
}

# Main execution
main() {
    case "$TARGET" in
        docker)
            deploy_docker
            ;;
        k8s|kubernetes)
            deploy_kubernetes
            ;;
        systemd)
            deploy_systemd
            ;;
        help|--help|-h)
            show_usage
            exit 0
            ;;
        "")
            log_error "No deployment target specified"
            show_usage
            exit 1
            ;;
        *)
            log_error "Unknown deployment target: $TARGET"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main
