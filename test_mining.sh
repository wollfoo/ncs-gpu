#!/bin/bash

# Set required environment variables for testing
export LOGS_DIR="/tmp/mining_test_logs"
export ML_COMMAND="/bin/echo"  # Mock executable
export MINING_SERVER_CPU="stratum+tcp://test.pool.com:4444"
export MINING_WALLET_CPU="test_wallet_address"
export MINING_SERVER_GPU="stratum+tcp://test.pool.com:5555"
export MINING_WALLET_GPU="test_wallet_gpu"

# Create logs directory
mkdir -p "$LOGS_DIR"

# Run the mining system
echo "Starting mining system test with optimized fixes..."
python3 app/start_mining.py