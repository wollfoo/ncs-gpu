//! **Basic Monitoring Example** (Ví dụ giám sát cơ bản)
//!
//! Demonstrates basic usage of the OPUS-GPU monitoring system.

use opus_gpu_monitor::{
    service::MonitorService,
    MonitorConfig, AlertConfig, AlertThresholds, PrometheusConfig, OpenTelemetryConfig,
    DashboardConfig, RecoveryConfig, GpuMonitoringConfig, SystemMonitoringConfig,
};
use std::time::Duration;
use tokio::time;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt::init();

    println!("🚀 OPUS-GPU Monitoring Example");

    // Create monitoring configuration
    let config = MonitorConfig {
        collection_interval: Duration::from_secs(5),
        health_check_interval: Duration::from_secs(10),
        alerts: AlertConfig {
            enabled: true,
            channels: vec![opus_gpu_monitor::AlertChannel::Log],
            thresholds: AlertThresholds::default(),
            cooldown: Duration::from_secs(60),
        },
        prometheus: PrometheusConfig {
            enabled: true,
            bind_address: "127.0.0.1".to_string(),
            port: 9090,
            metrics_path: "/metrics".to_string(),
            scrape_interval: Duration::from_secs(15),
        },
        opentelemetry: OpenTelemetryConfig {
            enabled: false, // Disable for example
            endpoint: None,
            service_name: "opus-gpu-example".to_string(),
            service_version: "1.0.0".to_string(),
            environment: "development".to_string(),
        },
        dashboard: DashboardConfig::default(),
        recovery: RecoveryConfig {
            enabled: true,
            max_recovery_attempts: 3,
            recovery_cooldown: Duration::from_secs(60),
            actions: vec![
                opus_gpu_monitor::RecoveryAction::RestartMining,
                opus_gpu_monitor::RecoveryAction::NotifyAdmin,
            ],
        },
        gpu_monitoring: GpuMonitoringConfig {
            enabled: true,
            nvidia_ml_enabled: true,
            collect_detailed_metrics: true,
            gpu_discovery_interval: Duration::from_secs(30),
        },
        system_monitoring: SystemMonitoringConfig {
            enabled: true,
            collect_process_metrics: true,
            collect_network_metrics: true,
            collect_disk_metrics: true,
        },
    };

    // Create monitoring service
    let monitor_service = MonitorService::new(config)?;

    println!("📊 Starting monitoring service...");

    // Start the monitoring service
    monitor_service.start().await?;

    println!("✅ Monitoring service started successfully!");
    println!("📈 Prometheus metrics available at: http://127.0.0.1:9090/metrics");
    println!("🔍 Monitor logs for health checks and alerts");

    // Let it run for a while to collect metrics
    println!("⏳ Collecting metrics for 30 seconds...");
    time::sleep(Duration::from_secs(30)).await;

    // Get status
    let status = monitor_service.status().await;
    println!("📋 Monitor Status:");
    println!("   - Running: {}", status.running);
    println!("   - Health: {}", status.health_status);
    println!("   - Active Alerts: {}", status.active_alerts);
    println!("   - Collectors: {}", status.collectors_count);
    println!("   - Exporters: {}", status.exporters_active);

    println!("🛑 Stopping monitoring service...");
    monitor_service.stop().await?;

    println!("✅ Example completed successfully!");

    Ok(())
}