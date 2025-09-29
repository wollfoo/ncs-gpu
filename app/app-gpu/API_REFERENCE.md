# Agent-GPU API Reference

🌐 **Complete API Documentation** cho **Agent-GPU v2.0** - REST, WebSocket & gRPC APIs

## 📋 Tổng quan

**Agent-GPU** cung cấp 3 loại API interface:
- **REST API** (HTTP/JSON) - General purpose operations
- **WebSocket API** - Real-time events và notifications
- **gRPC API** - High-performance binary protocol

## 🔗 API Endpoints

### Base URLs
```
REST API:     http://localhost:8080/api/v1
WebSocket:    ws://localhost:8081/ws
gRPC:         localhost:8082
Metrics:      http://localhost:9090/metrics
```

### Authentication
```http
# JWT Bearer Token (nếu enabled)
Authorization: Bearer <jwt_token>

# API Key (alternative)
X-API-Key: your-api-key
```

## 🌐 REST API

### System Endpoints

#### **GET /health**
**Health check** (kiểm tra sức khỏe hệ thống)
```http
GET /health

Response 200 OK:
{
  "status": "healthy",
  "timestamp": "2024-12-29T10:30:00Z",
  "uptime_seconds": 3600,
  "version": "2.0.0"
}

Response 503 Service Unavailable:
{
  "status": "unhealthy",
  "errors": ["GPU 0 overheating", "Pool disconnected"]
}
```

#### **GET /ready**
**Readiness check** (kiểm tra sẵn sàng hoạt động)
```http
GET /ready

Response 200 OK:
{
  "ready": true,
  "services": {
    "mining_engine": "ready",
    "pool_connection": "ready",
    "gpu_manager": "ready",
    "database": "ready"
  }
}
```

#### **GET /api/v1/status**
**System status overview** (tổng quan trạng thái hệ thống)
```http
GET /api/v1/status

Response 200 OK:
{
  "system": {
    "status": "running",
    "uptime_seconds": 7200,
    "cpu_usage": 45.2,
    "memory_usage": 68.7,
    "disk_usage": 23.1
  },
  "mining": {
    "status": "active",
    "algorithm": "SHA256",
    "hashrate": 1250000000,
    "accepted_shares": 156,
    "rejected_shares": 2,
    "efficiency": 98.7
  },
  "gpus": [
    {
      "id": 0,
      "name": "NVIDIA RTX 4080",
      "temperature": 68,
      "power_usage": 280,
      "memory_used": 12288,
      "utilization": 98
    }
  ],
  "pool": {
    "connected": true,
    "url": "stratum+tcp://pool.example.com:4444",
    "latency": 25,
    "last_ping": "2024-12-29T10:29:45Z"
  }
}
```

### Mining Endpoints

#### **GET /api/v1/mining/stats**
**Mining statistics** (thống kê mining)
```http
GET /api/v1/mining/stats

Response 200 OK:
{
  "current": {
    "hashrate": 1250000000,
    "hashrate_unit": "H/s",
    "power_consumption": 850,
    "efficiency": 1470588,
    "efficiency_unit": "H/J",
    "uptime_seconds": 7200
  },
  "session": {
    "total_shares": 158,
    "accepted_shares": 156,
    "rejected_shares": 2,
    "stale_shares": 0,
    "acceptance_rate": 98.73,
    "total_hashrate": 9000000000,
    "avg_hashrate": 1250000000
  },
  "workers": [
    {
      "id": "worker_0",
      "gpu_id": 0,
      "hashrate": 312500000,
      "shares": 39,
      "temperature": 68,
      "status": "active"
    },
    {
      "id": "worker_1",
      "gpu_id": 1,
      "hashrate": 312500000,
      "shares": 39,
      "temperature": 71,
      "status": "active"
    }
  ],
  "pool": {
    "difficulty": 10000000,
    "block_height": 820450,
    "network_hashrate": 500000000000000,
    "next_difficulty_change": 1890
  }
}
```

