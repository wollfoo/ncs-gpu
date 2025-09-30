# 📡 OPUS-GPU API Reference

**Version**: 0.1.0-alpha
**Last Updated**: 2025-09-30
**Base URL**: `http://localhost:8080` (configurable)

---

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [HTTP Endpoints](#http-endpoints)
  - [Health Check](#health-check)
  - [Prometheus Metrics](#prometheus-metrics)
  - [System Status](#system-status)
  - [Task Submission](#task-submission)
- [Request/Response Formats](#requestresponse-formats)
- [Error Codes](#error-codes)
- [Rate Limiting](#rate-limiting)
- [Examples](#examples)

---

## Overview

**OPUS-GPU HTTP API** cung cấp RESTful endpoints cho monitoring, control, và task submission.

### API Characteristics

| Feature | Specification |
|---------|---------------|
| **Protocol** | HTTP/1.1 |
| **Content-Type** | `application/json`, `text/plain` |
| **Authentication** | None (v0.1.0) / JWT (planned v0.2.0) |
| **Rate Limiting** | None (v0.1.0) / Token bucket (planned) |
| **Versioning** | URL path (`/api/v1/...`) |
| **CORS** | Disabled (same-origin only) |

### Base Configuration

**Default Settings** (config/app.toml):
```toml
[api]
host = "127.0.0.1"  # Bind address
port = 8080          # HTTP port
```

**Environment Override**:
```bash
API_HOST=0.0.0.0 API_PORT=9000 ./gpu-miner
```

---

## Authentication

### Current Status (v0.1.0-alpha)

**Authentication**: ❌ Not Implemented

**Security Implications**:
- ⚠️ **API is unauthenticated** - Anyone with network access can call endpoints
- ⚠️ **Bind to localhost only** - Prevent external access
- ⚠️ **Use firewall rules** - Restrict access to trusted IPs

### Planned (v0.2.0)

**JWT Token-Based Authentication**:

```bash
# Login request
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secure_password"}'

# Response
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2025-09-30T12:00:00Z"
}

# Authenticated request
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  http://localhost:8080/api/v1/status
```

---

## HTTP Endpoints

### Health Check

**Endpoint**: `GET /health`

**Purpose**: Liveness/readiness probe cho container orchestration.

**Request**:
```http
GET /health HTTP/1.1
Host: localhost:8080
```

**Response** (200 OK):
```json
{
  "status": "healthy",
  "timestamp": "2025-09-30T10:30:45Z",
  "uptime_seconds": 3600,
  "version": "0.1.0-alpha"
}
```

**Response** (503 Service Unavailable):
```json
{
  "status": "unhealthy",
  "timestamp": "2025-09-30T10:30:45Z",
  "reason": "GPU module not responding"
}
```

**Status Codes**:
- `200 OK` - System healthy
- `503 Service Unavailable` - System degraded/unhealthy

**Use Cases**:
- Kubernetes liveness probe
- Docker health check
- Load balancer health monitoring

**Example**:
```bash
# Kubernetes probe configuration
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10
```

---

### Prometheus Metrics

**Endpoint**: `GET /metrics`

**Purpose**: Expose Prometheus-compatible metrics.

**Request**:
```http
GET /metrics HTTP/1.1
Host: localhost:8080
Accept: text/plain
```

**Response** (200 OK):
```
# HELP opus_miner_hashrate_mhs Current hashrate in MH/s
# TYPE opus_miner_hashrate_mhs gauge
opus_miner_hashrate_mhs{gpu_id="0"} 125.5
opus_miner_hashrate_mhs{gpu_id="1"} 128.3

# HELP opus_miner_gpu_utilization_percent GPU utilization percentage
# TYPE opus_miner_gpu_utilization_percent gauge
opus_miner_gpu_utilization_percent{gpu_id="0"} 98.2
opus_miner_gpu_utilization_percent{gpu_id="1"} 97.8

# HELP opus_miner_gpu_temperature_celsius GPU temperature in Celsius
# TYPE opus_miner_gpu_temperature_celsius gauge
opus_miner_gpu_temperature_celsius{gpu_id="0"} 72.0
opus_miner_gpu_temperature_celsius{gpu_id="1"} 74.5

# HELP opus_miner_gpu_power_watts GPU power consumption in watts
# TYPE opus_miner_gpu_power_watts gauge
opus_miner_gpu_power_watts{gpu_id="0"} 285.0
opus_miner_gpu_power_watts{gpu_id="1"} 290.0

# HELP opus_miner_gpu_memory_used_mb GPU memory used in MB
# TYPE opus_miner_gpu_memory_used_mb gauge
opus_miner_gpu_memory_used_mb{gpu_id="0"} 6144.0
opus_miner_gpu_memory_used_mb{gpu_id="1"} 6208.0

# HELP opus_miner_shares_accepted_total Total accepted shares
# TYPE opus_miner_shares_accepted_total counter
opus_miner_shares_accepted_total 1523

# HELP opus_miner_shares_rejected_total Total rejected shares
# TYPE opus_miner_shares_rejected_total counter
opus_miner_shares_rejected_total 12

# HELP opus_miner_shares_stale_total Total stale shares
# TYPE opus_miner_shares_stale_total counter
opus_miner_shares_stale_total 5

# HELP opus_miner_cpu_usage_percent CPU usage percentage
# TYPE opus_miner_cpu_usage_percent gauge
opus_miner_cpu_usage_percent 3.2

# HELP opus_miner_memory_used_mb System memory used in MB
# TYPE opus_miner_memory_used_mb gauge
opus_miner_memory_used_mb 52.0

# HELP opus_miner_uptime_seconds System uptime in seconds
# TYPE opus_miner_uptime_seconds counter
opus_miner_uptime_seconds 3600
```

**Status Codes**:
- `200 OK` - Metrics successfully scraped

**Prometheus Configuration**:
```yaml
scrape_configs:
  - job_name: 'opus-gpu-miner'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: /metrics
    scrape_interval: 10s
```

**Metrics Summary**:

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `opus_miner_hashrate_mhs` | Gauge | `gpu_id` | Hashrate in MH/s |
| `opus_miner_gpu_utilization_percent` | Gauge | `gpu_id` | GPU utilization % |
| `opus_miner_gpu_temperature_celsius` | Gauge | `gpu_id` | GPU temperature °C |
| `opus_miner_gpu_power_watts` | Gauge | `gpu_id` | GPU power watts |
| `opus_miner_gpu_memory_used_mb` | Gauge | `gpu_id` | GPU memory MB |
| `opus_miner_shares_accepted_total` | Counter | - | Accepted shares |
| `opus_miner_shares_rejected_total` | Counter | - | Rejected shares |
| `opus_miner_shares_stale_total` | Counter | - | Stale shares |
| `opus_miner_cpu_usage_percent` | Gauge | - | CPU usage % |
| `opus_miner_memory_used_mb` | Gauge | - | System memory MB |
| `opus_miner_uptime_seconds` | Counter | - | Uptime seconds |

---

### System Status

**Endpoint**: `GET /api/v1/status`

**Purpose**: Real-time system status và GPU information.

**Request**:
```http
GET /api/v1/status HTTP/1.1
Host: localhost:8080
Accept: application/json
```

**Response** (200 OK):
```json
{
  "status": "running",
  "timestamp": "2025-09-30T10:30:45Z",
  "uptime_seconds": 3600,
  "version": "0.1.0-alpha",
  "gpus": [
    {
      "id": 0,
      "name": "NVIDIA RTX 4090",
      "hashrate_mhs": 125.5,
      "utilization_percent": 98.2,
      "temperature_celsius": 72.0,
      "power_watts": 285.0,
      "memory_used_mb": 6144,
      "memory_total_mb": 24576,
      "fan_speed_percent": 65,
      "status": "mining"
    },
    {
      "id": 1,
      "name": "NVIDIA RTX 4090",
      "hashrate_mhs": 128.3,
      "utilization_percent": 97.8,
      "temperature_celsius": 74.5,
      "power_watts": 290.0,
      "memory_used_mb": 6208,
      "memory_total_mb": 24576,
      "fan_speed_percent": 68,
      "status": "mining"
    }
  ],
  "mining": {
    "pool_url": "stratum+tcp://pool.example.com:3333",
    "wallet": "0x1234...5678",
    "shares_accepted": 1523,
    "shares_rejected": 12,
    "shares_stale": 5,
    "total_hashrate_mhs": 253.8,
    "efficiency_mhps_per_watt": 0.441
  },
  "system": {
    "cpu_usage_percent": 3.2,
    "memory_used_mb": 52,
    "memory_total_mb": 64000,
    "platform": "linux",
    "architecture": "x86_64"
  }
}
```

**Response** (503 Service Unavailable):
```json
{
  "status": "degraded",
  "timestamp": "2025-09-30T10:30:45Z",
  "error": "GPU 0 not responding",
  "gpus": [
    {
      "id": 0,
      "status": "error",
      "error": "CUDA driver error"
    },
    {
      "id": 1,
      "status": "mining",
      "hashrate_mhs": 128.3
    }
  ]
}
```

**Status Codes**:
- `200 OK` - System running normally
- `503 Service Unavailable` - System degraded/error

**Field Descriptions**:

| Field | Type | Description |
|-------|------|-------------|
| `status` | String | System status: `running`, `degraded`, `stopped` |
| `timestamp` | ISO8601 | Current server time |
| `uptime_seconds` | Integer | Time since startup |
| `version` | String | Software version |
| `gpus[].id` | Integer | GPU device ID (0-indexed) |
| `gpus[].name` | String | GPU model name |
| `gpus[].hashrate_mhs` | Float | Current hashrate (MH/s) |
| `gpus[].utilization_percent` | Float | GPU utilization (0-100) |
| `gpus[].temperature_celsius` | Float | GPU temperature (°C) |
| `gpus[].power_watts` | Float | GPU power consumption (W) |
| `gpus[].memory_used_mb` | Integer | GPU memory used (MB) |
| `gpus[].memory_total_mb` | Integer | GPU memory total (MB) |
| `gpus[].fan_speed_percent` | Integer | Fan speed (0-100) |
| `gpus[].status` | String | GPU status: `mining`, `idle`, `error` |

---

### Task Submission

**Endpoint**: `POST /api/v1/submit_task`

**Purpose**: Submit mining task/work unit.

**Status**: 🚧 **Planned** (v0.2.0) - Not yet implemented

**Request**:
```http
POST /api/v1/submit_task HTTP/1.1
Host: localhost:8080
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

{
  "job_id": "12345678",
  "nonce_start": 0,
  "nonce_end": 4294967295,
  "difficulty": 1000000,
  "algorithm": "ethash",
  "pool_url": "stratum+tcp://pool.example.com:3333",
  "wallet": "0x1234567890abcdef",
  "priority": "normal"
}
```

**Response** (202 Accepted):
```json
{
  "task_id": "task-abc123",
  "job_id": "12345678",
  "status": "queued",
  "assigned_gpus": [0, 1],
  "estimated_duration_seconds": 120,
  "queued_at": "2025-09-30T10:30:45Z"
}
```

**Response** (400 Bad Request):
```json
{
  "error": "invalid_request",
  "message": "Invalid nonce range: nonce_start must be < nonce_end",
  "details": {
    "field": "nonce_start",
    "value": 4294967295,
    "constraint": "< nonce_end"
  }
}
```

**Response** (503 Service Unavailable):
```json
{
  "error": "service_unavailable",
  "message": "All GPUs busy, queue full",
  "retry_after_seconds": 30
}
```

**Status Codes**:
- `202 Accepted` - Task queued successfully
- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Missing/invalid authentication
- `503 Service Unavailable` - System overloaded

**Request Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `job_id` | String | Yes | Unique job identifier |
| `nonce_start` | Integer | Yes | Starting nonce (0-2³²) |
| `nonce_end` | Integer | Yes | Ending nonce (0-2³²) |
| `difficulty` | Integer | Yes | Target difficulty |
| `algorithm` | String | Yes | Mining algorithm (`ethash`, `kawpow`) |
| `pool_url` | String | No | Pool URL (optional override) |
| `wallet` | String | No | Wallet address (optional override) |
| `priority` | String | No | Priority: `low`, `normal`, `high` (default: `normal`) |

---

## Request/Response Formats

### Content-Type Headers

**Supported Request Types**:
- `application/json` - JSON payloads (default)
- `text/plain` - Metrics endpoint

**Response Types**:
- `application/json` - JSON responses (API endpoints)
- `text/plain; version=0.0.4` - Prometheus metrics

### JSON Schema

**Health Check Response**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "status": { "type": "string", "enum": ["healthy", "unhealthy"] },
    "timestamp": { "type": "string", "format": "date-time" },
    "uptime_seconds": { "type": "integer", "minimum": 0 },
    "version": { "type": "string" },
    "reason": { "type": "string" }
  },
  "required": ["status", "timestamp"]
}
```

**Status Response**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "status": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "gpus": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "integer" },
          "name": { "type": "string" },
          "hashrate_mhs": { "type": "number" },
          "status": { "type": "string" }
        },
        "required": ["id", "status"]
      }
    }
  },
  "required": ["status", "timestamp", "gpus"]
}
```

---

## Error Codes

### Standard HTTP Status Codes

| Code | Description | Usage |
|------|-------------|-------|
| `200 OK` | Success | GET requests |
| `202 Accepted` | Async operation accepted | POST /submit_task |
| `400 Bad Request` | Invalid input | Validation errors |
| `401 Unauthorized` | Missing/invalid auth | Protected endpoints |
| `404 Not Found` | Endpoint not found | Invalid URL |
| `429 Too Many Requests` | Rate limit exceeded | Excessive requests |
| `500 Internal Server Error` | Server error | Unexpected failures |
| `503 Service Unavailable` | Service degraded | System errors |

### Error Response Format

**Standard Error Response**:
```json
{
  "error": "error_code",
  "message": "Human-readable error description",
  "details": {
    "field": "parameter_name",
    "value": "invalid_value",
    "constraint": "validation_rule"
  },
  "timestamp": "2025-09-30T10:30:45Z",
  "request_id": "req-abc123"
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `invalid_request` | 400 | Malformed request body |
| `validation_error` | 400 | Parameter validation failed |
| `unauthorized` | 401 | Authentication required |
| `forbidden` | 403 | Insufficient permissions |
| `not_found` | 404 | Resource not found |
| `rate_limit_exceeded` | 429 | Too many requests |
| `internal_error` | 500 | Unexpected server error |
| `service_unavailable` | 503 | System degraded/overloaded |
| `gpu_error` | 503 | GPU hardware error |

**Example Error Responses**:

```json
// 400 Bad Request - Validation Error
{
  "error": "validation_error",
  "message": "Invalid nonce range",
  "details": {
    "field": "nonce_end",
    "value": -1,
    "constraint": "must be >= 0 and <= 4294967295"
  },
  "timestamp": "2025-09-30T10:30:45Z"
}

// 503 Service Unavailable - GPU Error
{
  "error": "gpu_error",
  "message": "GPU 0 CUDA driver error",
  "details": {
    "gpu_id": 0,
    "cuda_error": "CUDA_ERROR_INVALID_DEVICE"
  },
  "timestamp": "2025-09-30T10:30:45Z"
}
```

---

## Rate Limiting

### Current Status (v0.1.0-alpha)

**Rate Limiting**: ❌ Not Implemented

**Recommendation**: Use reverse proxy (nginx, Caddy) for rate limiting.

### Planned (v0.2.0)

**Algorithm**: Token Bucket

**Limits**:
- `GET /health`: 100 requests/minute
- `GET /metrics`: 60 requests/minute (Prometheus default)
- `GET /api/v1/status`: 30 requests/minute
- `POST /api/v1/submit_task`: 10 requests/minute

**Response Headers**:
```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1633024845
```

**429 Response**:
```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Retry after 30 seconds",
  "retry_after_seconds": 30,
  "limit": 30,
  "window_seconds": 60
}
```

---

## Examples

### cURL Examples

**Health Check**:
```bash
curl -v http://localhost:8080/health
```

**Prometheus Metrics**:
```bash
curl http://localhost:8080/metrics
```

**System Status**:
```bash
curl http://localhost:8080/api/v1/status | jq
```

**Submit Task** (planned v0.2.0):
```bash
curl -X POST http://localhost:8080/api/v1/submit_task \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "job_id": "12345678",
    "nonce_start": 0,
    "nonce_end": 4294967295,
    "difficulty": 1000000,
    "algorithm": "ethash"
  }'
```

### Python Examples

```python
import requests

# Health check
response = requests.get('http://localhost:8080/health')
print(response.json())

# System status
response = requests.get('http://localhost:8080/api/v1/status')
data = response.json()
print(f"Total Hashrate: {data['mining']['total_hashrate_mhs']} MH/s")

# Submit task (v0.2.0)
task = {
    'job_id': '12345678',
    'nonce_start': 0,
    'nonce_end': 4294967295,
    'difficulty': 1000000,
    'algorithm': 'ethash'
}
headers = {'Authorization': 'Bearer YOUR_TOKEN'}
response = requests.post(
    'http://localhost:8080/api/v1/submit_task',
    json=task,
    headers=headers
)
print(response.json())
```

### Go Examples

```go
package main

import (
    "encoding/json"
    "fmt"
    "net/http"
)

type StatusResponse struct {
    Status    string `json:"status"`
    Timestamp string `json:"timestamp"`
    GPUs      []GPU  `json:"gpus"`
}

type GPU struct {
    ID          int     `json:"id"`
    HashrateMhs float64 `json:"hashrate_mhs"`
    Status      string  `json:"status"`
}

func main() {
    resp, err := http.Get("http://localhost:8080/api/v1/status")
    if err != nil {
        panic(err)
    }
    defer resp.Body.Close()

    var status StatusResponse
    if err := json.NewDecoder(resp.Body).Decode(&status); err != nil {
        panic(err)
    }

    fmt.Printf("Status: %s\n", status.Status)
    for _, gpu := range status.GPUs {
        fmt.Printf("GPU %d: %.2f MH/s (%s)\n",
            gpu.ID, gpu.HashrateMhs, gpu.Status)
    }
}
```

### JavaScript Examples

```javascript
// Health check
fetch('http://localhost:8080/health')
  .then(response => response.json())
  .then(data => console.log('Health:', data.status));

// System status
fetch('http://localhost:8080/api/v1/status')
  .then(response => response.json())
  .then(data => {
    console.log(`Total Hashrate: ${data.mining.total_hashrate_mhs} MH/s`);
    data.gpus.forEach(gpu => {
      console.log(`GPU ${gpu.id}: ${gpu.hashrate_mhs} MH/s (${gpu.temperature_celsius}°C)`);
    });
  });

// Submit task (v0.2.0)
fetch('http://localhost:8080/api/v1/submit_task', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_TOKEN'
  },
  body: JSON.stringify({
    job_id: '12345678',
    nonce_start: 0,
    nonce_end: 4294967295,
    difficulty: 1000000,
    algorithm: 'ethash'
  })
})
  .then(response => response.json())
  .then(data => console.log('Task submitted:', data.task_id));
```

---

## Changelog

### v0.1.0-alpha (2025-09-30)
- ✅ Implemented `/health` endpoint
- ✅ Implemented `/metrics` endpoint
- ✅ Implemented `/api/v1/status` endpoint
- ⏳ Planned `/api/v1/submit_task` endpoint
- ❌ No authentication
- ❌ No rate limiting

### v0.2.0 (Planned)
- 🔜 JWT authentication
- 🔜 Rate limiting (Token Bucket)
- 🔜 `/api/v1/submit_task` endpoint
- 🔜 `/api/v1/auth/login` endpoint
- 🔜 WebSocket support (real-time metrics)

---

**Document Version**: 1.0
**Authors**: OPUS-GPU Team
**License**: MIT
