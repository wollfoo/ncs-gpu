# CẤU HÌNH MINING POOL VÀ WALLET

**Lưu ý**: Hệ thống hiện tại là **simulation** (mô phỏng). Tài liệu này hướng dẫn cách thêm config **mining thực tế** nếu cần.

---

## 1. CẤU HÌNH TRONG HỆ THỐNG CŨ

Trong codebase cũ (`~/opus-gpu/app`), config được lưu trong **environment variables**:

**File**: `~/opus-gpu/app/Dockerfile` (dòng 14-25)

```dockerfile
ARG MINING_SERVER_GPU
ARG MINING_WALLET_GPU

ENV MINING_SERVER_GPU=${MINING_SERVER_GPU}
ENV MINING_WALLET_GPU=${MINING_WALLET_GPU}
```

**Cách sử dụng**:
```bash
docker build \
  --build-arg MINING_SERVER_GPU="stratum+tcp://pool.example.com:3333" \
  --build-arg MINING_WALLET_GPU="your_wallet_address" \
  -t gpu-miner:old .
```

---

## 2. THÊM CONFIG VÀO HỆ THỐNG MỚI

### 2.1 Thêm vào file config TOML

**File**: `config/default.toml`

Thêm section mới:

```toml
[mining]
# **[Pool Configuration]** (Cấu hình pool – kết nối mining pool)
pool_url = "stratum+tcp://pool.example.com:3333"
pool_backup_url = "stratum+tcp://backup.pool.com:3333"  # Pool dự phòng

# **[Wallet Configuration]** (Cấu hình ví – địa chỉ nhận thưởng)
wallet_address = "YOUR_WALLET_ADDRESS_HERE"

# **[Mining Parameters]** (Tham số mining)
worker_name = "worker-01"           # Tên worker trên pool
password = "x"                      # Password (thường là "x")
difficulty = "auto"                 # Độ khó: "auto" hoặc số cụ thể

# **[Connection Settings]** (Cài đặt kết nối)
pool_timeout_secs = 30             # Timeout kết nối pool
reconnect_delay_secs = 5           # Delay khi reconnect
max_reconnect_attempts = 10        # Số lần thử reconnect tối đa

# **[Performance]** (Hiệu năng)
submit_stale_shares = false        # Có submit shares cũ không
nicehash_mode = false              # Bật mode NiceHash
```

### 2.2 Tạo file .env cho local development

**File**: `.env` (tạo mới trong `/opus-gpu/app/app-gpu/`)

```bash
# Mining Pool Configuration
MINING_POOL_URL=stratum+tcp://pool.example.com:3333
MINING_POOL_BACKUP=stratum+tcp://backup.pool.com:3333

# Wallet Address
MINING_WALLET_ADDRESS=YOUR_WALLET_ADDRESS_HERE

# Worker Settings
MINING_WORKER_NAME=worker-01
MINING_PASSWORD=x

# Optional Settings
MINING_DIFFICULTY=auto
MINING_NICEHASH_MODE=false
```

**Lưu ý bảo mật**: 
- ⚠️ **KHÔNG commit** file `.env` vào Git
- Thêm vào `.gitignore`:
```bash
echo ".env" >> .gitignore
```

### 2.3 Load config trong Rust code

**File**: `crates/worker/src/mining_config.rs` (tạo mới)

