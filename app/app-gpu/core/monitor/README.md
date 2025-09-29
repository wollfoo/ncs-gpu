# OPUS-GPU Monitor Module

**Comprehensive monitoring and observability system** cho OPUS-GPU mining platform.

## Features (Tính năng)

### 🔍 **Performance Monitoring** (Giám sát hiệu suất)
- **GPU Metrics**: Temperature, utilization, power, hash rates
- **System Metrics**: CPU, memory, disk, network usage
- **Pool Statistics**: Connection status, latency, share rates
- **Mining Performance**: Hash rates, efficiency, profitability

### 🏥 **Health Monitoring** (Giám sát sức khỏe)
- **Component Health Checks**: GPU, system, pool, network
- **Automated Health Assessment**: Status evaluation with thresholds
- **Health History Tracking**: Monitor component health over time
- **Predictive Health Analysis**: Identify potential issues early

### 🚨 **Alert System** (Hệ thống cảnh báo)
- **Multi-Channel Alerts**: Log, Slack, Discord, webhooks, email
- **Configurable Thresholds**: Temperature, utilization, errors
- **Alert Cooldown Management**: Prevent alert spam
- **Alert Acknowledgment**: Track alert resolution

### 🔧 **Auto-Recovery** (Phục hồi tự động)
- **Progressive Recovery**: Escalating recovery actions
- **Recovery Rules Engine**: Configurable recovery strategies
- **Recovery History**: Track recovery attempts and success rates
- **Manual Override**: Admin intervention when needed

### 📊 **Observability** (Khả năng quan sát)
- **Prometheus Metrics**: Industry-standard metrics export
- **OpenTelemetry Tracing**: Distributed tracing support
- **Structured Logging**: JSON-formatted logs with context
- **Dashboard Integration**: Pre-built Grafana dashboards

## Architecture (Kiến trúc)

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Collectors    │    │   Health Checks │    │   Alert Manager │
│                 │    │                 │    │                 │
│ • GPU Collector │───▶│ • GPU Health    │───▶│ • Alert Rules   │
│ • Sys Collector │    │ • Pool Health   │    │ • Channels      │
│ • Pool Collector│    │ • Sys Health    │    │ • Cooldowns     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Exporters     │    │   Recovery Mgr  │    │   Dashboards    │
│                 │    │                 │    │                 │
│ • Prometheus    │    │ • Recovery Rules│    │ • GPU Overview  │
│ • OpenTelemetry │    │ • Action Exec   │    │ • System Stats  │
│ • Multi Export  │    │ • Attempt Track │    │ • Pool Stats    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Quick Start

### Basic Usage

```rust
use opus_gpu_monitor::{service::MonitorService, MonitorConfig};

#[tokio::main]
async fn main() -> Result<()> {
    // Create monitoring service with default config
    let monitor = MonitorService::new(MonitorConfig::default())?;

    // Start monitoring
    monitor.start().await?;

    // Monitor will now collect metrics, perform health checks,
    // send alerts, and export to Prometheus

    // Get status
    let status = monitor.status().await;
    println!("Health: {}, Alerts: {}", status.health_status, status.active_alerts);

    // Stop monitoring
    monitor.stop().await?;
    Ok(())
}
```

### Configuration Example

```rust
use opus_gpu_monitor::*;
use std::time::Duration;

let config = MonitorConfig {
    collection_interval: Duration::from_secs(5),
    health_check_interval: Duration::from_secs(10),

    alerts: AlertConfig {
        enabled: true,
        channels: vec![
            AlertChannel::Slack {
                webhook_url: "https://hooks.slack.com/...".to_string()
            },
            AlertChannel::Log,
        ],
        thresholds: AlertThresholds {
            gpu_temperature_critical: 85.0,
            gpu_utilization_low: 70.0,
            hashrate_drop_critical: 20.0,
            ..Default::default()
        },
        cooldown: Duration::from_secs(300),
    },

    prometheus: PrometheusConfig {
        enabled: true,
        bind_address: "0.0.0.0".to_string(),
        port: 9090,
        ..Default::default()
    },

    recovery: RecoveryConfig {
        enabled: true,
        max_recovery_attempts: 3,
        actions: vec![
            RecoveryAction::ReducePowerLimit,
            RecoveryAction::RestartMining,
            RecoveryAction::SwitchPool,
        ],
        ..Default::default()
    },

    ..Default::default()
};
```

## Metrics (Đo lường)

### GPU Metrics
- `opus_gpu_temperature_celsius` - GPU temperature
- `opus_gpu_utilization_percent` - GPU utilization
- `opus_gpu_power_draw_watts` - Power consumption
- `opus_gpu_hashrate_mhs` - Current hash rate
- `opus_gpu_shares_accepted_total` - Accepted shares
- `opus_gpu_memory_used_bytes` - GPU memory usage

### System Metrics
- `opus_system_cpu_usage_percent` - CPU utilization
- `opus_system_memory_used_bytes` - Memory usage
- `opus_system_load_average_1m` - Load average
- `opus_system_disk_usage_percent` - Disk usage
- `opus_system_uptime_seconds` - System uptime

