#!/bin/bash
#
# OPUS-GPU Production Deployment Script
#
# Usage: ./deploy.sh [docker|k8s|systemd] [options]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Banner
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 OPUS-GPU Production Deployment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get deployment target
DEPLOY_TARGET=${1:-"docker"}
PROJECT_ROOT="/home/azureuser/opus-gpu/app/app-gpu"

cd "$PROJECT_ROOT"

# Pre-flight checks
log_info "Running pre-flight checks..."

# Check if binaries exist
if [ ! -f "target/release/gpu-miner" ]; then
    log_warning "Binary not found. Building..."
    cargo build --release --features nvml
fi

# Check GPU availability (optional - warn only)
if ! command -v nvidia-smi &> /dev/null; then
    log_warning "nvidia-smi not found. GPU may not be available."
else
    log_success "NVIDIA GPU detected"
    nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
fi

# Check deployment method
case $DEPLOY_TARGET in
    docker)
        log_info "Deploying with Docker Compose..."

        # Check Docker
        if ! command -v docker &> /dev/null; then
            log_error "Docker not installed"
            exit 1
        fi

        # Check docker-compose
        if ! command -v docker-compose &> /dev/null; then
            log_error "docker-compose not installed"
            exit 1
        fi

        # Build image
        log_info "Building Docker image..."
        docker build -t opus-gpu:latest . || {
            log_error "Docker build failed"
            exit 1
        }

        # Deploy stack
        log_info "Starting Docker Compose stack..."
        cd gpu-tools/deploy/docker
        docker-compose up -d || {
            log_error "Docker Compose failed"
            exit 1
        }

        # Wait for services
        log_info "Waiting for services to start..."
        sleep 5

        # Verify
        if docker-compose ps | grep -q "Up"; then
            log_success "Docker deployment successful"

            echo ""
            log_info "Access endpoints:"
            echo "  • API: http://localhost:8080"
            echo "  • Metrics: http://localhost:8080/metrics"
            echo "  • Grafana: http://localhost:3000 (admin/admin)"
            echo "  • Prometheus: http://localhost:9091"

            echo ""
            log_info "Useful commands:"
            echo "  • Logs: docker-compose logs -f miner"
            echo "  • Status: docker-compose ps"
            echo "  • Stop: docker-compose down"
        else
            log_error "Services not running properly"
            docker-compose ps
            exit 1
        fi
        ;;

    k8s|kubernetes)
        log_info "Deploying to Kubernetes..."

        # Check kubectl
        if ! command -v kubectl &> /dev/null; then
            log_error "kubectl not installed"
            exit 1
        fi

        # Check cluster connection
        if ! kubectl cluster-info &> /dev/null; then
            log_error "Cannot connect to Kubernetes cluster"
            exit 1
        fi

        # Apply manifests
        log_info "Applying Kubernetes manifests..."
        kubectl apply -f gpu-tools/deploy/k8s/ || {
            log_error "Kubernetes deployment failed"
            exit 1
        }

        # Wait for rollout
        log_info "Waiting for deployment..."
        kubectl rollout status deployment/opus-gpu-miner -n opus-gpu --timeout=5m || {
            log_error "Deployment rollout failed"
            exit 1
        }

        log_success "Kubernetes deployment successful"

        echo ""
        log_info "Useful commands:"
        echo "  • Logs: kubectl logs -f deployment/opus-gpu-miner -n opus-gpu"
        echo "  • Status: kubectl get pods -n opus-gpu"
        echo "  • Port-forward: kubectl port-forward -n opus-gpu deployment/opus-gpu-miner 8080:8080"
        ;;

    systemd)
        log_info "Deploying with Systemd..."

        # Check if running as root
        if [ "$EUID" -ne 0 ]; then
            log_error "Systemd deployment requires sudo"
            exit 1
        fi

        # Install binaries
        log_info "Installing binaries..."
        install -m 755 target/release/gpu-miner /usr/local/bin/
        install -m 755 gpu-tools/bin/gpu-ctl /usr/local/bin/ || {
            log_warning "gpu-ctl not found, skipping"
        }

        # Create system user
        if ! id -u miner &> /dev/null; then
            log_info "Creating miner user..."
            useradd -r -s /bin/false -m -d /opt/opus-gpu miner
        fi

        # Setup directories
        log_info "Setting up directories..."
        mkdir -p /opt/opus-gpu/{config,plugins,logs}
        mkdir -p /etc/opus-gpu

        # Copy config
        cp config/app.toml /etc/opus-gpu/
        chown -R miner:miner /opt/opus-gpu /etc/opus-gpu

        # Install systemd units
        log_info "Installing systemd services..."
        cp gpu-tools/deploy/systemd/opus-gpu.service /etc/systemd/system/
        cp gpu-tools/deploy/systemd/opus-gpu-watchdog.service /etc/systemd/system/ || {
            log_warning "Watchdog service not found, skipping"
        }

        # Reload systemd
        systemctl daemon-reload

        # Enable and start
        systemctl enable opus-gpu
        systemctl start opus-gpu

        # Wait for startup
        sleep 3

        # Verify
        if systemctl is-active --quiet opus-gpu; then
            log_success "Systemd deployment successful"

            echo ""
            log_info "Useful commands:"
            echo "  • Status: systemctl status opus-gpu"
            echo "  • Logs: journalctl -u opus-gpu -f"
            echo "  • Restart: systemctl restart opus-gpu"
        else
            log_error "Service not running"
            systemctl status opus-gpu
            exit 1
        fi
        ;;

    *)
        log_error "Unknown deployment target: $DEPLOY_TARGET"
        echo "Usage: $0 [docker|k8s|systemd]"
        exit 1
        ;;
esac

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_success "Deployment complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
