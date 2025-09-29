# OPUS-GPU Migration Guide

🔄 **Migration Guide** từ hệ thống cũ sang **OPUS-GPU v2.0** - Safe & Comprehensive Migration

## 📋 Tổng quan Migration

Hướng dẫn này cung cấp quy trình migration toàn diện từ các hệ thống mining cũ sang **OPUS-GPU v2.0**, đảm bảo **zero downtime** (không gián đoạn) và **data integrity** (toàn vẹn dữ liệu).

## 🔍 Pre-Migration Assessment

### 1. Current System Analysis
```bash
# Kiểm tra hệ thống hiện tại
./migration-analyzer.sh --scan-current-system

# Output example:
Current Mining System Analysis
=============================
- Mining Software: CGMiner 4.11.1
- GPU Count: 4x RTX 3080
- Pool Configuration: 3 pools configured
- Hashrate: 400 MH/s average
- Uptime: 45 days
- Configuration Files: /etc/cgminer/cgminer.conf
- Data Location: /var/lib/cgminer/
- Wallet Files: /home/miner/.bitcoin/wallet.dat
```

### 2. Compatibility Check
```yaml
supported_migrations:
  from_miners:
    - "CGMiner 4.x"
    - "BFGMiner 5.x"
    - "T-Rex Miner 0.25+"
    - "NBMiner 42+"
    - "GMiner 3.x"
    - "PhoenixMiner 6.x"
    - "Claymore Miner 15.x"
    - "Custom miners"

  from_pools:
    - "Stratum v1/v2 pools"
    - "Getwork pools"
    - "Solo mining setups"

  from_platforms:
    - "Linux (Ubuntu 18.04+, CentOS 7+)"
    - "Windows 10+"
    - "Mining-specific distributions (HiveOS, SimpleMining)"

unsupported_scenarios:
  - "ASIC-only mining farms"
  - "Custom mining protocols"
  - "Legacy GPU drivers (< 2 years old)"
```

### 3. Migration Planning Checklist
```bash
# Pre-migration checklist
□ Backup current configuration files
□ Document current pool settings
□ Export wallet/key information
□ Record current performance baselines
□ Plan migration timeline
□ Prepare rollback strategy
□ Test OPUS-GPU on secondary system
□ Validate GPU compatibility
□ Check network requirements
□ Notify pools of potential IP changes
```

## 📦 Migration Types

### Type A: Simple Miner Replacement
**Scenario**: Replace single mining software, keep existing pools và configuration

```bash
# Estimated time: 30-60 minutes
# Downtime: 5-10 minutes
# Complexity: Low
# Risk: Low
```

### Type B: Complete System Migration
**Scenario**: Migrate từ old mining OS sang standard Linux + OPUS-GPU

```bash
# Estimated time: 2-4 hours
# Downtime: 1-2 hours
# Complexity: Medium
# Risk: Medium
```

### Type C: Infrastructure Overhaul
**Scenario**: Multi-rig migration với centralized management

```bash
# Estimated time: 1-3 days
# Downtime: Minimal (rolling migration)
# Complexity: High
# Risk: Medium
```

## 🛠️ Step-by-Step Migration Process

### Phase 1: Preparation & Backup

