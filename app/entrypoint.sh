#!/bin/bash
# entrypoint.sh - Smart startup script for transformer mining container
# Automatically detects and configures the environment for optimal operation

set -e

# ===== Globals =====
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
RESET='\033[0m'

# Log levels
LOG_INFO="$GREEN[INFO]$RESET"
LOG_WARN="$YELLOW[WARN]$RESET"
LOG_ERROR="$RED[ERROR]$RESET"
LOG_DEBUG="$BLUE[DEBUG]$RESET"

# Directories
SCRIPT_DIR=${SCRIPT_DIR:-"/app/mining_environment/scripts"}
CONFIG_DIR=${CONFIG_DIR:-"/app/mining_environment/config"}
LOG_DIR=${LOG_DIR:-${LOGS_DIR:-"/app/mining_environment/logs"}}

# All CPU-related paths removed - GPU-only operation

# ===== ĐỊNH NGHĨA CÁC HÀM CƠ BẢN TRƯỚC =====

log() {
    local level="$1"
    local message="$2"
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${level} ${message}"
}

 

# ==============================================================================
# PYTHON ENVIRONMENT SETUP
# ✅ Cố định PYTHONPATH trước khi import module Python
export PYTHONPATH="/app:$PYTHONPATH"
# GPU-only operation - all CPU throttling removed


# ===== Functions =====

setup_python_environment() {
    log "$LOG_INFO" "Thiết lập môi trường Python..."
    
    # Đảm bảo PYTHONPATH chứa /app 
    export PYTHONPATH="/app:$PYTHONPATH"
    
    # Kiểm tra các module quan trọng có import được không
    log "$LOG_DEBUG" "Kiểm tra Python path: $PYTHONPATH"
    log "$LOG_DEBUG" "Kiểm tra working directory: $(pwd)"
    
    # Test import cơ bản
    if python3 -c "import sys; sys.path.insert(0, '/app'); import app" 2>/dev/null; then
        log "$LOG_INFO" "✅ Module 'app' import thành công"
    else
        log "$LOG_WARN" "⚠️ Module 'app' không thể import, sử dụng fallback mode"
        export EBPF_MOCK_MODE=true
    fi
    
    log "$LOG_INFO" "✅ Môi trường Python đã được thiết lập"
}

 # setup_kernel_headers: removed (eBPF disabled, no kernel headers needed)
 setup_kernel_headers() {
     log "$LOG_INFO" "Bỏ qua thiết lập kernel headers (eBPF đã bị loại bỏ)"
     return 0
 }

setup_nvml_symbols() {
    log "$LOG_INFO" "Kiểm tra và thiết lập symbols cho NVML..."
    
    # Đường dẫn phổ biến cho NVML
    NVML_PATHS=(
        "/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1"
        "/usr/lib/libnvidia-ml.so.1" 
        "/usr/local/cuda/lib64/libnvidia-ml.so.1"
    )
    
    # Tìm thư viện NVML
    FOUND_NVML=""
    for path in "${NVML_PATHS[@]}"; do
        if [ -f "$path" ]; then
            FOUND_NVML=$path
            log "$LOG_INFO" "✅ Tìm thấy NVML library tại: $FOUND_NVML"
            break
        fi
    done
    
    if [ -z "$FOUND_NVML" ]; then
        log "$LOG_WARN" "⚠️ Không tìm thấy thư viện NVML ở các vị trí tiêu chuẩn"
        return 1
    fi
    
    # Luôn đảm bảo thư mục chứa NVML có trong LD_LIBRARY_PATH
    NVML_DIR="$(dirname "$FOUND_NVML")"
    OLD_LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-""}
    export LD_LIBRARY_PATH="$NVML_DIR:/usr/lib/x86_64-linux-gnu:/usr/lib:/usr/local/cuda/lib64:$OLD_LD_LIBRARY_PATH"
    log "$LOG_INFO" "Đã cập nhật LD_LIBRARY_PATH (ưu tiên $NVML_DIR) để bao gồm đường dẫn NVML"

    return 0
}

setup_system() {
    log "$LOG_INFO" "Setting up system environment..."
    # Create needed directories
    mkdir -p "$LOG_DIR"
}

 