#### **POST /api/v1/mining/start**
**Start mining** (bắt đầu mining)
```http
POST /api/v1/mining/start
Content-Type: application/json

{
  "algorithm": "SHA256",
  "gpu_devices": [0, 1],
  "pool_url": "stratum+tcp://pool.example.com:4444",
  "username": "wallet_address",
  "password": "worker01"
}

Response 200 OK:
{
  "status": "started",
  "message": "Mining started successfully",
  "workers": 2,
  "algorithm": "SHA256",
  "estimated_hashrate": 625000000
}

Response 400 Bad Request:
{
  "error": "invalid_algorithm",
  "message": "Algorithm 'INVALID' is not supported",
  "supported_algorithms": ["SHA256", "Ethash", "KawPow"]
}
```

#### **POST /api/v1/mining/stop**
**Stop mining** (dừng mining)
```http
POST /api/v1/mining/stop

Response 200 OK:
{
  "status": "stopped",
  "message": "Mining stopped successfully",
  "final_stats": {
    "total_runtime": 7200,
    "total_shares": 158,
    "avg_hashrate": 1250000000
  }
}
```

#### **POST /api/v1/mining/restart**
**Restart mining** (khởi động lại mining)
```http
POST /api/v1/mining/restart

Response 200 OK:
{
  "status": "restarted",
  "message": "Mining restarted successfully"
}
```

### Device Endpoints

#### **GET /api/v1/devices**
**List GPU devices** (danh sách thiết bị GPU)
```http
GET /api/v1/devices

Response 200 OK:
{
  "devices": [
    {
      "id": 0,
      "name": "NVIDIA GeForce RTX 4080",
      "vendor": "NVIDIA",
      "driver_version": "525.78.01",
      "cuda_version": "12.2",
      "memory": {
        "total": 16777216,
        "used": 12288000,
        "free": 4489216,
        "usage_percent": 73.2
      },
      "compute": {
        "capability": "8.9",
        "cores": 9728,
        "base_clock": 2205,
        "boost_clock": 2510
      },
      "thermal": {
        "temperature": 68,
        "max_temperature": 83,
        "fan_speed": 65,
        "power_limit": 320,
        "power_usage": 280
      },
      "status": "active",
      "supported_algorithms": ["SHA256", "Ethash", "KawPow"]
    }
  ],
  "total_devices": 1,
  "active_devices": 1
}
```

#### **GET /api/v1/devices/{device_id}**
**Get device details** (chi tiết thiết bị)
```http
GET /api/v1/devices/0

Response 200 OK:
{
  "id": 0,
  "name": "NVIDIA GeForce RTX 4080",
  "detailed_info": {
    "pci": {
      "bus_id": "0000:01:00.0",
      "device_id": "2704",
      "subsystem_id": "467610de"
    },
    "compute_modes": ["Default", "Exclusive", "Prohibited"],
    "current_mode": "Default",
    "ecc_enabled": false,
    "multi_gpu_board": false
  },
  "performance": {
    "base_hashrate": 312500000,
    "peak_hashrate": 350000000,
    "efficiency_rating": 4.5
  }
}
```

#### **POST /api/v1/devices/{device_id}/control**
**Control device** (điều khiển thiết bị)
```http
POST /api/v1/devices/0/control
Content-Type: application/json

{
  "action": "set_power_limit",
  "value": 300
}

Response 200 OK:
{
  "status": "success",
  "message": "Power limit set to 300W",
  "previous_value": 320,
  "new_value": 300
}

# Supported actions:
# - set_power_limit: Set power limit (50-450W)
# - set_fan_speed: Set fan speed (30-100%)
# - set_memory_clock: Set memory clock offset (-1000 to +1000 MHz)
# - set_core_clock: Set core clock offset (-200 to +200 MHz)
# - reset_settings: Reset to default settings
```

### Pool Endpoints