### Pool Metrics
- `opus_pool_connected` - Pool connection status
- `opus_pool_latency_ms` - Pool latency
- `opus_pool_hashrate_reported_mhs` - Pool-reported hash rate
- `opus_pool_shares_accepted_total` - Pool accepted shares

## Health Checks (Kiểm tra sức khỏe)

### Health Status Levels
- **Healthy**: All systems operating normally
- **Warning**: Minor issues detected, system still operational
- **Critical**: Critical issues detected, system may be degraded
- **Down**: System is down or unresponsive
- **Unknown**: Health status not yet determined

### Component Health Checks
- **GPU Health**: Temperature, utilization, errors
- **Pool Health**: Connection, latency, rejection rate
- **System Health**: CPU, memory, disk usage

## Alerts (Cảnh báo)

### Alert Levels
- **Info**: Informational messages
- **Warning**: Warning conditions
- **Critical**: Critical issues requiring attention
- **Emergency**: Emergency conditions requiring immediate action

### Alert Channels
- **Log**: Write to application logs
- **Slack**: Send to Slack webhook
- **Discord**: Send to Discord webhook
- **Webhook**: Send to custom webhook
- **Email**: Send email notifications (planned)

## Recovery Actions (Hành động phục hồi)

### Available Actions
- `RestartMining` - Restart mining process
- `SwitchPool` - Switch to backup mining pool
- `ReducePowerLimit` - Reduce GPU power limit
- `RestartGpu` - Restart specific GPU
- `RestartSystem` - Restart entire system (careful!)
- `NotifyAdmin` - Send admin notification
- `Custom` - Execute custom command

### Recovery Strategies
- **Immediate**: Execute recovery action immediately
- **Progressive**: Try actions in sequence until one succeeds
- **DelayedRetry**: Wait and retry with delay
- **Manual**: Require manual intervention

## Dashboards (Dashboard)

### Pre-built Dashboards
1. **GPU Overview** - GPU performance and health
2. **System Overview** - System resource monitoring
3. **Mining Performance** - Hash rates and efficiency
4. **Pool Statistics** - Pool connection and performance
5. **Alerts & Health** - Alert and health status overview

### Dashboard Export
```rust
use opus_gpu_monitor::dashboards::{DashboardManager, DashboardDeployment};

let manager = DashboardManager::new(config);
let deployment = DashboardDeployment::new(manager);

// Export all dashboards to directory
let files = deployment.export_all_to_directory("./dashboards").await?;

// Deploy to Grafana
deployment.deploy_to_grafana("http://localhost:3000", "api_key", "opus_gpu_overview").await?;
```

## Examples (Ví dụ)

Run examples to see the monitoring system in action:

```bash
# Basic monitoring example
cargo run --example basic_monitoring

# Dashboard export example
cargo run --example dashboard_export
```

## Integration (Tích hợp)

### With Mining Engine
```rust
// Update GPU mining statistics
gpu_collector.update_mining_stats(
    gpu_id,
    hashrate,
    shares_accepted,
    shares_rejected,
    shares_stale,
).await?;
```

### With Pool Manager
```rust
// Update pool metrics
pool_collector.update_pool_metrics(pool_name, pool_metrics).await;
```

### With Health System
```rust
// Trigger recovery for unhealthy component
recovery_manager.attempt_recovery(&component_health).await?;
```

## Configuration (Cấu hình)

### Environment Variables
- `OPUS_PROMETHEUS_PORT` - Prometheus metrics port
- `OPUS_ALERT_SLACK_WEBHOOK` - Slack webhook URL
- `OPUS_RECOVERY_ENABLED` - Enable auto-recovery
- `OPUS_GPU_MONITORING_ENABLED` - Enable GPU monitoring

### Config File (config.yaml)
```yaml
monitor:
  collection_interval: "5s"
  health_check_interval: "10s"

  alerts:
    enabled: true
    channels:
      - type: "slack"
        webhook_url: "https://hooks.slack.com/..."
    thresholds:
      gpu_temperature_critical: 85.0
      hashrate_drop_critical: 20.0

  prometheus:
    enabled: true
    port: 9090

  recovery:
    enabled: true
    max_attempts: 3
```

## Dependencies (Phụ thuộc)

- **tokio** - Async runtime
- **prometheus** - Metrics export
- **sysinfo** - System information
- **nvml-wrapper** - NVIDIA GPU metrics (optional)
- **reqwest** - HTTP client for webhooks
- **serde** - Serialization

## Features Flags

- `nvidia` - Enable NVIDIA GPU monitoring via NVML
- `prometheus` - Enable Prometheus metrics export
- `opentelemetry` - Enable OpenTelemetry tracing

## License

MIT License - See LICENSE file for details.

---

**OPUS-GPU Monitor** - Comprehensive monitoring cho high-performance GPU mining platform 🚀