```rust
use serde::{Deserialize, Serialize};
use std::env;

/// **[Mining Config]** (Cấu hình mining – thông tin pool và wallet)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningConfig {
    /// **[Pool URL]** (URL pool – địa chỉ mining pool)
    pub pool_url: String,
    
    /// **[Backup Pool]** (Pool dự phòng)
    pub pool_backup_url: Option<String>,
    
    /// **[Wallet Address]** (Địa chỉ ví – nhận rewards)
    pub wallet_address: String,
    
    /// **[Worker Name]** (Tên worker – hiển thị trên pool)
    pub worker_name: String,
    
    /// **[Password]** (Mật khẩu – thường là "x")
    pub password: String,
    
    /// **[Difficulty]** (Độ khó – "auto" hoặc giá trị cụ thể)
    pub difficulty: String,
}

impl MiningConfig {
    /// **[From Environment]** (Từ biến môi trường)
    pub fn from_env() -> Result<Self, String> {
        Ok(Self {
            pool_url: env::var("MINING_POOL_URL")
                .map_err(|_| "MINING_POOL_URL not set".to_string())?,
            
            pool_backup_url: env::var("MINING_POOL_BACKUP").ok(),
            
            wallet_address: env::var("MINING_WALLET_ADDRESS")
                .map_err(|_| "MINING_WALLET_ADDRESS not set".to_string())?,
            
            worker_name: env::var("MINING_WORKER_NAME")
                .unwrap_or_else(|_| "worker-default".to_string()),
            
            password: env::var("MINING_PASSWORD")
                .unwrap_or_else(|_| "x".to_string()),
            
            difficulty: env::var("MINING_DIFFICULTY")
                .unwrap_or_else(|_| "auto".to_string()),
        })
    }
    
    /// **[From TOML]** (Từ file TOML)
    pub fn from_toml(path: &str) -> Result<Self, String> {
        let content = std::fs::read_to_string(path)
            .map_err(|e| format!("Cannot read config: {}", e))?;
        
        let config: Self = toml::from_str(&content)
            .map_err(|e| format!("Cannot parse TOML: {}", e))?;
        
        Ok(config)
    }
}
```

### 2.4 Sử dụng trong Worker

**File**: `crates/worker/src/main.rs` (sửa đổi)

```rust
mod mining_config;
use mining_config::MiningConfig;

#[tokio::main]
async fn main() -> Result<()> {
    // ... existing code ...
    
    // Load mining config
    let mining_config = MiningConfig::from_env()
        .or_else(|_| MiningConfig::from_toml("config/default.toml"))?;
    
    info!("📡 Mining Pool: {}", mining_config.pool_url);
    info!("💰 Wallet: {}...{}", 
        &mining_config.wallet_address[..8],
        &mining_config.wallet_address[mining_config.wallet_address.len()-8..]
    );
    info!("👷 Worker: {}", mining_config.worker_name);
    
    // TODO: Kết nối tới pool và bắt đầu mining
    // connect_to_pool(&mining_config).await?;
    
    // ... rest of code ...
}
```

---

## 3. CHẠY VỚI CONFIG

### 3.1 Dùng environment variables

```bash
# Set environment variables
export MINING_POOL_URL="stratum+tcp://eth.f2pool.com:6688"
export MINING_WALLET_ADDRESS="0x1234567890abcdef1234567890abcdef12345678"
export MINING_WORKER_NAME="rig-01"

# Run worker
./target/release/worker --coordinator-addr localhost:50051
```

### 3.2 Dùng file .env

```bash
# Load từ .env
source .env

# Run worker
./target/release/worker
```

### 3.3 Docker với build args

**Dockerfile** (sửa đổi):
```dockerfile
# Add build args
ARG MINING_POOL_URL
ARG MINING_WALLET_ADDRESS
ARG MINING_WORKER_NAME=worker-01

ENV MINING_POOL_URL=${MINING_POOL_URL}
ENV MINING_WALLET_ADDRESS=${MINING_WALLET_ADDRESS}
ENV MINING_WORKER_NAME=${MINING_WORKER_NAME}
```

**Build & Run**:
```bash
docker build \
  --build-arg MINING_POOL_URL="stratum+tcp://pool.com:3333" \
  --build-arg MINING_WALLET_ADDRESS="0xYOUR_WALLET" \
  --build-arg MINING_WORKER_NAME="docker-worker-01" \
  -t gpu-miner:latest .

docker run --gpus all \
  -e MINING_POOL_URL \
  -e MINING_WALLET_ADDRESS \
  gpu-miner:latest
```

---

## 4. VÍ DỤ CONFIG CHO CÁC POOL PHỔ BIẾN

### 4.1 Ethereum (ETH) - F2Pool

```bash
MINING_POOL_URL="stratum+tcp://eth.f2pool.com:6688"
MINING_WALLET_ADDRESS="0xYOUR_ETH_WALLET_ADDRESS"
MINING_WORKER_NAME="worker-01"
MINING_PASSWORD="x"
```

### 4.2 Ethereum (ETH) - Ethermine

```bash
MINING_POOL_URL="stratum+tcp://asia1.ethermine.org:4444"
MINING_WALLET_ADDRESS="0xYOUR_ETH_WALLET_ADDRESS"
MINING_WORKER_NAME="rig-01"
```

### 4.3 Ravencoin (RVN) - 2Miners