#### **GET /api/v1/pool/status**
**Pool connection status** (trạng thái kết nối pool)
```http
GET /api/v1/pool/status

Response 200 OK:
{
  "connected": true,
  "primary_pool": {
    "url": "stratum+tcp://pool.example.com:4444",
    "status": "connected",
    "latency": 25,
    "last_ping": "2024-12-29T10:29:45Z",
    "connected_since": "2024-12-29T08:15:30Z"
  },
  "backup_pools": [
    {
      "url": "stratum+tcp://backup.example.com:4444",
      "status": "standby",
      "priority": 2
    }
  ],
  "stats": {
    "connection_attempts": 3,
    "successful_connections": 3,
    "dropped_connections": 0,
    "average_latency": 28
  }
}
```

#### **POST /api/v1/pool/switch**
**Switch mining pool** (chuyển pool mining)
```http
POST /api/v1/pool/switch
Content-Type: application/json

{
  "url": "stratum+tcp://newpool.example.com:4444",
  "username": "wallet_address",
  "password": "worker01"
}

Response 200 OK:
{
  "status": "switched",
  "message": "Successfully switched to new pool",
  "new_pool": "stratum+tcp://newpool.example.com:4444",
  "switch_time": "2024-12-29T10:30:15Z"
}
```

### Configuration Endpoints

#### **GET /api/v1/config**
**Get current configuration** (lấy cấu hình hiện tại)
```http
GET /api/v1/config

Response 200 OK:
{
  "mining": {
    "algorithm": "SHA256",
    "max_workers": 4,
    "gpu_devices": [0, 1],
    "batch_size": 2000
  },
  "pool": {
    "urls": ["stratum+tcp://pool.example.com:4444"],
    "username": "wallet_address",
    "retry_attempts": 3
  },
  "monitoring": {
    "enabled": true,
    "temperature_threshold": 80,
    "memory_threshold": 90
  }
}
```

#### **PUT /api/v1/config**
**Update configuration** (cập nhật cấu hình)
```http
PUT /api/v1/config
Content-Type: application/json

{
  "mining": {
    "batch_size": 2500,
    "worker_threads": 3
  },
  "monitoring": {
    "temperature_threshold": 75
  }
}

Response 200 OK:
{
  "status": "updated",
  "message": "Configuration updated successfully",
  "changes": [
    "mining.batch_size: 2000 -> 2500",
    "mining.worker_threads: 2 -> 3",
    "monitoring.temperature_threshold: 80 -> 75"
  ],
  "restart_required": false
}
```

### Metrics Endpoints

#### **GET /api/v1/metrics**
**Prometheus metrics** (metrics cho Prometheus)
```http
GET /api/v1/metrics

Response 200 OK (Prometheus format):
# HELP opus_gpu_hashrate Current mining hashrate in H/s
# TYPE opus_gpu_hashrate gauge
opus_gpu_hashrate{device="0"} 312500000
opus_gpu_hashrate{device="1"} 312500000

# HELP opus_gpu_temperature GPU temperature in Celsius
# TYPE opus_gpu_temperature gauge
opus_gpu_temperature{device="0"} 68
opus_gpu_temperature{device="1"} 71

# HELP opus_gpu_power_usage Power consumption in Watts
# TYPE opus_gpu_power_usage gauge
opus_gpu_power_usage{device="0"} 280
opus_gpu_power_usage{device="1"} 285

# HELP opus_gpu_shares_total Total number of shares
# TYPE opus_gpu_shares_total counter
opus_gpu_shares_total{type="accepted"} 156
opus_gpu_shares_total{type="rejected"} 2
```

