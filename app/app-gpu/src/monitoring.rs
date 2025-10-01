// Monitoring Module - Giám sát và telemetry
// Monitoring Module - Monitoring and telemetry

use anyhow::{Result, Context};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{info, debug, warn, error};
use prometheus::{Encoder, TextEncoder, Counter, Gauge, Histogram, HistogramOpts};
use std::collections::HashMap;
use sysinfo::{System, SystemExt, ProcessExt, CpuExt, NetworkExt};

use crate::config::Config;

/// Telemetry System - Hệ thống đo lường và giám sát
/// Telemetry System - Measurement and monitoring system
pub struct TelemetrySystem {
    /// Configuration
    config: Arc<Config>,
    
    /// System info collector
    system: Arc<RwLock<System>>,
    
    /// Prometheus metrics
    metrics: MetricsCollector,
    
    /// Performance history
    perf_history: Arc<RwLock<PerformanceHistory>>,
    
    /// Alert manager
    alerts: Arc<RwLock<AlertManager>>,
    
    /// Is running?
    running: Arc<RwLock<bool>>,
}

/// Prometheus metrics collector
struct MetricsCollector {
    /// Hash rate gauge (MH/s)
    hashrate: Gauge,
    
    /// GPU temperature gauge (Celsius)
    gpu_temp: Gauge,
    
    /// GPU power usage (Watts)
    gpu_power: Gauge,
    
    /// GPU utilization percentage
    gpu_util: Gauge,
    
    /// Shares accepted counter
    shares_accepted: Counter,
    
    /// Shares rejected counter
    shares_rejected: Counter,
    
    /// Mining uptime seconds
    uptime: Counter,
    
    /// Network latency histogram (ms)
    pool_latency: Histogram,
    
    /// Memory usage gauge (MB)
    memory_usage: Gauge,
    
    /// CPU usage gauge (%)
    cpu_usage: Gauge,
}

/// Performance history tracking
#[derive(Debug, Clone)]
struct PerformanceHistory {
    /// Hash rate history (MH/s)
    hashrate_history: Vec<(std::time::SystemTime, f64)>,
    
    /// Temperature history (Celsius)
    temp_history: Vec<(std::time::SystemTime, f32)>,
    
    /// Power usage history (Watts)
    power_history: Vec<(std::time::SystemTime, f32)>,
    
    /// Network latency history (ms)
    latency_history: Vec<(std::time::SystemTime, u32)>,
    
    /// Max history size
    max_history: usize,
}

/// Alert types
#[derive(Debug, Clone)]
enum AlertType {
    /// High temperature warning
    HighTemperature(f32),
    /// Low hashrate warning
    LowHashrate(f64),
    /// High rejection rate
    HighRejectionRate(f64),
    /// Connection lost
    ConnectionLost,
    /// GPU error
    GpuError(String),
    /// Memory pressure
    MemoryPressure(f64),
}

/// Alert manager
struct AlertManager {
    /// Active alerts
    active_alerts: HashMap<String, AlertType>,
    
    /// Alert thresholds
    thresholds: AlertThresholds,
    
    /// Alert cooldown (prevent spam)
    cooldown: HashMap<String, std::time::Instant>,
}

/// Alert thresholds configuration
struct AlertThresholds {
    /// Max GPU temperature (Celsius)
    max_temp: f32,
    
    /// Min hashrate (MH/s)
    min_hashrate: f64,
    
    /// Max rejection rate (%)
    max_rejection_rate: f64,
    
    /// Max memory usage (%)
    max_memory: f64,
    
    /// Alert cooldown period (seconds)
    cooldown_seconds: u64,
}

impl MetricsCollector {
    fn new() -> Result<Self> {
        Ok(Self {
            hashrate: Gauge::new("gpu_hashrate_mhs", "Current hashrate in MH/s")?,
            gpu_temp: Gauge::new("gpu_temperature_celsius", "GPU temperature in Celsius")?,
            gpu_power: Gauge::new("gpu_power_watts", "GPU power usage in Watts")?,
            gpu_util: Gauge::new("gpu_utilization_percent", "GPU utilization percentage")?,
            shares_accepted: Counter::new("shares_accepted_total", "Total accepted shares")?,
            shares_rejected: Counter::new("shares_rejected_total", "Total rejected shares")?,
            uptime: Counter::new("mining_uptime_seconds", "Mining uptime in seconds")?,
            pool_latency: Histogram::with_opts(
                HistogramOpts::new("pool_latency_ms", "Pool latency in milliseconds")
            )?,
            memory_usage: Gauge::new("memory_usage_mb", "Memory usage in MB")?,
            cpu_usage: Gauge::new("cpu_usage_percent", "CPU usage percentage")?,
        })
    }
    
    /// Export metrics as Prometheus format
    fn export(&self) -> Result<String> {
        let encoder = TextEncoder::new();
        let metric_families = prometheus::gather();
        let mut buffer = Vec::new();
        encoder.encode(&metric_families, &mut buffer)?;
        Ok(String::from_utf8(buffer)?)
    }
}

