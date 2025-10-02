# 📊 Phase 4: Performance Monitoring & Benchmark Suite Design

**Document Version**: 1.0
**Date**: 2025-10-02
**Status**: DESIGN - Ready for Implementation
**Author**: Odyssey AI System

---

## 🎯 Executive Summary

Tài liệu này thiết kế **Benchmark Suite** (bộ benchmark – đo hiệu năng hệ thống) và **Monitoring Stack** (stack giám sát – hệ thống theo dõi metrics) cho GPU Mining System, đáp ứng yêu cầu Phase 4 Production Roadmap.

### **Key Deliverables** (Sản phẩm chính)
1. ✅ Benchmark Tool Recommendation: **Criterion.rs + Custom GPU Harness**
2. ✅ Detailed Benchmark Specifications: Ethash, KawPow, Stratum Latency
3. ✅ Baseline Establishment Strategy: Statistical analysis với ±5% variance threshold
4. ✅ Monitoring Architecture: **Prometheus + Grafana** với GPU-specific exporters
5. ✅ Alert Rules: 4 critical conditions với severity levels
6. ✅ Infrastructure Requirements: Docker Compose setup với production-ready configuration

---

## 📋 Table of Contents

1. [Benchmark Tool Selection](#1-benchmark-tool-selection)
2. [Benchmark Design Specifications](#2-benchmark-design-specifications)
3. [Baseline Establishment Strategy](#3-baseline-establishment-strategy)
4. [Performance Monitoring Architecture](#4-performance-monitoring-architecture)
5. [Alerting Rules Framework](#5-alerting-rules-framework)
6. [Infrastructure Requirements](#6-infrastructure-requirements)
7. [Implementation Roadmap](#7-implementation-roadmap)

---

## 1. Benchmark Tool Selection

### 1.1 Decision Matrix

| **Tool** | **Pros** | **Cons** | **GPU Support** | **Verdict** |
|----------|----------|----------|-----------------|-------------|
| **Criterion.rs** | Industry standard, statistical rigor, flamegraphs, HTML reports | CPU-focused, no native GPU metrics | ⚠️ Indirect (via custom hooks) | ✅ **RECOMMENDED** (for CPU/coordination overhead) |
| **Custom GPU Harness** | Direct CUDA profiling, precise GPU metrics, kernel-level instrumentation | Requires development effort, no ecosystem tooling | ✅ Full CUDA support | ✅ **REQUIRED** (for GPU workload) |
| **nvprof/nsys** | Official NVIDIA profiling, kernel timelines, memory analysis | CLI-only, no CI integration, not embeddable | ✅ Full CUDA support | 🔧 **AUXILIARY** (for deep GPU debugging) |
| **rocm-smi** | AMD GPU support | AMD-only, not applicable for NVIDIA-focused system | ⚠️ AMD only | ❌ **NOT APPLICABLE** |

### 1.2 Hybrid Recommendation: **Criterion.rs + Custom GPU Harness**

**Architecture** (Kiến trúc):
```rust
// Criterion.rs → CPU overhead, Stratum latency, system coordination
criterion_group!(benchmarks,
    bench_stratum_getwork_latency,
    bench_share_submission_overhead,
    bench_work_distribution_coordination
);

// Custom GPU Harness → Kernel execution, hashrate, memory bandwidth
#[gpu_benchmark]
async fn bench_ethash_kernel_execution() {
    let miner = EthashMiner::new(device_id, epoch)?;
    let (hashrate, kernel_time, memory_bw) = miner.benchmark_run()?;
    // Record GPU-specific metrics
}
```

**Justification** (Lý do):
- **Criterion.rs**: Best-in-class for CPU-bound operations (Stratum protocol, work scheduling)
- **Custom Harness**: Essential for GPU kernel profiling (kernel execution time, memory bandwidth, warp efficiency)
- **Integration**: Custom GPU metrics can be exported to Criterion-compatible JSON for unified reporting

---

## 2. Benchmark Design Specifications

### 2.1 Ethash Benchmark Suite

#### **2.1.1 Hashrate Benchmark**
```yaml
benchmark:
  name: "ethash_hashrate"
  type: "throughput"
  metrics:
    - hashrate_mh_s: "Target ≥60 MH/s on RTX 3090"
    - gpu_utilization: "Target 95-100%"
    - memory_bandwidth_gb_s: "Track actual vs. theoretical peak"

  test_scenarios:
    - name: "optimal_batch"
      batch_size: 2048
      dag_epoch: 500  # ~2GB DAG size
      duration_secs: 30

    - name: "large_dag"
      batch_size: 2048
      dag_epoch: 1000  # ~4GB DAG size
      duration_secs: 30

    - name: "variable_batch"
      batch_sizes: [512, 1024, 2048, 4096]
      dag_epoch: 500
      iterations_per_size: 100

  acceptance_criteria:
    hashrate_target: ">= 60 MH/s"
    gpu_util_target: ">= 95%"
    variance_threshold: "± 5%"
    stability: "No >10% drops over 5 minute period"
```

**Implementation Note** (Ghi chú triển khai):
```rust
// Sử dụng CUDA Events cho chính xác timing
cudaEvent_t start, stop;
cudaEventCreate(&start);
cudaEventCreate(&stop);

cudaEventRecord(start);
// Execute Ethash kernel
ethash_search<<<grid, block>>>(header, target, dag, results);
cudaEventRecord(stop);
cudaEventSynchronize(stop);

float kernel_time_ms;
cudaEventElapsedTime(&kernel_time_ms, start, stop);

// Calculate metrics
double hashrate_mh = (batch_size * 1000.0) / (kernel_time_ms * 1e6);
double gpu_util = query_gpu_utilization(device_id);
double memory_bw = query_memory_bandwidth(device_id);
```

---

#### **2.1.2 Memory Bandwidth Benchmark**
```yaml
benchmark:
  name: "ethash_memory_bandwidth"
  type: "resource_utilization"
  metrics:
    - memory_read_gb_s: "Track DAG access efficiency"
    - memory_write_gb_s: "Track result buffer writes"
    - cache_hit_ratio: "L1/L2 cache effectiveness"

  test_scenarios:
    - name: "dag_access_pattern"
      description: "Measure memory bandwidth during DAG lookups"
      dag_sizes: [2GB, 4GB, 6GB]
      access_patterns: ["sequential", "random"]

    - name: "memory_contention"
      description: "Concurrent GPU memory operations"
      concurrent_kernels: [1, 2, 4]
      duration_secs: 10

  acceptance_criteria:
    memory_bw_utilization: ">= 80% of theoretical peak"
    cache_hit_ratio: ">= 90% for L2"
    contention_overhead: "<= 15%"
```

**GPU Profiling Command** (Lệnh profiling GPU):
```bash
# Use nsys/nvprof for deep analysis
nsys profile --stats=true ./mining-benchmark ethash_memory_bw

# Output: Timeline view, memory transactions, warp execution
```

---

### 2.2 KawPow Benchmark Suite

#### **2.2.1 Hashrate Benchmark**
```yaml
benchmark:
  name: "kawpow_hashrate"
  type: "throughput"
  metrics:
    - hashrate_mh_s: "Target ≥30 MH/s on RTX 3090"
    - kernel_execution_time_ms: "Per-kernel timing"
    - power_consumption_watts: "Power efficiency (H/W)"

  test_scenarios:
    - name: "varying_difficulty"
      difficulty_targets: ["1e6", "1e7", "1e8", "1e9"]
      batch_size: 1024
      iterations: 100

    - name: "long_running_stability"
      duration_secs: 300  # 5 minutes
      batch_size: 1024
      sample_interval_secs: 10

  acceptance_criteria:
    hashrate_target: ">= 30 MH/s"
    power_efficiency: ">= 0.12 MH/W"
    variance_threshold: "± 5%"
    thermal_stability: "<= 85°C sustained"
```

**Kernel Execution Timing** (Đo thời gian kernel):
```rust
// Track individual KawPow kernel stages
let stages = [
    "keccak_initial",
    "progpow_loop",
    "keccak_final"
];

for stage in stages {
    let kernel_time = measure_kernel_stage(stage);
    metrics.record_kernel_time(stage, kernel_time);
}
```

---

### 2.3 Stratum Latency Benchmark

#### **2.3.1 Getwork Latency**
```yaml
benchmark:
  name: "stratum_getwork_latency"
  type: "latency"
  metrics:
    - getwork_latency_ms: "Time from request to job received"
    - network_rtt_ms: "Round-trip time to pool"
    - job_processing_latency_ms: "Job parsing and validation"

  test_scenarios:
    - name: "local_pool_simulation"
      network_latency: 0  # Localhost
      iterations: 1000

    - name: "realistic_network"
      network_latencies: [10ms, 50ms, 100ms, 200ms]
      packet_loss: [0%, 1%, 5%]
      iterations: 500_per_condition

    - name: "pool_reconnection"
      disconnect_trigger: "After 10 getwork requests"
      measure_reconnect_time: true

  acceptance_criteria:
    getwork_p50: "<= 50ms (local), <= 150ms (network)"
    getwork_p95: "<= 100ms (local), <= 300ms (network)"
    getwork_p99: "<= 200ms (local), <= 500ms (network)"
    reconnect_time: "<= 5 seconds"
```

**Network Simulation** (Mô phỏng mạng):
```rust
// Sử dụng tokio::time::sleep để simulate network latency
async fn simulate_network_latency(latency_ms: u64) {
    tokio::time::sleep(Duration::from_millis(latency_ms)).await;
}

// Benchmark với varying latencies
for latency in [10, 50, 100, 200] {
    let start = Instant::now();

    // Simulate getwork request
    simulate_network_latency(latency).await;
    let job = stratum_client.get_work().await?;

    let elapsed = start.elapsed();
    metrics.record_getwork_latency(elapsed.as_millis());
}
```

---

#### **2.3.2 Share Submission Latency**
```yaml
benchmark:
  name: "stratum_share_submission"
  type: "latency"
  metrics:
    - submission_latency_ms: "Time from share found to pool ACK"
    - serialization_overhead_us: "JSON serialization time"
    - network_transmission_ms: "Network send time"

  test_scenarios:
    - name: "high_frequency_submission"
      shares_per_second: [1, 10, 50, 100]
      duration_secs: 30

    - name: "concurrent_devices"
      device_count: [1, 2, 4, 8]
      shares_per_device_per_sec: 10

  acceptance_criteria:
    submission_p50: "<= 100ms"
    submission_p95: "<= 200ms"
    serialization_overhead: "<= 1ms"
    stale_share_rate: "<= 2%"
```

**Stale Rate Calculation** (Tính tỷ lệ stale):
```rust
fn calculate_stale_rate(submission_latency_ms: f64, pool_job_interval_ms: f64) -> f64 {
    // Stale if submission time > pool job refresh interval
    if submission_latency_ms > pool_job_interval_ms {
        1.0  // 100% stale
    } else {
        submission_latency_ms / pool_job_interval_ms
    }
}
```

---

## 3. Baseline Establishment Strategy

### 3.1 Statistical Methodology

**Approach** (Phương pháp): Multi-run statistical analysis với confidence intervals

```yaml
baseline_establishment:
  methodology:
    name: "Bootstrap Confidence Intervals"
    description: "Resampling technique for robust baseline estimation"

  execution_plan:
    - step: "Initial Calibration Run"
      iterations: 100
      environment: "Controlled (no background load)"
      discard: "First 10 samples (warmup)"

    - step: "Statistical Analysis"
      calculations:
        - mean: "Arithmetic mean of 90 samples"
        - stddev: "Standard deviation"
        - percentiles: [50, 95, 99]
        - coefficient_of_variation: "stddev / mean"

    - step: "Baseline Recording"
      output_format: "JSON"
      fields:
        - metric_name
        - mean_value
        - stddev
        - p50, p95, p99
        - timestamp
        - environment_metadata:
            - gpu_model
            - cuda_version
            - driver_version
            - dag_epoch
            - batch_size

  acceptance_variance: "± 5%"
  outlier_detection: "Chauvenet's criterion (3σ)"
  rebaseline_triggers:
    - system_upgrade: "Driver, CUDA, hardware changes"
    - algorithm_change: "Kernel optimization, tuning"
    - periodic: "Every 30 days for drift detection"
```

### 3.2 Baseline Storage Format

```json
{
  "baseline_version": "1.0",
  "timestamp": "2025-10-02T14:30:00Z",
  "system_info": {
    "gpu_model": "NVIDIA GeForce RTX 3090",
    "cuda_version": "12.3",
    "driver_version": "545.29.06",
    "memory_gb": 24,
    "compute_capability": "8.6"
  },
  "benchmarks": [
    {
      "name": "ethash_hashrate",
      "unit": "MH/s",
      "statistics": {
        "mean": 62.5,
        "stddev": 1.8,
        "p50": 62.3,
        "p95": 65.1,
        "p99": 66.0,
        "coefficient_of_variation": 0.029
      },
      "test_conditions": {
        "dag_epoch": 500,
        "batch_size": 2048,
        "iterations": 100
      }
    },
    {
      "name": "kawpow_hashrate",
      "unit": "MH/s",
      "statistics": {
        "mean": 31.2,
        "stddev": 0.9,
        "p50": 31.1,
        "p95": 32.5,
        "p99": 33.0,
        "coefficient_of_variation": 0.029
      },
      "test_conditions": {
        "difficulty": "1e7",
        "batch_size": 1024,
        "iterations": 100
      }
    },
    {
      "name": "stratum_getwork_latency",
      "unit": "ms",
      "statistics": {
        "mean": 45.0,
        "stddev": 5.2,
        "p50": 44.0,
        "p95": 52.0,
        "p99": 58.0,
        "coefficient_of_variation": 0.116
      },
      "test_conditions": {
        "network_latency_ms": 10,
        "iterations": 1000
      }
    }
  ],
  "acceptance_criteria": {
    "variance_threshold": 0.05,
    "outlier_method": "chauvenet_3sigma"
  }
}
```

---

## 4. Performance Monitoring Architecture

### 4.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    GPU Mining Application                   │
│  ┌───────────────────────────────────────────────────────┐ │
│  │           Prometheus Exporter (Port 9100)             │ │
│  │  ┌────────────┬──────────────┬────────────────────┐  │ │
│  │  │ GPU Metrics│Stratum Metrics│ System Metrics    │  │ │
│  │  │ (nvml)     │ (shares)     │ (CPU, mem, disk)  │  │ │
│  │  └────────────┴──────────────┴────────────────────┘  │ │
│  └───────────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP /metrics (Pull)
                       ↓
         ┌──────────────────────────────┐
         │    Prometheus Server         │
         │      (Port 9090)             │
         │  ┌────────────────────────┐  │
         │  │  Scrape Config:        │  │
         │  │  - interval: 10s       │  │
         │  │  - retention: 30 days  │  │
         │  │  - storage: 100GB      │  │
         │  └────────────────────────┘  │
         │  ┌────────────────────────┐  │
         │  │  Alert Manager         │  │
         │  │  - Rules evaluation    │  │
         │  │  - Notification routing│  │
         │  └────────────────────────┘  │
         └──────────────┬───────────────┘
                        │ PromQL Queries
                        ↓
              ┌───────────────────────────┐
              │   Grafana Dashboard       │
              │     (Port 3000)           │
              │  ┌─────────────────────┐  │
              │  │ Panels:             │  │
              │  │ - Hashrate Graph    │  │
              │  │ - GPU Heatmap       │  │
              │  │ - Pool Status       │  │
              │  │ - Alert Feed        │  │
              │  └─────────────────────┘  │
              └───────────────────────────┘
```

---

### 4.2 Prometheus Metrics Specification

#### **4.2.1 Core Metrics to Expose**

```yaml
metrics:
  # Hashrate Metrics (Metrics Hashrate)
  - name: mining_hashrate_mhs
    type: gauge
    labels: [device_id, algorithm]
    description: "Current hashrate in MH/s per GPU"

  - name: mining_hashrate_peak_mhs
    type: gauge
    labels: [device_id, algorithm]
    description: "Peak hashrate achieved"

  - name: mining_hashrate_average_1m_mhs
    type: gauge
    labels: [device_id, algorithm]
    description: "1-minute moving average hashrate"

  # Share Metrics (Metrics Share)
  - name: mining_shares_submitted_total
    type: counter
    labels: [device_id, pool]
    description: "Total shares submitted"

  - name: mining_shares_accepted_total
    type: counter
    labels: [device_id, pool]
    description: "Total shares accepted"

  - name: mining_shares_rejected_total
    type: counter
    labels: [device_id, pool, reason]
    description: "Total shares rejected"

  - name: mining_shares_stale_total
    type: counter
    labels: [device_id, pool]
    description: "Total stale shares"

  - name: mining_share_acceptance_rate
    type: gauge
    labels: [device_id, pool]
    description: "Share acceptance rate (0-1)"

  # GPU Health Metrics (Metrics Sức Khỏe GPU)
  - name: gpu_temperature_celsius
    type: gauge
    labels: [device_id, gpu_model]
    description: "GPU temperature in °C"

  - name: gpu_utilization_percent
    type: gauge
    labels: [device_id, gpu_model]
    description: "GPU utilization (0-100)"

  - name: gpu_memory_used_bytes
    type: gauge
    labels: [device_id, gpu_model]
    description: "GPU memory used in bytes"

  - name: gpu_memory_total_bytes
    type: gauge
    labels: [device_id, gpu_model]
    description: "Total GPU memory"

  - name: gpu_power_usage_watts
    type: gauge
    labels: [device_id, gpu_model]
    description: "Power consumption in watts"

  - name: gpu_fan_speed_percent
    type: gauge
    labels: [device_id]
    description: "Fan speed (0-100)"

  # Stratum Metrics (Metrics Stratum)
  - name: stratum_connection_status
    type: gauge
    labels: [pool_url]
    description: "Connection status (1=connected, 0=disconnected)"

  - name: stratum_getwork_latency_ms
    type: histogram
    labels: [pool_url]
    buckets: [10, 25, 50, 100, 200, 500, 1000]
    description: "Getwork latency distribution"

  - name: stratum_share_submission_latency_ms
    type: histogram
    labels: [pool_url]
    buckets: [10, 25, 50, 100, 200, 500]
    description: "Share submission latency"

  - name: stratum_reconnects_total
    type: counter
    labels: [pool_url, reason]
    description: "Total pool reconnections"

  - name: stratum_job_received_total
    type: counter
    labels: [pool_url]
    description: "Total jobs received from pool"

  # System Metrics (Metrics Hệ Thống)
  - name: mining_uptime_seconds
    type: counter
    description: "Total mining uptime"

  - name: mining_restarts_total
    type: counter
    labels: [reason]
    description: "Total mining restarts"

  - name: system_cpu_usage_percent
    type: gauge
    description: "System CPU usage"

  - name: system_memory_used_bytes
    type: gauge
    description: "System memory used"
```

---

#### **4.2.2 Prometheus Exporter Implementation**

**Strategy** (Chiến lược): **Push-based exporter** tích hợp trong mining application

```rust
// crates/coordination/src/monitoring/prometheus_exporter.rs

use prometheus::{
    register_gauge_vec, register_counter_vec, register_histogram_vec,
    GaugeVec, CounterVec, HistogramVec, Encoder, TextEncoder
};
use std::sync::Arc;
use tokio::sync::RwLock;

pub struct PrometheusExporter {
    // Hashrate metrics
    hashrate_gauge: GaugeVec,
    hashrate_avg_1m: GaugeVec,

    // Share metrics
    shares_submitted: CounterVec,
    shares_accepted: CounterVec,
    shares_rejected: CounterVec,
    share_acceptance_rate: GaugeVec,

    // GPU metrics
    gpu_temperature: GaugeVec,
    gpu_utilization: GaugeVec,
    gpu_memory_used: GaugeVec,
    gpu_power: GaugeVec,

    // Stratum metrics
    stratum_latency: HistogramVec,
    stratum_reconnects: CounterVec,

    // HTTP server handle
    http_server: Option<tokio::task::JoinHandle<()>>,
}

impl PrometheusExporter {
    pub fn new() -> anyhow::Result<Self> {
        let hashrate_gauge = register_gauge_vec!(
            "mining_hashrate_mhs",
            "Current hashrate in MH/s",
            &["device_id", "algorithm"]
        )?;

        let shares_submitted = register_counter_vec!(
            "mining_shares_submitted_total",
            "Total shares submitted",
            &["device_id", "pool"]
        )?;

        let gpu_temperature = register_gauge_vec!(
            "gpu_temperature_celsius",
            "GPU temperature",
            &["device_id", "gpu_model"]
        )?;

        let stratum_latency = register_histogram_vec!(
            "stratum_getwork_latency_ms",
            "Getwork latency",
            &["pool_url"],
            vec![10.0, 25.0, 50.0, 100.0, 200.0, 500.0, 1000.0]
        )?;

        // Initialize other metrics...

        Ok(Self {
            hashrate_gauge,
            shares_submitted,
            gpu_temperature,
            stratum_latency,
            // ... other fields
            http_server: None,
        })
    }

    /// Start HTTP server on port 9100 exposing /metrics endpoint
    pub async fn start_http_server(&mut self, bind_addr: &str) -> anyhow::Result<()> {
        use warp::Filter;

        let metrics_route = warp::path!("metrics")
            .map(|| {
                let encoder = TextEncoder::new();
                let metric_families = prometheus::gather();
                let mut buffer = vec![];
                encoder.encode(&metric_families, &mut buffer).unwrap();
                String::from_utf8(buffer).unwrap()
            });

        let server = warp::serve(metrics_route)
            .run(bind_addr.parse::<std::net::SocketAddr>()?);

        self.http_server = Some(tokio::spawn(server));
        tracing::info!("📊 Prometheus exporter started on {}/metrics", bind_addr);
        Ok(())
    }

    /// Update hashrate metric for specific device
    pub fn update_hashrate(&self, device_id: usize, algorithm: &str, hashrate_mh: f64) {
        self.hashrate_gauge
            .with_label_values(&[&device_id.to_string(), algorithm])
            .set(hashrate_mh);
    }

    /// Record share submission
    pub fn record_share_submitted(&self, device_id: usize, pool: &str) {
        self.shares_submitted
            .with_label_values(&[&device_id.to_string(), pool])
            .inc();
    }

    /// Update GPU temperature
    pub fn update_gpu_temperature(&self, device_id: usize, gpu_model: &str, temp_celsius: f32) {
        self.gpu_temperature
            .with_label_values(&[&device_id.to_string(), gpu_model])
            .set(temp_celsius as f64);
    }

    /// Record Stratum latency
    pub fn observe_stratum_latency(&self, pool_url: &str, latency_ms: f64) {
        self.stratum_latency
            .with_label_values(&[pool_url])
            .observe(latency_ms);
    }
}
```

---

### 4.3 Scraping Strategy

**Approach** (Phương pháp): **Pull model** (Prometheus scrapes exporter)

```yaml
prometheus_scrape_config:
  job_name: "gpu-mining"
  scrape_interval: 10s      # Thu thập mỗi 10 giây
  scrape_timeout: 5s        # Timeout sau 5 giây
  metrics_path: "/metrics"  # HTTP endpoint

  static_configs:
    - targets:
        - "mining-node-1:9100"
        - "mining-node-2:9100"
        - "mining-node-3:9100"
      labels:
        cluster: "production"
        environment: "main"

  relabel_configs:
    - source_labels: [__address__]
      target_label: instance

    - source_labels: [__address__]
      regex: "([^:]+):(.*)"
      target_label: node
      replacement: "$1"
```

**Justification cho Pull Model**:
- ✅ **Simplicity**: No need for mining nodes to know Prometheus location
- ✅ **Scalability**: Prometheus controls load, rate limiting built-in
- ✅ **Reliability**: Failed scrapes tracked automatically
- ✅ **Security**: No outbound connections from mining nodes required

---

### 4.4 Data Retention Policy

```yaml
data_retention:
  strategy: "Tiered Storage"

  tiers:
    - name: "hot_storage"
      duration: "7 days"
      resolution: "10s"  # Raw scrape interval
      storage_backend: "Prometheus TSDB (local SSD)"
      estimated_size: "~5GB per node per week"

    - name: "warm_storage"
      duration: "30 days"
      resolution: "1m"   # Downsampled to 1-minute averages
      storage_backend: "Prometheus (spinning disk)"
      estimated_size: "~10GB per node per month"

    - name: "cold_storage"
      duration: "1 year"
      resolution: "5m"   # Downsampled to 5-minute averages
      storage_backend: "S3-compatible object storage"
      estimated_size: "~30GB per node per year"
      compression: "gzip"

  downsampling_rules:
    - metric_pattern: "mining_hashrate_*"
      aggregation: "avg"  # Average hashrate over window

    - metric_pattern: "gpu_temperature_*"
      aggregation: "max"  # Peak temperature in window

    - metric_pattern: "mining_shares_*_total"
      aggregation: "delta"  # Rate of change
```

---

### 4.5 Grafana Dashboard Design

#### **Dashboard Layout** (Bố cục dashboard)

```
┌────────────────────────────────────────────────────────────────┐
│  GPU Mining Performance Dashboard                              │
│  Last Updated: 2s ago  │  Time Range: Last 1h  │  Refresh: 5s │
├────────────────────────────────────────────────────────────────┤
│  Row 1: Hashrate Overview                                      │
│  ┌───────────────────────┬───────────────────────────────────┐│
│  │ Total Hashrate        │ Hashrate per GPU (Line Chart)    ││
│  │ 180.5 MH/s           │ [Graph with 3 lines: GPU 0,1,2] ││
│  │ ↑ +2.3% from 1h ago   │ [X-axis: Time, Y-axis: MH/s]     ││
│  └───────────────────────┴───────────────────────────────────┘│
├────────────────────────────────────────────────────────────────┤
│  Row 2: Share Statistics                                       │
│  ┌──────────┬──────────┬──────────┬───────────────────────────┐│
│  │ Accepted │ Rejected │ Stale    │ Acceptance Rate (Gauge)  ││
│  │ 1,234    │ 5        │ 12       │ [Gauge: 98.6%]           ││
│  │ ↑ +15/h  │ ⚠️ +2/h   │ ↑ +1/h   │ Target: >95%             ││
│  └──────────┴──────────┴──────────┴───────────────────────────┘│
├────────────────────────────────────────────────────────────────┤
│  Row 3: GPU Health Monitoring                                  │
│  ┌───────────────────────────────────────────────────────────┐│
│  │ GPU Temperature Heatmap (Colored by severity)            ││
│  │ [Heatmap: GPU 0,1,2 × Temperature over time]            ││
│  │ Green: <75°C | Yellow: 75-80°C | Red: >80°C             ││
│  └───────────────────────────────────────────────────────────┘│
│  ┌──────────────────────┬────────────────────────────────────┐│
│  │ GPU Utilization      │ Memory Usage per GPU              ││
│  │ [Stacked Area Chart] │ [Bar Chart: Used/Total MB]        ││
│  └──────────────────────┴────────────────────────────────────┘│
├────────────────────────────────────────────────────────────────┤
│  Row 4: Pool Status                                            │
│  ┌──────────────────────┬────────────────────────────────────┐│
│  │ Pool Connection      │ Stratum Latency (Histogram)       ││
│  │ ✅ Connected         │ [Histogram: P50, P95, P99]        ││
│  │ Uptime: 12h 34m      │ P95: 85ms (Target: <200ms)        ││
│  └──────────────────────┴────────────────────────────────────┘│
│  ┌───────────────────────────────────────────────────────────┐│
│  │ Reconnection Events (Timeline)                           ││
│  │ [Event markers on timeline showing disconnect reasons]   ││
│  └───────────────────────────────────────────────────────────┘│
├────────────────────────────────────────────────────────────────┤
│  Row 5: System Resources                                       │
│  ┌──────────────────────┬────────────────────────────────────┐│
│  │ CPU Usage            │ System Memory                     ││
│  │ [Line Chart: 8%]     │ [Gauge: 4.2GB / 16GB]             ││
│  └──────────────────────┴────────────────────────────────────┘│
├────────────────────────────────────────────────────────────────┤
│  Row 6: Active Alerts                                          │
│  ┌───────────────────────────────────────────────────────────┐│
│  │ 🔥 CRITICAL: GPU 1 temperature 87°C (threshold: 85°C)    ││
│  │ ⚠️  WARNING: Share rejection rate 6.2% on pool-1         ││
│  └───────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────┘
```

---

#### **Key PromQL Queries** (Truy vấn PromQL chính)

```promql
# Total hashrate across all GPUs
sum(mining_hashrate_mhs{cluster="production"})

# Per-GPU hashrate with 1-minute average
avg_over_time(mining_hashrate_mhs{device_id="0"}[1m])

# Share acceptance rate (percentage)
(
  sum(rate(mining_shares_accepted_total[5m]))
  /
  sum(rate(mining_shares_submitted_total[5m]))
) * 100

# GPU temperature heatmap (max temp per GPU over time)
max_over_time(gpu_temperature_celsius[1m])

# Stratum latency P95
histogram_quantile(0.95, rate(stratum_getwork_latency_ms_bucket[5m]))

# Pool reconnection rate (events per hour)
rate(stratum_reconnects_total[1h]) * 3600

# Hashrate drop detection (>15% drop in 5 minutes)
(
  mining_hashrate_mhs{device_id="0"}
  -
  mining_hashrate_mhs{device_id="0"} offset 5m
)
/
mining_hashrate_mhs{device_id="0"} offset 5m
< -0.15
```

---

## 5. Alerting Rules Framework

### 5.1 Alert Rule Definitions

```yaml
alerting_rules:
  # CRITICAL Alerts (Cảnh báo NGHIÊM TRỌNG)
  - alert: "HighGPUTemperature"
    severity: critical
    condition: |
      gpu_temperature_celsius > 85
      FOR 5m
    description: "GPU {{ $labels.device_id }} temperature {{ $value }}°C exceeds 85°C threshold"
    actions:
      - notification: ["email", "slack", "pagerduty"]
      - auto_action: "reduce_power_limit_to_80_percent"

  - alert: "HashrateDropSignificant"
    severity: critical
    condition: |
      (
        (mining_hashrate_mhs - mining_hashrate_mhs offset 5m)
        / mining_hashrate_mhs offset 5m
      ) < -0.15
      FOR 5m
    description: "Hashrate dropped {{ $value | humanizePercentage }} on GPU {{ $labels.device_id }}"
    actions:
      - notification: ["email", "slack"]
      - auto_action: "restart_mining_worker"

  - alert: "StratumDisconnected"
    severity: critical
    condition: |
      stratum_connection_status == 0
      FOR 2m
    description: "Pool {{ $labels.pool_url }} disconnected for >2 minutes"
    actions:
      - notification: ["email", "slack"]
      - auto_action: "attempt_reconnection"

  # HIGH Priority Alerts (Cảnh báo ƯU TIÊN CAO)
  - alert: "HighShareRejectionRate"
    severity: high
    condition: |
      (
        sum(rate(mining_shares_rejected_total[5m]))
        / sum(rate(mining_shares_submitted_total[5m]))
      ) > 0.05
      FOR 5m
    description: "Share rejection rate {{ $value | humanizePercentage }} exceeds 5% threshold"
    actions:
      - notification: ["slack"]
      - auto_action: "log_rejection_reasons"

  - alert: "FrequentPoolReconnects"
    severity: high
    condition: |
      rate(stratum_reconnects_total[1h]) * 3600 > 3
    description: "Pool reconnections: {{ $value }} times per hour (threshold: 3)"
    actions:
      - notification: ["slack"]
      - auto_action: "check_network_connectivity"

  # MEDIUM Priority Alerts (Cảnh báo ƯU TIÊN TRUNG BÌNH)
  - alert: "GPUUtilizationLow"
    severity: medium
    condition: |
      gpu_utilization_percent < 85
      FOR 10m
    description: "GPU {{ $labels.device_id }} utilization {{ $value }}% below 85% target"
    actions:
      - notification: ["slack"]
      - auto_action: "increase_batch_size"

  - alert: "StratumLatencyHigh"
    severity: medium
    condition: |
      histogram_quantile(0.95, rate(stratum_getwork_latency_ms_bucket[5m])) > 200
      FOR 10m
    description: "Stratum P95 latency {{ $value }}ms exceeds 200ms threshold"
    actions:
      - notification: ["slack"]
```

---

### 5.2 Notification Channels

```yaml
notification_channels:
  slack:
    webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    channel: "#gpu-mining-alerts"
    mention_on_critical: "@oncall-team"

  email:
    smtp_server: "smtp.gmail.com:587"
    from: "mining-alerts@company.com"
    to: ["ops-team@company.com", "devops@company.com"]
    subject_template: "[{{ .Severity | toUpper }}] Mining Alert: {{ .AlertName }}"

  pagerduty:
    integration_key: "YOUR_PAGERDUTY_KEY"
    service_name: "GPU Mining Production"
    escalation_policy: "Immediate Escalation"

  webhook:
    url: "https://internal-api.company.com/alerts"
    method: POST
    headers:
      - "Content-Type: application/json"
      - "Authorization: Bearer YOUR_TOKEN"
```

---

### 5.3 Alert Severity Matrix

| **Severity** | **Response Time** | **Notification Channels** | **Auto-Action** | **Escalation** |
|--------------|-------------------|---------------------------|-----------------|----------------|
| **CRITICAL** | Immediate | Email + Slack + PagerDuty | Yes (automatic mitigation) | After 5 min if unresolved |
| **HIGH** | Within 15 min | Email + Slack | Yes (diagnostic) | After 30 min if unresolved |
| **MEDIUM** | Within 1 hour | Slack only | Optional | Manual escalation |
| **LOW** | Next business day | Dashboard only | No | No escalation |

---

## 6. Infrastructure Requirements

### 6.1 Docker Compose Stack

```yaml
version: "3.8"

services:
  # GPU Mining Application
  mining-app:
    image: opus-gpu-mining:latest
    container_name: mining-node-1
    runtime: nvidia  # NVIDIA Container Toolkit
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - PROMETHEUS_EXPORTER_PORT=9100
    ports:
      - "9100:9100"  # Prometheus exporter
    volumes:
      - ./config/mining-config.toml:/app/config.toml:ro
      - ./data/wallet:/app/wallet:ro
    networks:
      - monitoring
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  # Prometheus Server
  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"
      - "--storage.tsdb.retention.time=30d"
      - "--web.console.libraries=/usr/share/prometheus/console_libraries"
      - "--web.console.templates=/usr/share/prometheus/consoles"
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./config/alert-rules.yml:/etc/prometheus/alert-rules.yml:ro
      - prometheus-data:/prometheus
    networks:
      - monitoring
    restart: unless-stopped
    depends_on:
      - mining-app

  # Grafana Dashboard
  grafana:
    image: grafana/grafana:10.2.0
    container_name: grafana
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=secure_password_here
      - GF_USERS_ALLOW_SIGN_UP=false
    ports:
      - "3000:3000"
    volumes:
      - ./config/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./config/grafana/datasources:/etc/grafana/provisioning/datasources:ro
      - grafana-data:/var/lib/grafana
    networks:
      - monitoring
    restart: unless-stopped
    depends_on:
      - prometheus

  # Alert Manager (Optional)
  alertmanager:
    image: prom/alertmanager:v0.26.0
    container_name: alertmanager
    command:
      - "--config.file=/etc/alertmanager/alertmanager.yml"
      - "--storage.path=/alertmanager"
    ports:
      - "9093:9093"
    volumes:
      - ./config/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
      - alertmanager-data:/alertmanager
    networks:
      - monitoring
    restart: unless-stopped

networks:
  monitoring:
    driver: bridge

volumes:
  prometheus-data:
    driver: local
  grafana-data:
    driver: local
  alertmanager-data:
    driver: local
```

---

### 6.2 Configuration Files

#### **prometheus.yml** (Cấu hình Prometheus)

```yaml
global:
  scrape_interval: 10s      # Thu thập mỗi 10 giây
  evaluation_interval: 10s  # Đánh giá alert mỗi 10 giây

# Alert Manager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - "alertmanager:9093"

# Alert rules
rule_files:
  - "/etc/prometheus/alert-rules.yml"

# Scrape configurations
scrape_configs:
  - job_name: "gpu-mining"
    static_configs:
      - targets:
          - "mining-app:9100"
        labels:
          cluster: "production"
          instance: "mining-node-1"

    scrape_interval: 10s
    scrape_timeout: 5s
    metrics_path: "/metrics"

  # Prometheus self-monitoring
  - job_name: "prometheus"
    static_configs:
      - targets:
          - "localhost:9090"
```

---

#### **alert-rules.yml** (Quy tắc cảnh báo)

```yaml
groups:
  - name: gpu_mining_alerts
    interval: 10s
    rules:
      # Critical: GPU Temperature
      - alert: HighGPUTemperature
        expr: gpu_temperature_celsius > 85
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "GPU {{ $labels.device_id }} overheating"
          description: "Temperature {{ $value }}°C exceeds 85°C for >5 minutes"

      # Critical: Hashrate Drop
      - alert: HashrateDropSignificant
        expr: |
          (
            (mining_hashrate_mhs - mining_hashrate_mhs offset 5m)
            / (mining_hashrate_mhs offset 5m)
          ) < -0.15
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Hashrate dropped >15% on GPU {{ $labels.device_id }}"
          description: "Current: {{ $value | humanize }}%"

      # High: Share Rejection
      - alert: HighShareRejectionRate
        expr: |
          (
            sum(rate(mining_shares_rejected_total[5m]))
            / sum(rate(mining_shares_submitted_total[5m]))
          ) > 0.05
        for: 5m
        labels:
          severity: high
        annotations:
          summary: "High share rejection rate"
          description: "Rejection rate: {{ $value | humanizePercentage }}"

      # High: Frequent Reconnects
      - alert: FrequentPoolReconnects
        expr: rate(stratum_reconnects_total[1h]) * 3600 > 3
        for: 10m
        labels:
          severity: high
        annotations:
          summary: "Frequent pool reconnections"
          description: "{{ $value }} reconnects per hour"
```

---

#### **alertmanager.yml** (Cấu hình Alert Manager)

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'

  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
      continue: true

    - match:
        severity: high
      receiver: 'high-alerts'
      continue: true

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://internal-api.company.com/alerts'

  - name: 'critical-alerts'
    email_configs:
      - to: 'ops-team@company.com'
        from: 'mining-alerts@company.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'mining-alerts@company.com'
        auth_password: 'YOUR_PASSWORD'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#gpu-mining-alerts'
        text: '🔥 CRITICAL: {{ .CommonAnnotations.summary }}'

  - name: 'high-alerts'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#gpu-mining-alerts'
        text: '⚠️ HIGH: {{ .CommonAnnotations.summary }}'
```

---

### 6.3 Storage Requirements

| **Component** | **Storage Type** | **Size** | **IOPS** | **Retention** |
|---------------|------------------|----------|----------|---------------|
| **Prometheus TSDB** | SSD (local) | 100GB | 1000+ | 30 days hot |
| **Grafana Database** | SSD (local) | 10GB | 500+ | N/A (persistent config) |
| **AlertManager Data** | HDD | 5GB | 100+ | 7 days |
| **Benchmark Results** | SSD | 20GB | 500+ | 90 days (JSON archives) |

**Total Storage**: ~135GB per mining node

**Scaling Calculation** (Tính toán mở rộng):
- Prometheus: ~5GB per node per week → 20GB per month
- 10 mining nodes → 200GB per month
- With 30-day retention → ~250GB total for production cluster

---

### 6.4 Network Topology

```
┌──────────────────────────────────────────────────────────────┐
│                    Production Network                        │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │ Mining     │  │ Mining     │  │ Mining     │           │
│  │ Node 1     │  │ Node 2     │  │ Node 3     │           │
│  │ :9100      │  │ :9100      │  │ :9100      │           │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘           │
│        │                │                │                  │
│        └────────────────┴────────────────┘                  │
│                         │                                   │
│                         ↓ HTTP Pull (10s interval)          │
│               ┌─────────────────┐                           │
│               │   Prometheus    │                           │
│               │     :9090       │                           │
│               └────────┬────────┘                           │
│                        │                                    │
│                        ↓ PromQL Queries                     │
│               ┌─────────────────┐                           │
│               │    Grafana      │                           │
│               │     :3000       │                           │
│               └─────────────────┘                           │
│                                                              │
│               ┌─────────────────┐                           │
│               │ Alert Manager   │                           │
│               │     :9093       │                           │
│               └────────┬────────┘                           │
│                        │                                    │
│                        ↓ Notifications                      │
│               [Email, Slack, PagerDuty]                     │
└──────────────────────────────────────────────────────────────┘
```

**Firewall Rules** (Quy tắc tường lửa):
```bash
# Allow Prometheus scraping from monitoring server
iptables -A INPUT -p tcp --dport 9100 -s 10.0.1.10 -j ACCEPT

# Allow Grafana access (authenticated users only)
iptables -A INPUT -p tcp --dport 3000 -s 10.0.0.0/24 -j ACCEPT

# Deny all other inbound to monitoring ports
iptables -A INPUT -p tcp --dport 9090:9100 -j DROP
```

---

## 7. Implementation Roadmap

### 7.1 Wave 3: Benchmark Implementation (Week 13-14)

**Objective** (Mục tiêu): Implement Criterion.rs benchmarks và Custom GPU Harness

```yaml
wave_3_tasks:
  - task: "Setup Criterion.rs infrastructure"
    duration: 2 days
    files:
      - "crates/mining-core/benches/stratum_latency.rs"
      - "crates/mining-core/benches/coordination_overhead.rs"
    deliverables:
      - Criterion benchmark harness configured
      - CI integration for benchmark regression detection

  - task: "Implement GPU benchmark harness"
    duration: 3 days
    files:
      - "crates/mining-core/benches/gpu_benchmarks.rs"
      - "crates/mining-core/src/benchmarks/mod.rs"
    deliverables:
      - Ethash kernel execution benchmark
      - KawPow kernel execution benchmark
      - Memory bandwidth measurement

  - task: "Establish performance baselines"
    duration: 2 days
    process:
      - Run 100 iterations of each benchmark
      - Statistical analysis (mean, stddev, percentiles)
      - Store baselines in JSON format
    deliverables:
      - "baselines/rtx3090-ethash.json"
      - "baselines/rtx3090-kawpow.json"
      - "baselines/stratum-latency.json"

  - task: "Integrate benchmark into CI/CD"
    duration: 1 day
    actions:
      - Add GitHub Actions workflow for benchmark runs
      - Automatic regression detection (±5% threshold)
      - Generate HTML benchmark reports
    deliverables:
      - ".github/workflows/benchmarks.yml"
```

---

### 7.2 Wave 4: Monitoring Stack Deployment (Week 15-16)

**Objective** (Mục tiêu): Deploy Prometheus + Grafana monitoring infrastructure

```yaml
wave_4_tasks:
  - task: "Implement Prometheus exporter"
    duration: 3 days
    files:
      - "crates/coordination/src/monitoring/prometheus_exporter.rs"
      - "crates/coordination/src/monitoring/nvml_collector.rs"
    deliverables:
      - HTTP /metrics endpoint on port 9100
      - All 25 core metrics exposed
      - NVML integration for GPU metrics

  - task: "Deploy Prometheus server"
    duration: 1 day
    actions:
      - Configure prometheus.yml with scrape targets
      - Setup alert rules
      - Configure 30-day retention policy
    deliverables:
      - "config/prometheus.yml"
      - "config/alert-rules.yml"
      - Running Prometheus instance on :9090

  - task: "Create Grafana dashboards"
    duration: 2 days
    dashboards:
      - "GPU Mining Performance Overview"
      - "Share Statistics & Pool Health"
      - "GPU Health Monitoring"
      - "System Resources & Alerts"
    deliverables:
      - "config/grafana/dashboards/mining-overview.json"
      - Provisioned datasources
      - Authenticated Grafana on :3000

  - task: "Configure Alert Manager"
    duration: 1 day
    actions:
      - Setup notification channels (Slack, Email)
      - Configure alert routing rules
      - Test critical alert scenarios
    deliverables:
      - "config/alertmanager.yml"
      - Verified end-to-end alerting flow

  - task: "Docker Compose integration"
    duration: 1 day
    actions:
      - Create docker-compose.yml for full stack
      - Configure persistent volumes
      - Document deployment procedure
    deliverables:
      - "docker-compose.monitoring.yml"
      - "docs/MONITORING-DEPLOYMENT.md"
```

---

### 7.3 Success Criteria

**Wave 3 Complete**:
- ✅ All benchmarks runnable via `cargo bench`
- ✅ Baseline metrics established with ±5% variance
- ✅ CI/CD benchmark regression detection working
- ✅ HTML benchmark reports generated

**Wave 4 Complete**:
- ✅ Prometheus collecting metrics from all mining nodes
- ✅ Grafana dashboards visualizing real-time performance
- ✅ Alert Manager sending notifications on critical conditions
- ✅ Full stack deployable via `docker-compose up`

---

## 8. Appendix

### 8.1 Useful Commands

```bash
# Run Criterion benchmarks
cargo bench --bench stratum_latency

# Run GPU benchmarks (requires CUDA GPU)
cargo bench --bench gpu_benchmarks --features cuda

# Generate benchmark report
cargo bench -- --save-baseline main

# Compare against baseline
cargo bench -- --baseline main

# Start monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d

# View Prometheus metrics
curl http://localhost:9100/metrics

# Query Prometheus API
curl 'http://localhost:9090/api/v1/query?query=mining_hashrate_mhs'

# Backup Prometheus data
docker exec prometheus tar czf /prometheus-backup.tar.gz /prometheus

# Check Grafana health
curl http://localhost:3000/api/health
```

---

### 8.2 References

**Tools & Libraries**:
- [Criterion.rs](https://github.com/bheisler/criterion.rs) - Statistical benchmarking for Rust
- [Prometheus](https://prometheus.io/docs/) - Time-series database
- [Grafana](https://grafana.com/docs/) - Visualization platform
- [NVML](https://developer.nvidia.com/nvidia-management-library-nvml) - NVIDIA Management Library
- [prometheus-client](https://docs.rs/prometheus-client/) - Rust Prometheus client library

**Mining Protocols**:
- [Stratum Protocol Specification](https://braiins.com/stratum-v1/docs)
- [Ethash Algorithm](https://eth.wiki/en/concepts/ethash/ethash)
- [KawPow Algorithm](https://github.com/RavenCommunity/kawpow)

---

**Document Status**: ✅ **READY FOR IMPLEMENTATION**
**Next Steps**: Begin Wave 3 benchmark implementation (Week 13-14)
**Review Date**: After Wave 3 completion for monitoring stack refinement

---

**End of Document**