#### **GET /api/v1/metrics/summary**
**Metrics summary** (tóm tắt metrics)
```http
GET /api/v1/metrics/summary

Response 200 OK:
{
  "timestamp": "2024-12-29T10:30:00Z",
  "hashrate": {
    "current": 1250000000,
    "average_1m": 1248000000,
    "average_5m": 1245000000,
    "average_15m": 1240000000
  },
  "power": {
    "total_consumption": 850,
    "efficiency": 1470588,
    "cost_per_hour": 0.12
  },
  "shares": {
    "total": 158,
    "accepted": 156,
    "rejected": 2,
    "rate_per_minute": 1.3
  },
  "devices": {
    "total": 2,
    "active": 2,
    "avg_temperature": 69.5,
    "max_temperature": 71
  }
}
```

### Error Handling

#### **Error Response Format**
```json
{
  "error": "error_code",
  "message": "Human readable error message",
  "details": {
    "field": "field_name",
    "value": "invalid_value",
    "expected": "expected_format"
  },
  "timestamp": "2024-12-29T10:30:00Z",
  "request_id": "req_123456789"
}
```

#### **Common Error Codes**
```http
400 Bad Request:
- invalid_algorithm: Unsupported mining algorithm
- invalid_device: GPU device not found
- invalid_configuration: Configuration validation failed
- missing_parameter: Required parameter missing

401 Unauthorized:
- invalid_token: JWT token invalid or expired
- missing_authorization: Authorization header missing

403 Forbidden:
- insufficient_permissions: User lacks required permissions
- rate_limit_exceeded: API rate limit exceeded

404 Not Found:
- device_not_found: GPU device not found
- endpoint_not_found: API endpoint does not exist

409 Conflict:
- mining_already_active: Mining is already running
- device_in_use: GPU device already in use

500 Internal Server Error:
- gpu_driver_error: GPU driver communication failed
- pool_connection_failed: Cannot connect to mining pool
- database_error: Database operation failed

503 Service Unavailable:
- system_overheating: System temperature too high
- insufficient_resources: Insufficient system resources
```

## 🔄 WebSocket API

### Connection
```javascript
const ws = new WebSocket('ws://localhost:8081/ws');

// With authentication
const ws = new WebSocket('ws://localhost:8081/ws', {
  headers: {
    'Authorization': 'Bearer your-jwt-token'
  }
});
```

### Message Format
```json
{
  "type": "message_type",
  "id": "optional_message_id",
  "timestamp": "2024-12-29T10:30:00Z",
  "data": { }
}
```

### Subscription Management

#### **Subscribe to Events**
```json
{
  "type": "subscribe",
  "topics": [
    "mining.stats",
    "device.status",
    "pool.connection",
    "system.alerts"
  ]
}

Response:
{
  "type": "subscription_confirmed",
  "topics": ["mining.stats", "device.status", "pool.connection", "system.alerts"],
  "subscriptions": 4
}
```

#### **Unsubscribe from Events**
```json
{
  "type": "unsubscribe",
  "topics": ["system.alerts"]
}

Response:
{
  "type": "subscription_updated",
  "removed_topics": ["system.alerts"],
  "active_topics": ["mining.stats", "device.status", "pool.connection"]
}
```

### Event Types

#### **Mining Statistics Updates**
```json
{
  "type": "mining.stats",
  "timestamp": "2024-12-29T10:30:00Z",
  "data": {
    "hashrate": 1250000000,
    "power_consumption": 850,
    "shares": {
      "accepted": 156,
      "rejected": 2,
      "total": 158
    },
    "efficiency": 1470588
  }
}
```

#### **Device Status Changes**
```json
{
  "type": "device.status",
  "timestamp": "2024-12-29T10:30:00Z",
  "data": {
    "device_id": 0,
    "status": "active",
    "temperature": 72,
    "power_usage": 285,
    "hashrate": 312500000,
    "alerts": []
  }
}
```

#### **Pool Connection Events**
```json
{
  "type": "pool.connection",
  "timestamp": "2024-12-29T10:30:00Z",
  "data": {
    "status": "connected",
    "pool_url": "stratum+tcp://pool.example.com:4444",
    "latency": 28,
    "difficulty": 10000000
  }
}
```

