#!/bin/bash
# Script thiết lập môi trường test cho hệ thống GPU mining
# Created: $(date)

echo "🚀 Setting up test environment for GPU mining system..."

# Export các biến môi trường cần thiết
export LOGS_DIR="/home/azureuser/ncs-gpu/app/mining_environment/logs"
export CUDA_COMMAND="/usr/local/bin/inference-cuda"  # Default path from code
export MINING_SERVER_GPU="stratum+tcp://pool.example.com:3333"  # Test server
export MINING_WALLET_GPU="test_wallet_address_123456"  # Test wallet

# Tạo thư mục logs nếu chưa tồn tại
echo "📁 Creating logs directory: $LOGS_DIR"
mkdir -p "$LOGS_DIR"

# Hiển thị các biến môi trường đã thiết lập
echo "✅ Environment variables set:"
echo "   LOGS_DIR=$LOGS_DIR"
echo "   CUDA_COMMAND=$CUDA_COMMAND"
echo "   MINING_SERVER_GPU=$MINING_SERVER_GPU"
echo "   MINING_WALLET_GPU=$MINING_WALLET_GPU"

# Kiểm tra xem file inference-cuda có tồn tại không
if [ ! -f "$CUDA_COMMAND" ]; then
    echo "⚠️  Warning: CUDA command not found at $CUDA_COMMAND"
    echo "   Creating mock executable for testing..."
    # Tạo mock executable cho test
    sudo mkdir -p /usr/local/bin
    echo '#!/bin/bash' | sudo tee /usr/local/bin/inference-cuda > /dev/null
    echo 'echo "Mock inference-cuda running with args: $@"' | sudo tee -a /usr/local/bin/inference-cuda > /dev/null
    sudo chmod +x /usr/local/bin/inference-cuda
fi

echo ""
echo "🎯 To use these environment variables, run:"
echo "   source test_env_setup.sh"
echo ""
echo "📝 Then run the mining system:"
echo "   python3 start_mining.py"
