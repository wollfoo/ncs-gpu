#!/bin/bash
# entrypoint.sh - Optimized startup script for transformer mining container
# Refactored to remove legacy eBPF code and improve startup performance

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
LOG_DIR=${LOGS_DIR:-"/app/mining_environment/logs"}

# ===== CORE FUNCTIONS =====

log() {
    local level="$1"
    local message="$2"
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${level} ${message}"
}

setup_python_environment() {
    log "$LOG_INFO" "Setting up Python environment..."
    
    # Ensure PYTHONPATH contains /app 
    export PYTHONPATH="/app:$PYTHONPATH"
    
    # Test basic import
    if python3 -c "import sys; sys.path.insert(0, '/app'); import app" 2>/dev/null; then
        log "$LOG_INFO" "✅ Module 'app' import successful"
    else
        log "$LOG_WARN" "⚠️ Module 'app' cannot be imported, continuing with fallback mode"
    fi
    
    log "$LOG_INFO" "✅ Python environment configured"
}

setup_nvml_symbols() {
    log "$LOG_INFO" "Setting up NVML library paths..."
    
    # Common NVML paths
    NVML_PATHS=(
        "/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1"
        "/usr/lib/libnvidia-ml.so.1" 
        "/usr/local/cuda/lib64/libnvidia-ml.so.1"
    )
    
    # Find NVML library
    FOUND_NVML=""
    for path in "${NVML_PATHS[@]}"; do
        if [ -f "$path" ]; then
            FOUND_NVML=$path
            log "$LOG_INFO" "✅ Found NVML library at: $FOUND_NVML"
            break
        fi
    done
    
    if [ -z "$FOUND_NVML" ]; then
        log "$LOG_WARN" "⚠️ NVML library not found at standard locations"
        return 1
    fi
    
    # Update LD_LIBRARY_PATH to include NVML directory
    NVML_DIR="$(dirname "$FOUND_NVML")"
    OLD_LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-""}
    export LD_LIBRARY_PATH="$NVML_DIR:/usr/lib/x86_64-linux-gnu:/usr/lib:/usr/local/cuda/lib64:$OLD_LD_LIBRARY_PATH"
    log "$LOG_INFO" "Updated LD_LIBRARY_PATH to include NVML path"

    # Create symlinks if needed and permissions allow
    mkdir -p /usr/lib /usr/local/cuda/lib64 2>/dev/null || true

    # Create symlinks for common locations
    for target_dir in "/usr/lib" "/usr/local/cuda/lib64"; do
        target_file="$target_dir/libnvidia-ml.so.1"
        if [ ! -f "$target_file" ] && [ -f "$FOUND_NVML" ] && [ -w "$target_dir" ]; then
            ln -sf "$FOUND_NVML" "$target_file" || true
            log "$LOG_DEBUG" "Created symlink: $target_file -> $FOUND_NVML"
        fi
    done

    return 0
}

setup_basic_directories() {
    log "$LOG_INFO" "Setting up basic directories..."
    
    # Create essential directories
    mkdir -p "$LOG_DIR" || log "$LOG_WARN" "Cannot create log directory: $LOG_DIR"
    
    log "$LOG_INFO" "✅ Basic directories configured"
}

setup_stunnel() {
    log "$LOG_INFO" "Setting up Stunnel secure communication..."
    
    # Check if stunnel binary exists
    if command -v stunnel &> /dev/null; then
        if [ -f "/etc/stunnel/stunnel.conf" ]; then
            log "$LOG_INFO" "Starting Stunnel service..."
            stunnel /etc/stunnel/stunnel.conf &
        else
            log "$LOG_WARN" "Stunnel config not found at /etc/stunnel/stunnel.conf"
        fi
    else
        log "$LOG_WARN" "Stunnel not found, secure communication disabled"
    fi
}

check_gpu_environment() {
    log "$LOG_INFO" "Checking GPU environment..."
    
    # Test NVIDIA drivers
    if [ -f /proc/driver/nvidia/version ]; then
        local nvidia_version=$(cat /proc/driver/nvidia/version | head -n 1)
        log "$LOG_INFO" "NVIDIA driver version: $nvidia_version"
    else
        log "$LOG_WARN" "NVIDIA driver not detected in /proc"
    fi
    
    # Check NVML library 
    if [ -f /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1 ]; then
        log "$LOG_INFO" "NVML library detected"
    else
        log "$LOG_WARN" "NVML library not found at expected location"
    fi
    
    # Check CUDA command
    if [ -f "$CUDA_COMMAND" ]; then
        log "$LOG_INFO" "CUDA command found at $CUDA_COMMAND"
    else
        log "$LOG_WARN" "CUDA command not found at $CUDA_COMMAND"
    fi
}

ensure_libhwloc() {
    log "$LOG_INFO" "Checking libhwloc library..."
    
    if ldconfig -p | grep -q "libhwloc.so.15"; then
        log "$LOG_INFO" "✅ libhwloc.so.15 available"
        return 0
    fi

    log "$LOG_WARN" "⚠️ libhwloc.so.15 not found, attempting installation..."
    apt-get update -q || true
    apt-get install -y --no-install-recommends libhwloc15 || true

    # Create symlink to alternative version if needed
    if ! ldconfig -p | grep -q "libhwloc.so.15"; then
        local ALT_LIB=$(ldconfig -p | awk '/libhwloc.so/{print $4; exit}')
        if [ -n "$ALT_LIB" ] && [ -f "$ALT_LIB" ]; then
            ln -sf "$ALT_LIB" /usr/lib/x86_64-linux-gnu/libhwloc.so.15 || true
            log "$LOG_INFO" "Created symlink libhwloc.so.15 -> $ALT_LIB"
        fi
    fi

    ldconfig 2>/dev/null || true
    
    if ldconfig -p | grep -q "libhwloc.so.15"; then
        log "$LOG_INFO" "✅ libhwloc.so.15 ready"
    else
        log "$LOG_WARN" "⚠️ libhwloc.so.15 not available - mining may continue without hardware topology detection"
    fi
}

# ===== MAIN EXECUTION =====

log "$LOG_INFO" "Starting Transformer Mining container (Optimized)..."
log "$LOG_INFO" "Container initialization beginning..."

# Core setup sequence - optimized for fast startup
setup_python_environment
setup_nvml_symbols
setup_basic_directories
setup_stunnel
check_gpu_environment
ensure_libhwloc

# Log successful initialization 
log "$LOG_INFO" "✅ Container initialization complete. Starting application: $@"

# Execute the provided command (usually start_mining.py)
exec "$@"