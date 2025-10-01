#!/bin/bash
# Installation script cho GPU Mining System v2.0

set -e

echo "🚀 Installing GPU Mining System v2.0..."

# Check prerequisites
check_prerequisites() {
    echo "📋 Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker not found. Please install Docker first."
        exit 1
    fi
    
    # Check NVIDIA Docker runtime
    if ! docker info | grep -q nvidia; then
        echo "❌ NVIDIA Docker runtime not found. Please install nvidia-container-toolkit."
        exit 1
    fi
    
    # Check Go
    if ! command -v go &> /dev/null; then
        echo "⚠️ Go not found. Installing Go..."
        wget -q https://go.dev/dl/go1.22.0.linux-amd64.tar.gz
        sudo tar -C /usr/local -xzf go1.22.0.linux-amd64.tar.gz
        export PATH=$PATH:/usr/local/bin
        rm go1.22.0.linux-amd64.tar.gz
    fi
    
    # Check Rust
    if ! command -v cargo &> /dev/null; then
        echo "⚠️ Rust not found. Installing Rust..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source $HOME/.cargo/env
    fi
    
    echo "✅ All prerequisites satisfied"
}

# Build the system
build_system() {
    echo "🔨 Building system..."
    
    # Build Go services
    echo "Building Go services..."
    make build-go
    
    # Build Rust workers
    echo "Building Rust workers..."
    make build-rust
    
    # Build Docker images
    echo "Building Docker images..."
    make docker-build
    
    echo "✅ Build completed"
}

# Configure system
configure_system() {
    echo "⚙️ Configuring system..."
    
    # Create config from example
    if [ ! -f .env ]; then
        cp .env.example .env
        echo "📝 Created .env file. Please edit it with your wallet address and pool settings."
    fi
    
    # Create directories
    mkdir -p logs data configs
    
    # Set permissions
    chmod 755 scripts/*.sh
    
    echo "✅ Configuration completed"
}

# Install systemd service
install_service() {
    echo "🔧 Installing systemd service..."
    
    cat > /tmp/gpu-mining.service <<EOF
[Unit]
Description=GPU Mining System
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/docker-compose up
ExecStop=/usr/bin/docker-compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    sudo mv /tmp/gpu-mining.service /etc/systemd/system/
    sudo systemctl daemon-reload
    
    echo "✅ Service installed. Use 'sudo systemctl start gpu-mining' to start."
}

# Main installation flow
main() {
    check_prerequisites
    build_system
    configure_system
    
    read -p "Install as systemd service? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_service
    fi
    
    echo "
✅ Installation complete!

Next steps:
1. Edit .env file with your wallet address and pool settings
2. Start the system with: docker-compose up -d
   OR if installed as service: sudo systemctl start gpu-mining
3. Monitor logs with: docker-compose logs -f
4. View metrics at: http://localhost:3000 (Grafana)

Happy mining! ⛏️
"
}

main "$@"