#### **System Alerts**
```json
{
  "type": "system.alert",
  "timestamp": "2024-12-29T10:30:00Z",
  "data": {
    "severity": "warning",
    "category": "temperature",
    "message": "GPU 0 temperature high: 78°C",
    "device_id": 0,
    "current_value": 78,
    "threshold": 75,
    "recommended_action": "Increase fan speed or reduce power limit"
  }
}
```

#### **New Block Notifications**
```json
{
  "type": "pool.new_block",
  "timestamp": "2024-12-29T10:30:00Z",
  "data": {
    "block_height": 820451,
    "block_hash": "000000000000000000052abc123...",
    "difficulty": 10500000,
    "network_hashrate": 510000000000000
  }
}
```

### Control Commands

#### **Real-time Control**
```json
{
  "type": "control",
  "command": "set_power_limit",
  "data": {
    "device_id": 0,
    "value": 300
  }
}

Response:
{
  "type": "control_response",
  "status": "success",
  "message": "Power limit updated to 300W"
}
```

## 🔗 gRPC API

### Service Definition
```protobuf
// opus_gpu.proto
syntax = "proto3";

package opus_gpu.v1;

service MiningService {
  rpc GetStatus(Empty) returns (StatusResponse);
  rpc StartMining(StartMiningRequest) returns (OperationResponse);
  rpc StopMining(Empty) returns (OperationResponse);
  rpc GetStats(Empty) returns (StatsResponse);
  rpc StreamStats(Empty) returns (stream StatsResponse);
}

service DeviceService {
  rpc ListDevices(Empty) returns (DeviceListResponse);
  rpc GetDevice(DeviceRequest) returns (DeviceResponse);
  rpc ControlDevice(DeviceControlRequest) returns (OperationResponse);
}

service PoolService {
  rpc GetPoolStatus(Empty) returns (PoolStatusResponse);
  rpc SwitchPool(SwitchPoolRequest) returns (OperationResponse);
}

message Empty {}

message StatusResponse {
  string status = 1;
  int64 uptime_seconds = 2;
  SystemStats system = 3;
  MiningStats mining = 4;
}

message StartMiningRequest {
  string algorithm = 1;
  repeated int32 gpu_devices = 2;
  string pool_url = 3;
  string username = 4;
  string password = 5;
}

message OperationResponse {
  bool success = 1;
  string message = 2;
  map<string, string> metadata = 3;
}

message StatsResponse {
  int64 hashrate = 1;
  int32 power_consumption = 2;
  ShareStats shares = 3;
  repeated WorkerStats workers = 4;
}

message ShareStats {
  int64 total = 1;
  int64 accepted = 2;
  int64 rejected = 3;
  double acceptance_rate = 4;
}

message WorkerStats {
  string id = 1;
  int32 gpu_id = 2;
  int64 hashrate = 3;
  int64 shares = 4;
  int32 temperature = 5;
  string status = 6;
}
```

### Client Examples

#### **Go Client**
```go
package main

import (
    "context"
    "log"

    "google.golang.org/grpc"
    pb "github.com/agent-gpu/agent-gpu/api/grpc/proto"
)

func main() {
    conn, err := grpc.Dial("localhost:8082", grpc.WithInsecure())
    if err != nil {
        log.Fatal(err)
    }
    defer conn.Close()

    client := pb.NewMiningServiceClient(conn)

    // Get mining stats
    stats, err := client.GetStats(context.Background(), &pb.Empty{})
    if err != nil {
        log.Fatal(err)
    }

    log.Printf("Hashrate: %d H/s", stats.Hashrate)
    log.Printf("Power: %d W", stats.PowerConsumption)
}
```