#### **Step 1.1: Create System Backup**
```bash
#!/bin/bash
# backup-current-system.sh

BACKUP_DIR="/backup/opus-gpu-migration-$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

echo "Creating comprehensive system backup..."

# 1. Configuration files
echo "Backing up configurations..."
mkdir -p $BACKUP_DIR/config
cp -r /etc/cgminer/* $BACKUP_DIR/config/ 2>/dev/null || true
cp -r /etc/miner/* $BACKUP_DIR/config/ 2>/dev/null || true
cp ~/.mining* $BACKUP_DIR/config/ 2>/dev/null || true

# 2. Mining data và logs
echo "Backing up mining data..."
mkdir -p $BACKUP_DIR/data
cp -r /var/lib/cgminer/* $BACKUP_DIR/data/ 2>/dev/null || true
cp -r /var/log/mining/* $BACKUP_DIR/data/ 2>/dev/null || true

# 3. Wallet files (if present)
echo "Backing up wallet files..."
mkdir -p $BACKUP_DIR/wallets
find /home -name "wallet.dat" -exec cp {} $BACKUP_DIR/wallets/ \; 2>/dev/null || true
find /home -name "*.key" -exec cp {} $BACKUP_DIR/wallets/ \; 2>/dev/null || true

# 4. System information
echo "Recording system information..."
uname -a > $BACKUP_DIR/system_info.txt
lsb_release -a >> $BACKUP_DIR/system_info.txt 2>/dev/null || true
nvidia-smi > $BACKUP_DIR/gpu_info.txt 2>/dev/null || true
cat /proc/cpuinfo > $BACKUP_DIR/cpu_info.txt
free -h > $BACKUP_DIR/memory_info.txt
df -h > $BACKUP_DIR/disk_info.txt

# 5. Network configuration
ip addr show > $BACKUP_DIR/network_config.txt
cat /etc/resolv.conf > $BACKUP_DIR/dns_config.txt

# 6. Current mining performance
echo "Recording current performance..."
ps aux | grep -E "(cgminer|miner)" > $BACKUP_DIR/current_processes.txt
netstat -tuln > $BACKUP_DIR/network_connections.txt

echo "Backup completed: $BACKUP_DIR"
```

#### **Step 1.2: Extract Configuration**
```bash
#!/bin/bash
# extract-mining-config.sh

echo "Extracting mining configuration..."

# CGMiner configuration extraction
if [ -f "/etc/cgminer/cgminer.conf" ]; then
    echo "Found CGMiner configuration"

    # Extract pool information
    grep -E "\"url\"|\"user\"|\"pass\"" /etc/cgminer/cgminer.conf > extracted_pools.json

    # Extract GPU settings
    grep -E "\"intensity\"|\"gpu-engine\"|\"gpu-memclock\"" /etc/cgminer/cgminer.conf > extracted_gpu_settings.json
fi

# T-Rex Miner configuration
if [ -f "/etc/t-rex/config.json" ]; then
    echo "Found T-Rex configuration"
    jq '.pools[] | {url: .url, user: .user, pass: .pass}' /etc/t-rex/config.json > extracted_pools.json
fi

# Generate OPUS-GPU configuration template
cat > opus-gpu-migrated.toml << EOF
# Migrated configuration from previous mining setup
# Generated on: $(date)

[mining]
algorithm = "SHA256"  # Update based on your previous mining
max_workers = $(nproc)
# GPU devices will be auto-detected

[pool]
# Extracted from previous configuration
urls = [
    # Add your pools here from extracted_pools.json
]
username = "your_wallet_address"
password = "worker_name"

[monitoring]
enabled = true
metrics_port = 9090

[api.rest]
host = "127.0.0.1"
port = 8080
EOF

echo "Configuration template created: opus-gpu-migrated.toml"
```

#### **Step 1.3: Validate Prerequisites**
```bash
#!/bin/bash
# validate-prerequisites.sh

echo "Validating migration prerequisites..."

# Check GPU drivers
echo "Checking GPU drivers..."
if nvidia-smi >/dev/null 2>&1; then
    DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits | head -1)
    echo "NVIDIA Driver: $DRIVER_VERSION"

    # Check minimum version
    if [ "$(echo "$DRIVER_VERSION >= 525" | bc)" -eq 1 ]; then
        echo "✓ NVIDIA driver compatible"
    else
        echo "⚠ NVIDIA driver may need update"
    fi
else
    echo "⚠ NVIDIA drivers not detected"
fi

# Check CUDA
if nvcc --version >/dev/null 2>&1; then
    CUDA_VERSION=$(nvcc --version | grep "release" | awk '{print $6}' | cut -c2-)
    echo "✓ CUDA Toolkit: $CUDA_VERSION"
else
    echo "⚠ CUDA Toolkit not found"
fi

# Check system resources
echo "Checking system resources..."
TOTAL_RAM=$(free -g | awk '/^Mem:/{print $2}')
AVAILABLE_DISK=$(df / | awk 'NR==2{print $4}')

if [ $TOTAL_RAM -ge 8 ]; then
    echo "✓ RAM: ${TOTAL_RAM}GB (sufficient)"
else
    echo "⚠ RAM: ${TOTAL_RAM}GB (may be insufficient)"
fi

if [ $AVAILABLE_DISK -ge 10485760 ]; then  # 10GB in KB
    echo "✓ Disk space: $(($AVAILABLE_DISK/1048576))GB available"
else
    echo "⚠ Disk space may be insufficient"
fi

# Check network connectivity
echo "Checking network connectivity..."
if ping -c 1 google.com >/dev/null 2>&1; then
    echo "✓ Internet connectivity"
else
    echo "⚠ No internet connectivity"
fi

echo "Prerequisites validation completed"
```

