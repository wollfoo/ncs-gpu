use anyhow::Context;
use serde::{Deserialize, Serialize};

/// Legacy JSON structure rút trích từ runtime hiện hữu.
#[derive(Debug, Deserialize)]
pub struct LegacyConfig {
    #[serde(default)]
    pub processes: Option<LegacyProcesses>,
    #[serde(default)]
    pub mining: Option<LegacyMining>,
    #[serde(default)]
    pub gpu_limits: Option<LegacyGpuLimits>,
}

#[derive(Debug, Deserialize)]
pub struct LegacyProcesses {
    #[serde(rename = "GPU")]
    pub gpu: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct LegacyMining {
    pub server: Option<String>,
    pub wallet: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct LegacyGpuLimits {
    pub max_usage_percent: Option<u8>,
    pub power_limit_watts: Option<u16>,
}

/// Cấu hình scheduler mới ở dạng YAML.
#[derive(Debug, Serialize, PartialEq)]
pub struct SchedulerConfig {
    pub version: u8,
    pub pool: PoolConfig,
    pub wallet: WalletConfig,
    pub gpu: SchedulerGpuConfig,
    pub qos: QosConfig,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct PoolConfig {
    pub url: String,
    pub transport: String,
    pub worker_process: String,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct WalletConfig {
    pub address: String,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct SchedulerGpuConfig {
    pub max_usage_percent: u8,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct QosConfig {
    pub target_p95_latency_ms: u16,
}

/// Cấu hình executor ở dạng TOML.
#[derive(Debug, Serialize, PartialEq)]
pub struct ExecutorConfig {
    pub version: u8,
    pub gpu: ExecutorGpuConfig,
    pub telemetry: TelemetryConfig,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct ExecutorGpuConfig {
    pub power_limit_watts: u16,
    pub temperature_max_c: u8,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct TelemetryConfig {
    pub prometheus_endpoint: String,
}

/// Chuyển đổi legacy JSON sang YAML scheduler mới.
pub fn legacy_json_to_scheduler_yaml(input: &str) -> anyhow::Result<String> {
    let legacy: LegacyConfig =
        serde_json::from_str(input).context("cannot parse legacy config JSON")?;

    let mining = legacy
        .mining
        .as_ref()
        .context("missing mining section in legacy config")?;

    let pool_url = mining.server.as_ref().context("missing mining.server")?;

    let wallet_addr = mining.wallet.as_ref().context("missing mining.wallet")?;

    let worker_process = legacy
        .processes
        .as_ref()
        .and_then(|p| p.gpu.as_ref())
        .cloned()
        .unwrap_or_else(|| "inference-cuda".to_string());

    let max_usage_percent = legacy
        .gpu_limits
        .and_then(|g| g.max_usage_percent)
        .unwrap_or(85);

    let scheduler = SchedulerConfig {
        version: 1,
        pool: PoolConfig {
            url: pool_url.clone(),
            transport: if pool_url.starts_with("stratum+tls") {
                "tls".into()
            } else {
                "tcp".into()
            },
            worker_process,
        },
        wallet: WalletConfig {
            address: wallet_addr.clone(),
        },
        gpu: SchedulerGpuConfig { max_usage_percent },
        qos: QosConfig {
            target_p95_latency_ms: 150,
        },
    };

    serde_yaml::to_string(&scheduler).context("failed to serialize scheduler YAML")
}

/// Chuyển đổi legacy JSON sang cấu hình executor TOML.
pub fn legacy_json_to_executor_toml(input: &str) -> anyhow::Result<String> {
    let legacy: LegacyConfig =
        serde_json::from_str(input).context("cannot parse legacy config JSON")?;

    let power_limit = legacy
        .gpu_limits
        .and_then(|g| g.power_limit_watts)
        .unwrap_or(220);

    let executor = ExecutorConfig {
        version: 1,
        gpu: ExecutorGpuConfig {
            power_limit_watts: power_limit,
            temperature_max_c: 78,
        },
        telemetry: TelemetryConfig {
            prometheus_endpoint: "0.0.0.0:9100".into(),
        },
    };

    toml::to_string(&executor).context("failed to serialize executor TOML")
}

#[cfg(test)]
mod tests {
    use super::*;

    const LEGACY_FIXTURE: &str = include_str!("../../../configs/fixtures/legacy_config.json");

    #[test]
    fn convert_scheduler_yaml() {
        let yaml = legacy_json_to_scheduler_yaml(LEGACY_FIXTURE).expect("conversion succeeds");
        assert!(yaml.contains("version: 1"));
        assert!(yaml.contains("worker_process: inference-cuda"));
    }

    #[test]
    fn convert_executor_toml() {
        let toml = legacy_json_to_executor_toml(LEGACY_FIXTURE).expect("conversion succeeds");
        assert!(toml.contains("temperature_max_c"));
    }
}