impl PerformanceHistory {
    fn new() -> Self {
        Self {
            hashrate_history: Vec::new(),
            temp_history: Vec::new(),
            power_history: Vec::new(),
            latency_history: Vec::new(),
            max_history: 1000, // Keep last 1000 data points
        }
    }
    
    /// Add hashrate data point
    fn add_hashrate(&mut self, rate: f64) {
        self.hashrate_history.push((std::time::SystemTime::now(), rate));
        if self.hashrate_history.len() > self.max_history {
            self.hashrate_history.remove(0);
        }
    }
    
    /// Add temperature data point
    fn add_temperature(&mut self, temp: f32) {
        self.temp_history.push((std::time::SystemTime::now(), temp));
        if self.temp_history.len() > self.max_history {
            self.temp_history.remove(0);
        }
    }
    
    /// Get average hashrate over last N minutes
    fn get_avg_hashrate(&self, minutes: u64) -> f64 {
        let cutoff = std::time::SystemTime::now()
            - std::time::Duration::from_secs(minutes * 60);
        
        let recent: Vec<f64> = self.hashrate_history.iter()
            .filter(|(t, _)| *t > cutoff)
            .map(|(_, r)| *r)
            .collect();
        
        if recent.is_empty() {
            0.0
        } else {
            recent.iter().sum::<f64>() / recent.len() as f64
        }
    }
    
    /// Get max temperature over last N minutes
    fn get_max_temp(&self, minutes: u64) -> f32 {
        let cutoff = std::time::SystemTime::now()
            - std::time::Duration::from_secs(minutes * 60);
        
        self.temp_history.iter()
            .filter(|(t, _)| *t > cutoff)
            .map(|(_, temp)| *temp)
            .fold(0.0f32, f32::max)
    }
}

impl AlertManager {
    fn new() -> Self {
        Self {
            active_alerts: HashMap::new(),
            thresholds: AlertThresholds {
                max_temp: 85.0,
                min_hashrate: 10.0,
                max_rejection_rate: 5.0,
                max_memory: 90.0,
                cooldown_seconds: 300, // 5 minutes
            },
            cooldown: HashMap::new(),
        }
    }
    
    /// Check if alert should be triggered
    fn should_alert(&mut self, key: &str) -> bool {
        if let Some(last_alert) = self.cooldown.get(key) {
            if last_alert.elapsed().as_secs() < self.thresholds.cooldown_seconds {
                return false;
            }
        }
        true
    }
    
    /// Trigger alert
    fn trigger_alert(&mut self, key: String, alert_type: AlertType) {
        if !self.should_alert(&key) {
            return;
        }
        
        match &alert_type {
            AlertType::HighTemperature(temp) => {
                error!("🔥 ALERT: GPU temperature too high: {}°C", temp);
            }
            AlertType::LowHashrate(rate) => {
                warn!("⚠️ ALERT: Low hashrate detected: {} MH/s", rate);
            }
            AlertType::HighRejectionRate(rate) => {
                warn!("⚠️ ALERT: High share rejection rate: {:.1}%", rate);
            }
            AlertType::ConnectionLost => {
                error!("🔌 ALERT: Pool connection lost!");
            }
            AlertType::GpuError(msg) => {
                error!("🎮 ALERT: GPU error: {}", msg);
            }
            AlertType::MemoryPressure(usage) => {
                warn!("💾 ALERT: High memory usage: {:.1}%", usage);
            }
        }
        
        self.active_alerts.insert(key.clone(), alert_type);
        self.cooldown.insert(key, std::time::Instant::now());
    }
    
    /// Clear alert
    fn clear_alert(&mut self, key: &str) {
        if self.active_alerts.remove(key).is_some() {
            info!("✅ Alert cleared: {}", key);
        }
    }
}

impl TelemetrySystem {
    /// Create new telemetry system
    pub fn new(config: Arc<Config>) -> Result<Self> {
        debug!("Initializing Telemetry System");
        
        let mut system = System::new_all();
        system.refresh_all();
        
        Ok(Self {
            config,
            system: Arc::new(RwLock::new(system)),
            metrics: MetricsCollector::new()?,
            perf_history: Arc::new(RwLock::new(PerformanceHistory::new())),
            alerts: Arc::new(RwLock::new(AlertManager::new())),
            running: Arc::new(RwLock::new(false)),
        })
    }
    
    /// Start telemetry collection
    pub async fn start(&mut self) -> Result<()> {
        info!("📊 Starting telemetry system");
        
        *self.running.write().await = true;
        
        // Start collection threads
        self.start_system_monitor().await;
        self.start_gpu_monitor().await;
        self.start_alert_monitor().await;
        
        // Start metrics HTTP server if configured
        if let Some(endpoint) = &self.config.logging.remote_endpoint {
            self.start_metrics_server(endpoint.clone()).await?;
        }
        
        Ok(())
    }
    
