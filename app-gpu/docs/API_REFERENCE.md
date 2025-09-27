# OPUS-GPU v2.0 API Reference

## Table of Contents
- [Overview](#overview)
- [Authentication](#authentication)
- [Core APIs](#core-apis)
- [GPU Execution APIs](#gpu-execution-apis)
- [Monitoring APIs](#monitoring-apis)
- [Error Codes](#error-codes)
- [Rate Limiting](#rate-limiting)

---

## Overview

OPUS-GPU provides a comprehensive REST API and gRPC interface for GPU compute operations.

**Base URL**: `https://api.opus-gpu.io/v2`  
**Protocol**: HTTPS only  
**Format**: JSON

### Versioning
- Current Version: v2.0
- API Version Header: `X-API-Version: 2.0`
- Backward Compatibility: v1.x endpoints deprecated

---

## Authentication

### Methods

#### 1. API Key Authentication
```http
GET /api/v2/resource
Authorization: Bearer YOUR_API_KEY
```

#### 2. JWT Authentication
```http
POST /auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "secure_password"
}

Response:
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "expires_at": "2024-01-28T00:00:00Z",
  "refresh_token": "..."
}
```

#### 3. mTLS Authentication
Configure client certificate for mutual TLS authentication.

---

## Core APIs

### Task Submission

#### Submit GPU Task
```http
POST /api/v2/tasks
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN

{
  "type": "compute",
  "priority": 5,
  "payload": {
    "kernel": "matrix_multiply",
    "params": {
      "size": 1024,
      "precision": "fp32"
    }
  },
  "requirements": {
    "gpu_memory": 4096,
    "compute_capability": "7.5"
  }
}

Response: 201 Created
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "estimated_completion": "2024-01-27T12:30:00Z",
  "queue_position": 5
}
```

#### Get Task Status
```http
GET /api/v2/tasks/{task_id}
Authorization: Bearer YOUR_TOKEN

Response: 200 OK
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": 45,
  "gpu_assigned": "GPU-0",
  "started_at": "2024-01-27T12:25:00Z",
  "metrics": {
    "gpu_utilization": 85,
    "memory_used": 3500,
    "temperature": 65
  }
}
```

#### Cancel Task
```http
DELETE /api/v2/tasks/{task_id}
Authorization: Bearer YOUR_TOKEN

Response: 204 No Content
```

#### Get Task Result
```http
GET /api/v2/tasks/{task_id}/result
Authorization: Bearer YOUR_TOKEN

Response: 200 OK
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": {
    "output": "base64_encoded_data",
    "format": "tensor",
    "shape": [1024, 1024],
    "dtype": "float32"
  },
  "execution_time_ms": 1234,
  "gpu_time_ms": 1100
}
```

### Batch Operations

#### Submit Batch
```http
POST /api/v2/batches
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN

{
  "name": "training_batch_001",
  "tasks": [
    {
      "type": "training",
      "payload": {...}
    },
    {
      "type": "inference",
      "payload": {...}
    }
  ],
  "dependencies": {
    "0": [],
    "1": [0]
  }
}

Response: 201 Created
{
  "batch_id": "batch_123",
  "total_tasks": 2,
  "status": "pending"
}
```

---

## GPU Execution APIs

### GPU Management

#### List Available GPUs
```http
GET /api/v2/gpus
Authorization: Bearer YOUR_TOKEN

Response: 200 OK
{
  "gpus": [
    {
      "id": "GPU-0",
      "name": "NVIDIA RTX 4090",
      "status": "available",
      "compute_capability": "8.9",
      "memory_total": 24576,
      "memory_available": 20480,
      "utilization": 15,
      "temperature": 42
    }
  ]
}
```

#### Reserve GPU
```http
POST /api/v2/gpus/{gpu_id}/reserve
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN

{
  "duration_minutes": 60,
  "exclusive": true
}

Response: 200 OK
{
  "reservation_id": "res_456",
  "gpu_id": "GPU-0",
  "expires_at": "2024-01-27T13:30:00Z"
}
```

### Kernel Management

#### List Available Kernels
```http
GET /api/v2/kernels
Authorization: Bearer YOUR_TOKEN

Response: 200 OK
{
  "kernels": [
    {
      "name": "matrix_multiply",
      "version": "1.2.0",
      "description": "Optimized matrix multiplication",
      "supported_dtypes": ["fp16", "fp32", "fp64"],
      "required_capability": "7.0"
    }
  ]
}
```

#### Upload Custom Kernel
```http
POST /api/v2/kernels
Content-Type: multipart/form-data
Authorization: Bearer YOUR_TOKEN

--boundary
Content-Disposition: form-data; name="kernel"; filename="custom.cu"
Content-Type: text/plain

[CUDA kernel code]
--boundary
Content-Disposition: form-data; name="metadata"
Content-Type: application/json

{
  "name": "custom_kernel",
  "version": "1.0.0",
  "entry_point": "kernel_main"
}
--boundary--

Response: 201 Created
{
  "kernel_id": "kernel_789",
  "compilation_status": "success",
  "warnings": []
}
```

---

## Monitoring APIs

### Metrics

#### Get System Metrics
```http
GET /api/v2/metrics
Authorization: Bearer YOUR_TOKEN

Response: 200 OK
{
  "timestamp": "2024-01-27T12:00:00Z",
  "system": {
    "tasks_submitted": 1234,
    "tasks_completed": 1200,
    "tasks_failed": 10,
    "avg_latency_ms": 450,
    "queue_depth": 24
  },
  "gpus": [
    {
      "id": "GPU-0",
      "utilization": 75,
      "memory_used": 18432,
      "temperature": 68,
      "power_watts": 320
    }
  ]
}
```

#### Get Prometheus Metrics
```http
GET /metrics
Authorization: Bearer YOUR_TOKEN

Response: 200 OK
# HELP opus_gpu_tasks_total Total number of tasks
# TYPE opus_gpu_tasks_total counter
opus_gpu_tasks_total{status="completed"} 1200
opus_gpu_tasks_total{status="failed"} 10

# HELP opus_gpu_utilization GPU utilization percentage
# TYPE opus_gpu_utilization gauge
opus_gpu_utilization{gpu="0"} 75.5
```

### Health Checks

#### Liveness Probe
```http
GET /health/live

Response: 200 OK
{
  "status": "alive",
  "timestamp": "2024-01-27T12:00:00Z"
}
```

#### Readiness Probe
```http
GET /health/ready

Response: 200 OK
{
  "status": "ready",
  "components": {
    "database": "healthy",
    "gpu": "healthy",
    "scheduler": "healthy"
  }
}
```

---

## Error Codes

| Code | Status | Description | Recovery |
|------|--------|-------------|----------|
| `E001` | 400 | Invalid request format | Check request syntax |
| `E002` | 401 | Authentication failed | Verify credentials |
| `E003` | 403 | Insufficient permissions | Check RBAC roles |
| `E004` | 404 | Resource not found | Verify resource ID |
| `E005` | 409 | Resource conflict | Retry with backoff |
| `E006` | 429 | Rate limit exceeded | Wait before retry |
| `E007` | 500 | Internal server error | Contact support |
| `E008` | 503 | Service unavailable | Check system status |
| `G001` | 507 | GPU memory exhausted | Reduce memory usage |
| `G002` | 508 | No GPU available | Wait or reserve GPU |
| `G003` | 509 | GPU error occurred | Check GPU health |

### Error Response Format
```json
{
  "error": {
    "code": "E002",
    "message": "Authentication failed",
    "details": "Invalid API key",
    "request_id": "req_abc123",
    "timestamp": "2024-01-27T12:00:00Z"
  }
}
```

---

## Rate Limiting

### Default Limits
- **Requests**: 1000 per hour per API key
- **Burst**: 100 requests per minute
- **GPU Time**: 3600 seconds per hour

### Headers
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1706361600
```

### Exceeded Response
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 3600
Content-Type: application/json

{
  "error": {
    "code": "E006",
    "message": "Rate limit exceeded",
    "retry_after_seconds": 3600
  }
}
```

---

## gRPC Service Definition

```protobuf
syntax = "proto3";

package opus.gpu.v2;

service GpuExecutor {
  rpc SubmitTask(TaskRequest) returns (TaskResponse);
  rpc GetTaskStatus(TaskId) returns (TaskStatus);
  rpc StreamResults(TaskId) returns (stream ResultChunk);
  rpc CancelTask(TaskId) returns (Empty);
}

message TaskRequest {
  string type = 1;
  uint32 priority = 2;
  bytes payload = 3;
  Requirements requirements = 4;
}

message Requirements {
  uint32 gpu_memory = 1;
  string compute_capability = 2;
}

message TaskResponse {
  string task_id = 1;
  string status = 2;
  int64 queue_position = 3;
}
```

---

## SDK Examples

### Python
```python
from opus_gpu import Client

client = Client(api_key="YOUR_API_KEY")

# Submit task
task = client.submit_task(
    type="inference",
    payload={"model": "resnet50", "input": data},
    priority=5
)

# Get result
result = client.get_result(task.id)
print(f"Result shape: {result.shape}")
```

### Go
```go
import "github.com/opus-gpu/go-client"

client := opus.NewClient("YOUR_API_KEY")

task, err := client.SubmitTask(&opus.TaskRequest{
    Type:     "inference",
    Priority: 5,
    Payload:  payload,
})

result, err := client.GetResult(task.ID)
```

### Rust
```rust
use opus_gpu::Client;

let client = Client::new("YOUR_API_KEY");

let task = client.submit_task(
    TaskType::Inference,
    payload,
    Priority::Normal
).await?;

let result = client.get_result(&task.id).await?;
```

---

## Webhooks

### Configuration
```http
POST /api/v2/webhooks
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN

{
  "url": "https://your-server.com/webhook",
  "events": ["task.completed", "task.failed"],
  "secret": "webhook_secret"
}
```

### Webhook Payload
```json
{
  "event": "task.completed",
  "timestamp": "2024-01-27T12:00:00Z",
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "execution_time_ms": 1234
  },
  "signature": "sha256=..."
}
```

---

## Migration Guide

### From v1 to v2
1. Update base URL from `/api/v1` to `/api/v2`
2. Replace `device_id` with `gpu_id` in all requests
3. Update authentication header format
4. New response format for batch operations

---

## Support

- **Documentation**: https://docs.opus-gpu.io
- **Status Page**: https://status.opus-gpu.io
- **Support Email**: support@opus-gpu.io
- **Discord**: https://discord.gg/opus-gpu

---

*Last Updated: 2024-01-27*  
*API Version: 2.0.0*