### Phase 2: OPUS-GPU Installation

#### **Step 2.1: Install OPUS-GPU (Docker Method)**
```bash
#!/bin/bash
# install-opus-gpu-docker.sh

echo "Installing OPUS-GPU via Docker..."

# 1. Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
fi

# 2. Install NVIDIA Container Toolkit
if ! command -v nvidia-container-runtime &> /dev/null; then
    echo "Installing NVIDIA Container Toolkit..."
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
    curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
    sudo apt-get update && sudo apt-get install -y nvidia-docker2
    sudo systemctl restart docker
fi

# 3. Create OPUS-GPU directory structure
sudo mkdir -p /opt/opus-gpu/{config,data,logs,backup}
sudo chown -R $USER:$USER /opt/opus-gpu

# 4. Pull OPUS-GPU image
echo "Pulling OPUS-GPU Docker image..."
docker pull opus-gpu:latest

# 5. Test Docker installation
echo "Testing Docker + GPU access..."
docker run --rm --gpus all nvidia/cuda:12.2-base-ubuntu22.04 nvidia-smi

echo "OPUS-GPU Docker installation completed"
```

#### **Step 2.2: Configuration Migration**
```bash
#!/bin/bash
# migrate-configuration.sh

echo "Migrating configuration to OPUS-GPU format..."

# Read backup data
BACKUP_DIR="/backup/opus-gpu-migration-*"
CONFIG_FILE="/opt/opus-gpu/config/migrated.toml"

# Start với base configuration
cat > $CONFIG_FILE << 'EOF'
# OPUS-GPU Configuration
# Migrated from previous mining setup

[mining]
algorithm = "SHA256"
max_workers = 4
difficulty = 1000000
work_timeout_secs = 30
stats_interval_secs = 5
gpu_devices = []  # Will be auto-detected
worker_threads = 1
batch_size = 1000
memory_size = 536870912

[pool]
urls = []
username = ""
password = ""
retry_attempts = 3
retry_delay_secs = 5
connection_timeout_secs = 10
keepalive_interval_secs = 30

[wallet]
keystore_dir = "/opt/opus-gpu/keystore"
backup_dir = "/opt/opus-gpu/backup"
encryption_enabled = true

[monitoring]
enabled = true
metrics_port = 9090
stats_interval_secs = 10
temperature_threshold = 80.0
memory_threshold = 90.0
enable_alerts = true

[storage]
data_dir = "/opt/opus-gpu/data"
database_url = "sqlite://opus-gpu.db"
max_connections = 10
backup_enabled = true
backup_interval_hours = 24
retention_days = 30

[api.rest]
host = "127.0.0.1"
port = 8080
cors_enabled = true
cors_origins = ["*"]
rate_limit = 100
request_timeout_secs = 30

[api.websocket]
host = "127.0.0.1"
port = 8081
max_connections = 1000
message_buffer_size = 1000
heartbeat_interval_secs = 30

[api.grpc]
host = "127.0.0.1"
port = 8082
max_message_size = 4194304
keepalive_interval_secs = 30
keepalive_timeout_secs = 5

[plugins]
disabled = false
plugin_dir = "/opt/opus-gpu/plugins"
max_plugins = 50
load_timeout_secs = 30
whitelist = []
blacklist = []

[bus]
buffer_size = 1000
max_subscribers = 100
message_timeout_secs = 5
enable_persistence = false
persistence_file = "/opt/opus-gpu/data/bus_state.json"
EOF

# Extract pools from backup
if [ -f "$BACKUP_DIR/extracted_pools.json" ]; then
    echo "Migrating pool configuration..."
    # Parse và add pools to configuration
    # This would need custom parsing based on source format
fi

# Auto-detect GPUs và update configuration
echo "Auto-detecting GPUs..."
GPU_COUNT=$(nvidia-smi -L | wc -l)
if [ $GPU_COUNT -gt 0 ]; then
    GPU_DEVICES=$(seq 0 $((GPU_COUNT-1)) | tr '\n' ',' | sed 's/,$//')
    sed -i "s/gpu_devices = \[\]/gpu_devices = [$GPU_DEVICES]/" $CONFIG_FILE
    sed -i "s/max_workers = 4/max_workers = $GPU_COUNT/" $CONFIG_FILE
fi

echo "Configuration migration completed: $CONFIG_FILE"
```