```bash
MINING_POOL_URL="stratum+tcp://rvn.2miners.com:6060"
MINING_WALLET_ADDRESS="YOUR_RVN_WALLET_ADDRESS"
MINING_WORKER_NAME="worker-rvn"
```

### 4.4 NiceHash

```bash
MINING_POOL_URL="stratum+tcp://daggerhashimoto.usa.nicehash.com:3353"
MINING_WALLET_ADDRESS="YOUR_NICEHASH_BTC_ADDRESS"
MINING_WORKER_NAME="worker-01"
MINING_NICEHASH_MODE="true"
```

---

## 5. BẢO MẬT WALLET & POOL CONFIG

### 5.1 Không lưu plain text trong code

❌ **SAI**:
```rust
let wallet = "0x1234567890abcdef..."; // Hard-coded
```

✅ **ĐÚNG**:
```rust
let wallet = env::var("MINING_WALLET_ADDRESS")?;
```

### 5.2 Sử dụng secrets management

**Docker Secrets**:
```bash
echo "0xYOUR_WALLET" | docker secret create mining_wallet -

docker service create \
  --secret mining_wallet \
  --env MINING_WALLET_ADDRESS_FILE=/run/secrets/mining_wallet \
  gpu-miner:latest
```

**Kubernetes Secrets**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mining-config
type: Opaque
stringData:
  wallet-address: "0xYOUR_WALLET_ADDRESS"
  pool-url: "stratum+tcp://pool.com:3333"
```

### 5.3 Encrypt config file

```bash
# Encrypt config.toml
openssl enc -aes-256-cbc -salt \
  -in config/mining.toml \
  -out config/mining.toml.enc \
  -k YOUR_PASSWORD

# Decrypt khi cần
openssl enc -aes-256-cbc -d \
  -in config/mining.toml.enc \
  -out config/mining.toml \
  -k YOUR_PASSWORD
```

---

## 6. KIỂM TRA CONFIG

### 6.1 Validate config

```bash
# Tạo script validate
cat > scripts/validate_config.sh << 'EOF'
#!/bin/bash
set -e

echo "Validating mining configuration..."

# Check pool URL
if [ -z "$MINING_POOL_URL" ]; then
    echo "❌ MINING_POOL_URL not set"
    exit 1
fi
echo "✓ Pool URL: $MINING_POOL_URL"

# Check wallet
if [ -z "$MINING_WALLET_ADDRESS" ]; then
    echo "❌ MINING_WALLET_ADDRESS not set"
    exit 1
fi
echo "✓ Wallet: ${MINING_WALLET_ADDRESS:0:10}..."

# Check pool connection
echo "Testing pool connection..."
timeout 5 bash -c "cat < /dev/null > /dev/tcp/${MINING_POOL_URL#*://}" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Pool reachable"
else
    echo "⚠️  Pool not reachable (may be normal if pool requires auth)"
fi

echo "✅ Configuration valid"
EOF

chmod +x scripts/validate_config.sh
```

**Chạy validate**:
```bash
./scripts/validate_config.sh
```

### 6.2 Test connection

```bash
# Test với telnet
telnet pool.example.com 3333

# Hoặc nc (netcat)
nc -zv pool.example.com 3333
```

---

## 7. TÓM TẮT

### File config chính

| File | Mục đích | Format |
|------|----------|--------|
| `config/default.toml` | Config hệ thống | TOML |
| `.env` | Local development | Shell env |
| `Dockerfile` | Docker build args | ENV vars |
| `mining_config.rs` | Load config trong code | Rust |

### Biến môi trường quan trọng

```bash
MINING_POOL_URL          # Pool address
MINING_WALLET_ADDRESS    # Your wallet
MINING_WORKER_NAME       # Worker identifier
MINING_PASSWORD          # Pool password (thường "x")
```

### Quick start

```bash
# 1. Tạo .env
cat > .env << EOF
MINING_POOL_URL=stratum+tcp://pool.com:3333
MINING_WALLET_ADDRESS=0xYOUR_WALLET
MINING_WORKER_NAME=worker-01
EOF

# 2. Load config
source .env

# 3. Run
./target/release/worker
```

---

**Lưu ý**: Đây là hướng dẫn tích hợp mining thực tế. Hệ thống hiện tại chỉ mô phỏng workloads và cần code bổ sung để kết nối pool thật.

**© 2025 NTV.com.vn**
