#!/bin/bash
# Deployment script for OPUS-GPU
# Supports: docker-compose, systemd, kubernetes

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ============================================================================
# Docker Compose Deployment
# ============================================================================
deploy_docker_compose() {
    echo -e "${YELLOW}Deploying với Docker Compose...${NC}"

    cd "$ROOT_DIR/deploy/docker"

    # Check .env file
    if [ ! -f ".env" ]; then
        echo -e "${RED}Error: .env file not found${NC}"
        echo "Creating template .env file..."
        cat > .env <<EOF
# InfluxDB Configuration
INFLUXDB_TOKEN=your-secret-token-here
INFLUXDB_PASSWORD=admin-password
INFLUXDB_ORG=opus-gpu
INFLUXDB_BUCKET=metrics

# Grafana Configuration
GRAFANA_PASSWORD=admin-password

# Miner Configuration
MINER_WALLET=0xYourWalletAddress
MINER_POOL=stratum+tcp://pool.example.com:3333
EOF
        echo -e "${YELLOW}Please edit .env file and run again${NC}"
        exit 1
    fi

    # Pull latest images
    docker-compose pull

    # Build custom images
    docker-compose build

    # Start services
    docker-compose up -d

    # Wait for services
    echo "Waiting for services to be ready..."
    sleep 10

    # Check health
    docker-compose ps

    echo -e "${GREEN}✓ Deployment completed${NC}"
    echo ""
    echo "Services:"
    echo "  Miner HTTP API:    http://localhost:8080"
    echo "  Grafana Dashboard: http://localhost:3000"
    echo "  InfluxDB:          http://localhost:8086"
    echo "  Prometheus:        http://localhost:9093"
}

# ============================================================================
# Systemd Deployment
# ============================================================================
deploy_systemd() {
    echo -e "${YELLOW}Deploying với systemd...${NC}"

    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}Error: systemd deployment requires root${NC}"
        exit 1
    fi

    # Copy binaries
    echo "Installing binaries..."
    cp "$ROOT_DIR/build/bin/gpu-miner" /usr/local/bin/
    cp "$ROOT_DIR/build/bin/gpu-ctl" /usr/local/bin/
    cp "$ROOT_DIR/build/bin/gpu-watchdog" /usr/local/bin/
    cp "$ROOT_DIR/build/bin/metrics-aggregator" /usr/local/bin/

    chmod +x /usr/local/bin/gpu-*

    # Create systemd service files
    cat > /etc/systemd/system/gpu-watchdog.service <<'EOF'
[Unit]
Description=OPUS-GPU Miner Watchdog
After=network.target

[Service]
Type=simple
User=miner
Group=miner
ExecStart=/usr/local/bin/gpu-watchdog --config /etc/miner/config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    cat > /etc/systemd/system/metrics-aggregator.service <<'EOF'
[Unit]
Description=OPUS-GPU Metrics Aggregator
After=network.target gpu-watchdog.service

[Service]
Type=simple
User=miner
Group=miner
ExecStart=/usr/local/bin/metrics-aggregator --config /etc/miner/aggregator.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Create miner user if not exists
    if ! id -u miner > /dev/null 2>&1; then
        useradd -m -s /bin/bash miner
    fi

    # Create directories
    mkdir -p /etc/miner /var/log/miner /var/run/miner
    chown -R miner:miner /etc/miner /var/log/miner /var/run/miner

    # Reload systemd
    systemctl daemon-reload

    # Enable and start services
    systemctl enable gpu-watchdog metrics-aggregator
    systemctl start gpu-watchdog metrics-aggregator

    # Check status
    systemctl status gpu-watchdog metrics-aggregator --no-pager

    echo -e "${GREEN}✓ Systemd deployment completed${NC}"
}

# ============================================================================
# Kubernetes Deployment
# ============================================================================
deploy_kubernetes() {
    echo -e "${YELLOW}Deploying to Kubernetes...${NC}"

    cd "$ROOT_DIR/deploy/k8s"

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}Error: kubectl not found${NC}"
        exit 1
    fi

    # Apply manifests
    kubectl apply -f namespace.yaml
    kubectl apply -f configmap.yaml
    kubectl apply -f secret.yaml
    kubectl apply -f deployment.yaml
    kubectl apply -f service.yaml

    # Wait for deployment
    echo "Waiting for deployment to be ready..."
    kubectl rollout status deployment/opus-gpu-miner -n opus-gpu

    # Show status
    kubectl get all -n opus-gpu

    echo -e "${GREEN}✓ Kubernetes deployment completed${NC}"
}

# ============================================================================
# Rollback Function
# ============================================================================
rollback() {
    echo -e "${YELLOW}Rolling back deployment...${NC}"

    case "$DEPLOYMENT_TYPE" in
        docker)
            docker-compose down
            docker-compose up -d --force-recreate
            ;;
        systemd)
            systemctl stop gpu-watchdog metrics-aggregator
            # Restore previous binaries from backup
            ;;
        k8s)
            kubectl rollout undo deployment/opus-gpu-miner -n opus-gpu
            ;;
    esac

    echo -e "${GREEN}✓ Rollback completed${NC}"
}

# ============================================================================
# Main
# ============================================================================
main() {
    local DEPLOYMENT_TYPE="${1:-docker}"

    case "$DEPLOYMENT_TYPE" in
        docker|docker-compose)
            deploy_docker_compose
            ;;
        systemd)
            deploy_systemd
            ;;
        k8s|kubernetes)
            deploy_kubernetes
            ;;
        rollback)
            rollback
            ;;
        --help)
            echo "Usage: $0 [TYPE]"
            echo ""
            echo "Types:"
            echo "  docker       Deploy using Docker Compose (default)"
            echo "  systemd      Deploy using systemd services"
            echo "  k8s          Deploy to Kubernetes cluster"
            echo "  rollback     Rollback to previous version"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown deployment type: $DEPLOYMENT_TYPE${NC}"
            exit 1
            ;;
    esac
}

main "$@"