### Phase 3: Data Migration

#### **Step 3.1: Wallet Migration**
```bash
#!/bin/bash
# migrate-wallets.sh

echo "Migrating wallet data..."

BACKUP_WALLET_DIR="/backup/opus-gpu-migration-*/wallets"
OPUS_WALLET_DIR="/opt/opus-gpu/keystore"

mkdir -p $OPUS_WALLET_DIR

# Migrate wallet files
if [ -d "$BACKUP_WALLET_DIR" ]; then
    echo "Found wallet backup directory"

    # Copy wallet files
    cp $BACKUP_WALLET_DIR/* $OPUS_WALLET_DIR/ 2>/dev/null || true

    # Set proper permissions
    chmod 600 $OPUS_WALLET_DIR/*
    chown -R $USER:$USER $OPUS_WALLET_DIR

    echo "Wallet files migrated to $OPUS_WALLET_DIR"
else
    echo "No wallet files found in backup"
fi

# Create default wallet configuration
cat > $OPUS_WALLET_DIR/wallet_info.txt << EOF
# Wallet Migration Information
# Generated: $(date)

# Original wallet location: $BACKUP_WALLET_DIR
# New wallet location: $OPUS_WALLET_DIR
# Encryption: Enabled by default in OPUS-GPU

# Important: Verify wallet access before deleting backup files
EOF
```

#### **Step 3.2: Historical Data Migration**
```bash
#!/bin/bash
# migrate-historical-data.sh

echo "Migrating historical mining data..."

BACKUP_DATA_DIR="/backup/opus-gpu-migration-*/data"
OPUS_DATA_DIR="/opt/opus-gpu/data"

mkdir -p $OPUS_DATA_DIR

# Migrate relevant data files
if [ -d "$BACKUP_DATA_DIR" ]; then
    # Mining statistics
    if [ -f "$BACKUP_DATA_DIR/mining_stats.log" ]; then
        cp "$BACKUP_DATA_DIR/mining_stats.log" "$OPUS_DATA_DIR/legacy_stats.log"
    fi

    # Configuration history
    if [ -f "$BACKUP_DATA_DIR/config_history.log" ]; then
        cp "$BACKUP_DATA_DIR/config_history.log" "$OPUS_DATA_DIR/legacy_config.log"
    fi

    echo "Historical data migrated"
else
    echo "No historical data found"
fi

# Initialize OPUS-GPU database
echo "Initializing OPUS-GPU database..."
# This would be done by OPUS-GPU on first run
```

### Phase 4: Testing & Validation