# ------------------  Logrotate-based deletion every 1 minute ------------------
start_logrotate_daemon() {
    # **logrotate** (công cụ xoay/xoá log tầng hệ thống) chạy độc lập với ứng dụng
    if ! command -v logrotate >/dev/null 2>&1; then
        log "$LOG_WARN" "logrotate không có trong container, bỏ qua daemon xoá log"
        return 0
    fi

    mkdir -p /etc/logrotate.d /var/lib/logrotate || true

    # Tạo cấu hình logrotate cho thư mục log ứng dụng (xóa mỗi lần chạy)
    cat >/etc/logrotate.d/opus-gpu-logs <<'EOF'
/app/mining_environment/logs/*.log {
    missingok
    notifempty
    copytruncate
    rotate 0
    compress
    delaycompress
    dateext
    ifempty
    su root root
    postrotate
        # Dọn các file xoay còn sót (nếu có)
        find /app/mining_environment/logs -maxdepth 1 -type f -name '*.log.*' -delete || true
    endscript
}
EOF

    # Chạy logrotate cưỡng bức mỗi 60 giây (time-based) để đảm bảo TTL 1 phút
    nohup bash -c 'while :; do \
        logrotate -f -s /var/lib/logrotate/status /etc/logrotate.d/opus-gpu-logs >/dev/null 2>&1; \
        sleep 60; \
    done' >/dev/null 2>&1 &

    log "$LOG_INFO" "logrotate daemon started (TTL=60s) cho /app/mining_environment/logs/*.log"
}

# # setup_ebpf_environment (removed, eBPF disabled)() - REMOVED
# eBPF environment setup has been completely removed as container does not use eBPF

check_gpu_environment() {
    log "$LOG_INFO" "Checking GPU environment..."
    
    # Test NVIDIA drivers and libraries
    if [ -f /proc/driver/nvidia/version ]; then
        log "$LOG_INFO" "NVIDIA driver version: $(cat /proc/driver/nvidia/version | head -n 1)"
    else
        log "$LOG_WARN" "NVIDIA driver not detected in /proc"
    fi
    
    # Check NVML library 
    if [ -f /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1 ]; then
        log "$LOG_INFO" "NVML library detected"
    else
        log "$LOG_WARN" "NVML library not found at expected location"
    fi
    
    # Check if our GPU binaries exist
    if [ -f "$CUDA_COMMAND" ]; then
        log "$LOG_INFO" "CUDA command found at $CUDA_COMMAND"
    else
        log "$LOG_WARN" "CUDA command not found at $CUDA_COMMAND"
    fi
}

# ===== DirectPIDRegistry (no-op here; handled in Python) =====
setup_direct_pid_registry() {
    log "$LOG_INFO" "DirectPIDRegistry is handled by Python components; no setup required at entrypoint"
}

# ===== Main =====

log "$LOG_INFO" "Starting Transformer Mining container..."
log "$LOG_INFO" "Environment: EBPF_DEBUG_MODE=${EBPF_DEBUG_MODE:-false}"

# 🚀 PRE-FLIGHT CHECKS (removed eBPF-related; keep minimal)

# 🚌 SETUP DIRECT PID REGISTRY (handled in Python)
setup_direct_pid_registry

# ✅ BƯỚC ĐẦU TIÊN: Thiết lập môi trường Python
setup_python_environment

# Thiết lập NVML trước
setup_nvml_symbols


# Setup steps
setup_system
# setup_ebpf_environment (removed, eBPF disabled)
check_gpu_environment


# Start monitoring services in the background
log "$LOG_INFO" "Starting system monitoring..."
# GPU plugins monitoring removed - keep neutral log without referencing removed path
log "$LOG_INFO" "Monitoring: Prometheus exporter disabled"

# NVRTC fix script removed – base image đã đảm bảo thư viện NVRTC chuẩn
# Log successful initialization 
log "$LOG_INFO" "Container initialization complete. Running command: $@"

# Khởi động daemon logrotate xoá log theo thời gian (mỗi 1 phút) nếu được bật
if [ "${ENABLE_LOGROTATE:-0}" = "1" ]; then
    start_logrotate_daemon
else
    log "$LOG_INFO" "logrotate daemon disabled via ENABLE_LOGROTATE=${ENABLE_LOGROTATE:-0}"
fi

# Execute the provided command (usually the CMD directive from Dockerfile)
exec "$@" 