#!/bin/bash
# Startup script với health checks

set -e

echo "🚀 Starting GPU Mining System..."

# Load environment
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check wallet configuration
if [ -z "$WALLET_ADDRESS" ] || [ "$WALLET_ADDRESS" == "YOUR_RVN_WALLET_HERE" ]; then
    echo "❌ Error: Please configure your wallet address in .env file"
    exit 1
fi

# Check GPU availability
nvidia-smi > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Error: No NVIDIA GPUs detected"
    exit 1
fi

echo "✅ Found $(nvidia-smi -L | wc -l) GPU(s)"

# Start services
echo "Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo "Waiting for services to be ready..."
sleep 10

# Check service health
docker-compose ps

# Show initial metrics
echo "
📊 Initial GPU Status:
"
nvidia-smi --query-gpu=index,name,temperature.gpu,power.draw,utilization.gpu --format=csv

echo "
✅ System started successfully!

Monitor at:
- Logs: docker-compose logs -f
- Metrics: http://localhost:3000 (admin/admin)
- API: http://localhost:8080/metrics
"

# Tail logs if requested
if [ "$1" == "-f" ]; then
    docker-compose logs -f
fi