#### **Python Client**
```python
import grpc
import opus_gpu_pb2
import opus_gpu_pb2_grpc

def main():
    with grpc.insecure_channel('localhost:8082') as channel:
        stub = opus_gpu_pb2_grpc.MiningServiceStub(channel)

        # Get mining stats
        response = stub.GetStats(opus_gpu_pb2.Empty())
        print(f"Hashrate: {response.hashrate} H/s")
        print(f"Power: {response.power_consumption} W")

        # Stream real-time stats
        for stats in stub.StreamStats(opus_gpu_pb2.Empty()):
            print(f"Real-time hashrate: {stats.hashrate}")

if __name__ == '__main__':
    main()
```

#### **Node.js Client**
```javascript
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

const packageDefinition = protoLoader.loadSync('opus_gpu.proto');
const opus_gpu = grpc.loadPackageDefinition(packageDefinition).opus_gpu.v1;

const client = new opus_gpu.MiningService('localhost:8082',
                                         grpc.credentials.createInsecure());

// Get mining stats
client.GetStats({}, (error, response) => {
    if (error) {
        console.error(error);
        return;
    }

    console.log(`Hashrate: ${response.hashrate} H/s`);
    console.log(`Power: ${response.power_consumption} W`);
});

// Stream stats
const stream = client.StreamStats({});
stream.on('data', (stats) => {
    console.log(`Real-time hashrate: ${stats.hashrate}`);
});
```

## 📱 Message Bus Events

### Internal Event System
```rust
// Message bus topics
pub enum BusEvent {
    MiningStarted { workers: u32, algorithm: String },
    MiningStats { hashrate: u64, power: u32 },
    DeviceAlert { device_id: u32, message: String },
    PoolConnected { url: String, latency: u32 },
    ShareSubmitted { accepted: bool, difficulty: u64 },
    ConfigUpdated { section: String, changes: Vec<String> }
}
```

### Plugin Event Handling
```rust
use opus_gpu_plugin_api::{EventHandler, BusEvent};

impl EventHandler for MyPlugin {
    async fn handle_event(&self, event: BusEvent) -> Result<(), PluginError> {
        match event {
            BusEvent::MiningStats { hashrate, power } => {
                // Custom hashrate processing
                self.process_hashrate(hashrate).await?;
            }
            BusEvent::DeviceAlert { device_id, message } => {
                // Custom alerting logic
                self.send_alert(device_id, message).await?;
            }
            _ => {}
        }
        Ok(())
    }
}
```

## 🔧 SDK & Libraries

### **Rust SDK**
```rust
use opus_gpu_sdk::{Client, Config};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let config = Config::new("http://localhost:8080")?;
    let client = Client::new(config).await?;

    // Get mining stats
    let stats = client.mining().stats().await?;
    println!("Hashrate: {} H/s", stats.hashrate);

    // Control devices
    client.devices().set_power_limit(0, 300).await?;

    Ok(())
}
```

### **Python SDK**
```python
from opus_gpu import Client

async def main():
    client = Client("http://localhost:8080")

    # Get mining stats
    stats = await client.mining.stats()
    print(f"Hashrate: {stats.hashrate} H/s")

    # Control devices
    await client.devices.set_power_limit(0, 300)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### **JavaScript SDK**
```javascript
import { OpusGPUClient } from 'agent-gpu-sdk';

const client = new OpusGPUClient('http://localhost:8080');

// Get mining stats
const stats = await client.mining.stats();
console.log(`Hashrate: ${stats.hashrate} H/s`);

// WebSocket connection
const ws = client.websocket();
ws.on('mining.stats', (data) => {
    console.log('New stats:', data);
});
```

## 🛡️ Rate Limiting

### **Rate Limit Headers**
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
X-RateLimit-Window: 60
```

### **Rate Limit Response**
```json
{
  "error": "rate_limit_exceeded",
  "message": "API rate limit exceeded",
  "details": {
    "limit": 100,
    "window": 60,
    "retry_after": 45
  }
}
```

---

**🚀 Complete API Reference for Agent-GPU** | **Build Powerful Mining Applications**