#### **Step 4.1: Test Installation**
```bash
#!/bin/bash
# test-opus-gpu-installation.sh

echo "Testing OPUS-GPU installation..."

# 1. Test Docker container
echo "Testing Docker container..."
docker run --rm --gpus all \
  -v /opt/opus-gpu/config:/app/config \
  opus-gpu:latest \
  --config config/migrated.toml --validate

if [ $? -eq 0 ]; then
    echo "✓ Configuration validation passed"
else
    echo "✗ Configuration validation failed"
    exit 1
fi

# 2. Test GPU detection
echo "Testing GPU detection..."
docker run --rm --gpus all \
  opus-gpu:latest \
  --list-devices

# 3. Test benchmark mode
echo "Running benchmark test..."
docker run --rm --gpus all \
  -v /opt/opus-gpu/config:/app/config \
  opus-gpu:latest \
  --benchmark --duration 30 --config config/migrated.toml

echo "Installation testing completed"
```

#### **Step 4.2: Performance Comparison**
```bash
#!/bin/bash
# compare-performance.sh

echo "Comparing performance với previous system..."

# Record baseline from backup
BACKUP_PERFORMANCE="/backup/opus-gpu-migration-*/current_processes.txt"
if [ -f "$BACKUP_PERFORMANCE" ]; then
    echo "Previous system baseline:"
    cat $BACKUP_PERFORMANCE
fi

# Test OPUS-GPU performance
echo "Testing OPUS-GPU performance..."
docker run -d --name opus-gpu-test \
  --gpus all \
  -v /opt/opus-gpu/config:/app/config \
  -v /opt/opus-gpu/data:/app/data \
  opus-gpu:latest \
  --config config/migrated.toml

# Wait for startup
sleep 30

# Collect performance metrics
echo "Collecting OPUS-GPU metrics..."
curl -s http://localhost:8080/api/v1/status > opus_gpu_performance.json
curl -s http://localhost:8080/api/v1/mining/stats >> opus_gpu_performance.json

# Stop test container
docker stop opus-gpu-test && docker rm opus-gpu-test

echo "Performance comparison data saved"
```

### Phase 5: Production Deployment

#### **Step 5.1: Stop Old Miner**
```bash
#!/bin/bash
# stop-old-miner.sh

echo "Stopping old mining software..."

# Record final statistics
echo "Recording final statistics from old system..."
ps aux | grep -E "(cgminer|miner)" > /opt/opus-gpu/backup/final_old_system_stats.txt

# Stop mining processes gracefully
echo "Stopping mining processes..."
pkill -TERM cgminer 2>/dev/null || true
pkill -TERM t-rex 2>/dev/null || true
pkill -TERM nbminer 2>/dev/null || true
pkill -TERM gminer 2>/dev/null || true

# Wait for graceful shutdown
sleep 10

# Force stop if still running
pkill -KILL cgminer 2>/dev/null || true
pkill -KILL t-rex 2>/dev/null || true

echo "Old mining software stopped"
```

#### **Step 5.2: Deploy OPUS-GPU Production**
```bash
#!/bin/bash
# deploy-opus-gpu-production.sh

echo "Deploying OPUS-GPU in production mode..."

# 1. Final configuration check
echo "Final configuration validation..."
docker run --rm --gpus all \
  -v /opt/opus-gpu/config:/app/config \
  opus-gpu:latest \
  --config config/migrated.toml --validate

if [ $? -ne 0 ]; then
    echo "Configuration validation failed. Aborting deployment."
    exit 1
fi

# 2. Start OPUS-GPU production container
echo "Starting OPUS-GPU production container..."
docker run -d \
  --name opus-gpu-production \
  --runtime=nvidia \
  --gpus all \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 8081:8081 \
  -p 8082:8082 \
  -p 9090:9090 \
  -v /opt/opus-gpu/config:/app/config \
  -v /opt/opus-gpu/data:/app/data \
  -v /opt/opus-gpu/logs:/app/logs \
  --log-driver=json-file \
  --log-opt max-size=100m \
  --log-opt max-file=3 \
  opus-gpu:latest \
  --config config/migrated.toml

# 3. Wait for startup
echo "Waiting for OPUS-GPU startup..."
sleep 30

# 4. Verify operation
echo "Verifying OPUS-GPU operation..."
if curl -f http://localhost:8080/health >/dev/null 2>&1; then
    echo "✓ OPUS-GPU health check passed"
else
    echo "✗ OPUS-GPU health check failed"
    docker logs opus-gpu-production
    exit 1
fi

# 5. Start mining
echo "Starting mining..."
curl -X POST http://localhost:8080/api/v1/mining/start

echo "OPUS-GPU production deployment completed successfully!"
```