    /// Start system monitoring thread
    async fn start_system_monitor(&self) {
        let system = self.system.clone();
        let metrics = Arc::new(self.metrics.memory_usage.clone());
        let cpu_gauge = Arc::new(self.metrics.cpu_usage.clone());
        let running = self.running.clone();
        
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(tokio::time::Duration::from_secs(5));
            
            loop {
                interval.tick().await;
                
                if !*running.read().await {
                    break;
                }
                
                // Update system info
                let mut sys = system.write().await;
                sys.refresh_cpu();
                sys.refresh_memory();
                sys.refresh_processes();
                
                // Update metrics
                let mem_used_mb = (sys.used_memory() / 1024) as f64;
                metrics.set(mem_used_mb);
                
                let cpu_usage = sys.global_cpu_info().cpu_usage();
                cpu_gauge.set(cpu_usage as f64);
                
                debug!("System: Memory {} MB, CPU {:.1}%", mem_used_mb, cpu_usage);
            }
        });
    }
    
    /// Start GPU monitoring thread
    async fn start_gpu_monitor(&self) {
        let history = self.perf_history.clone();
        let hashrate_gauge = Arc::new(self.metrics.hashrate.clone());
        let temp_gauge = Arc::new(self.metrics.gpu_temp.clone());
        let power_gauge = Arc::new(self.metrics.gpu_power.clone());
        let running = self.running.clone();
        
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(tokio::time::Duration::from_secs(10));
            
            loop {
                interval.tick().await;
                
                if !*running.read().await {
                    break;
                }
                
                // Simulate GPU metrics (would be real NVML/ROCm calls)
                let hashrate = 75.0 + (rand::random::<f64>() * 10.0);
                let temp = 70.0 + (rand::random::<f32>() * 5.0);
                let power = 150.0 + (rand::random::<f32>() * 20.0);
                
                // Update metrics
                hashrate_gauge.set(hashrate);
                temp_gauge.set(temp as f64);
                power_gauge.set(power as f64);
                
                // Update history
                let mut hist = history.write().await;
                hist.add_hashrate(hashrate);
                hist.add_temperature(temp);
                
                debug!("GPU: {:.2} MH/s, {}°C, {} W", hashrate, temp, power);
            }
        });
    }
    
    /// Start alert monitoring
    async fn start_alert_monitor(&self) {
        let alerts = self.alerts.clone();
        let history = self.perf_history.clone();
        let running = self.running.clone();
        
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(tokio::time::Duration::from_secs(30));
            
            loop {
                interval.tick().await;
                
                if !*running.read().await {
                    break;
                }
                
                let mut alert_mgr = alerts.write().await;
                let hist = history.read().await;
                
                // Check temperature
                let max_temp = hist.get_max_temp(5);
                if max_temp > alert_mgr.thresholds.max_temp {
                    alert_mgr.trigger_alert(
                        "high_temp".to_string(),
                        AlertType::HighTemperature(max_temp)
                    );
                } else {
                    alert_mgr.clear_alert("high_temp");
                }
                
                // Check hashrate
                let avg_hashrate = hist.get_avg_hashrate(5);
                if avg_hashrate < alert_mgr.thresholds.min_hashrate && avg_hashrate > 0.0 {
                    alert_mgr.trigger_alert(
                        "low_hashrate".to_string(),
                        AlertType::LowHashrate(avg_hashrate)
                    );
                } else {
                    alert_mgr.clear_alert("low_hashrate");
                }
            }
        });
    }
    
    /// Start metrics HTTP server
    async fn start_metrics_server(&self, endpoint: String) -> Result<()> {
        info!("📡 Starting metrics server on {}", endpoint);
        
        // Simplified metrics endpoint
        // Real implementation would use warp or axum
        
        Ok(())
    }
    
    /// Stop telemetry system
    pub async fn stop(&mut self) -> Result<()> {
        info!("📊 Stopping telemetry system");
        
        *self.running.write().await = false;
        
        // Export final metrics
        if let Ok(metrics) = self.metrics.export() {
            debug!("Final metrics:\n{}", metrics);
        }
        
        Ok(())
    }
    
    /// Get current metrics snapshot
    pub async fn get_metrics(&self) -> Result<String> {
        self.metrics.export()
    }
    
    /// Get performance summary
    pub async fn get_summary(&self) -> Result<String> {
        let history = self.perf_history.read().await;
        let alerts = self.alerts.read().await;
        
        let avg_1m = history.get_avg_hashrate(1);
        let avg_5m = history.get_avg_hashrate(5);
        let max_temp = history.get_max_temp(5);
        let active_alerts = alerts.active_alerts.len();
        
        Ok(format!(
            "📊 Performance Summary:\n\
             Hashrate: {:.2} MH/s (1m), {:.2} MH/s (5m)\n\
             Max Temperature: {:.1}°C\n\
             Active Alerts: {}",
            avg_1m, avg_5m, max_temp, active_alerts
        ))
    }
}