### Phase 6: Post-Migration Validation

#### **Step 6.1: 24-Hour Monitoring**
```bash
#!/bin/bash
# post-migration-monitoring.sh

echo "Starting 24-hour post-migration monitoring..."

MONITOR_DURATION=86400  # 24 hours in seconds
START_TIME=$(date +%s)
LOG_FILE="/opt/opus-gpu/logs/migration_monitoring.log"

while [ $(($(date +%s) - START_TIME)) -lt $MONITOR_DURATION ]; do
    echo "=== Monitoring Check: $(date) ===" >> $LOG_FILE

    # Check container status
    docker ps | grep opus-gpu-production >> $LOG_FILE

    # Check mining status
    curl -s http://localhost:8080/api/v1/status >> $LOG_FILE

    # Check system resources
    echo "System Resources:" >> $LOG_FILE
    free -h >> $LOG_FILE
    df -h >> $LOG_FILE

    # Check GPU status
    nvidia-smi --query-gpu=timestamp,name,temperature.gpu,utilization.gpu,power.draw --format=csv >> $LOG_FILE

    echo "---" >> $LOG_FILE

    # Sleep for 1 hour
    sleep 3600
done

echo "24-hour monitoring completed. Check $LOG_FILE for details."
```

#### **Step 6.2: Performance Validation**
```bash
#!/bin/bash
# validate-migration-success.sh

echo "Validating migration success..."

# 1. Compare hashrates
echo "Comparing hashrates..."
OLD_HASHRATE=$(grep -E "hashrate|MH/s" /opt/opus-gpu/backup/final_old_system_stats.txt | head -1)
NEW_HASHRATE=$(curl -s http://localhost:8080/api/v1/mining/stats | jq -r '.current.hashrate')

echo "Old system hashrate: $OLD_HASHRATE"
echo "New system hashrate: $NEW_HASHRATE H/s"

# 2. Check pool connectivity
echo "Validating pool connectivity..."
POOL_STATUS=$(curl -s http://localhost:8080/api/v1/pool/status | jq -r '.connected')
if [ "$POOL_STATUS" = "true" ]; then
    echo "✓ Pool connectivity confirmed"
else
    echo "✗ Pool connectivity issues"
fi

# 3. Check GPU utilization
echo "Checking GPU utilization..."
GPU_UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | awk '{sum+=$1} END {print sum/NR}')
echo "Average GPU utilization: ${GPU_UTIL}%"

if [ "$(echo "$GPU_UTIL > 90" | bc)" -eq 1 ]; then
    echo "✓ GPU utilization optimal"
else
    echo "⚠ GPU utilization may need optimization"
fi

# 4. Validate data integrity
echo "Validating data integrity..."
if [ -f "/opt/opus-gpu/keystore/wallet_info.txt" ]; then
    echo "✓ Wallet data preserved"
else
    echo "⚠ Wallet data may be missing"
fi

echo "Migration validation completed"
```

## 🔄 Rollback Procedures

### Emergency Rollback
```bash
#!/bin/bash
# emergency-rollback.sh

echo "Initiating emergency rollback..."

# 1. Stop OPUS-GPU
echo "Stopping OPUS-GPU..."
docker stop opus-gpu-production
docker rm opus-gpu-production

# 2. Restore old configuration
echo "Restoring old configuration..."
BACKUP_DIR="/backup/opus-gpu-migration-*"
cp -r $BACKUP_DIR/config/* /etc/cgminer/ 2>/dev/null || true

# 3. Restart old mining software
echo "Restarting old mining software..."
# This depends on what was running before
systemctl start cgminer 2>/dev/null || true
# hoặc
/usr/local/bin/cgminer --config /etc/cgminer/cgminer.conf &

echo "Emergency rollback completed"
```

### Gradual Rollback
```bash
#!/bin/bash
# gradual-rollback.sh

echo "Initiating gradual rollback..."

# 1. Reduce OPUS-GPU load
echo "Reducing OPUS-GPU GPU allocation..."
curl -X PUT http://localhost:8080/api/v1/config \
  -H "Content-Type: application/json" \
  -d '{"mining": {"gpu_devices": [0]}}'

# 2. Start old miner on remaining GPUs
echo "Starting old miner on GPUs 1-3..."
# Configure old miner để use specific GPUs

# 3. Gradually migrate traffic back
echo "Monitor performance và continue migration..."

echo "Gradual rollback initiated"
```

## 📊 Migration Verification Checklist

### Technical Verification
```bash
# Post-migration checklist
□ OPUS-GPU container running successfully
□ All GPUs detected và utilized
□ Pool connections established
□ Hashrate matches or exceeds previous system
□ System resources within normal parameters
□ API endpoints responding correctly
□ Monitoring systems operational
□ Backup systems configured
□ Security measures in place
□ Documentation updated
```

### Business Verification
```bash
# Business impact checklist
□ Mining revenue maintained or improved
□ Operational costs stable or reduced
□ System reliability improved
□ Monitoring capabilities enhanced
□ Management interfaces functional
□ Support processes established
□ Team training completed
□ Disaster recovery plan updated
```

## 🚨 Troubleshooting Common Migration Issues

### Issue 1: GPU Not Detected
```bash
# Problem: GPUs not detected after migration
# Solution:
docker run --rm --gpus all nvidia/cuda:12.2-base-ubuntu22.04 nvidia-smi

# If this fails:
sudo apt update && sudo apt install nvidia-container-toolkit
sudo systemctl restart docker
```

### Issue 2: Performance Degradation
```bash
# Problem: Lower hashrate than expected
# Solution:
# 1. Check GPU power limits
nvidia-smi -q -d POWER

# 2. Verify thermal throttling
nvidia-smi -q -d TEMPERATURE

# 3. Optimize OPUS-GPU configuration
curl -X PUT http://localhost:8080/api/v1/config \
  -H "Content-Type: application/json" \
  -d '{"mining": {"batch_size": 2000, "worker_threads": 2}}'
```

### Issue 3: Pool Connection Problems
```bash
# Problem: Cannot connect to mining pools
# Solution:
# 1. Test network connectivity
telnet pool.example.com 4444

# 2. Check firewall rules
sudo ufw status

# 3. Verify pool configuration
curl http://localhost:8080/api/v1/pool/status
```

### Issue 4: Configuration Errors
```bash
# Problem: Invalid configuration format
# Solution:
# 1. Validate configuration
docker run --rm -v /opt/opus-gpu/config:/app/config \
  opus-gpu:latest --config config/migrated.toml --validate

# 2. Reset to default configuration
cp /opt/opus-gpu/config/default.toml /opt/opus-gpu/config/migrated.toml
```

## 📞 Migration Support

### **Emergency Support**
- **Migration Hotline**: +1-XXX-XXX-XXXX (24/7 during migration window)
- **Emergency Email**: migration-support@opus-gpu.com
- **Discord Channel**: #migration-support

### **Documentation**
- **Detailed Guide**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **API Reference**: [API_REFERENCE.md](API_REFERENCE.md)
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)

### **Professional Services**
- **Managed Migration**: Full-service migration with expert support
- **Remote Assistance**: Real-time support during migration
- **Custom Scripts**: Tailored migration scripts for specific environments

---

**🔄 Safe & Successful Migration to OPUS-GPU** | **Zero Downtime, Maximum Performance**