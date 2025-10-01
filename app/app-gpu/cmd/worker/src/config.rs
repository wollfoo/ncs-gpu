use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::fs;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    pub worker: WorkerConfig,
    pub pool: PoolConfig,
    pub gpu: GpuConfig,
    pub mining: MiningConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerConfig {
    pub name: String,
    pub threads_per_gpu: usize,
    pub restart_on_failure: bool,
    pub restart_delay_secs: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoolConfig {
    pub url: String,
    pub wallet: String,
    pub password: String,
    pub worker_name: String,
    pub retry_count: usize,
    pub timeout_secs: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuConfig {
    pub power_limit_watts: Option<u32>,
    pub target_temperature: u32,
    pub memory_clock_offset: Option<i32>,
    pub core_clock_offset: Option<i32>,
    pub fan_speed_percent: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningConfig {
    pub algorithm: String, // "kawpow" for RVN
    pub intensity: u32,
    pub worksize: usize,
    pub dag_build_mode: String, // "parallel" or "sequential"
}

impl Default for Config {
    fn default() -> Self {
        Self {
            worker: WorkerConfig {
                name: "gpu-worker".to_string(),
                threads_per_gpu: 1,
                restart_on_failure: true,
                restart_delay_secs: 10,
            },
            pool: PoolConfig {
                url: "stratum+tcp://pool.woolypooly.com:55555".to_string(),
                wallet: "".to_string(),
                password: "x".to_string(),
                worker_name: "worker01".to_string(),
                retry_count: 5,
                timeout_secs: 30,
            },
            gpu: GpuConfig {
                power_limit_watts: Some(200),
                target_temperature: 70,
                memory_clock_offset: None,
                core_clock_offset: None,
                fan_speed_percent: None,
            },
            mining: MiningConfig {
                algorithm: "kawpow".to_string(),
                intensity: 20,
                worksize: 256,
                dag_build_mode: "parallel".to_string(),
            },
        }
    }
}

impl Config {
    pub fn load(path: &str) -> Result<Self> {
        let contents = fs::read_to_string(path)?;
        let config: Config = toml::from_str(&contents)?;
        Ok(config)
    }
    
    pub fn save(&self, path: &str) -> Result<()> {
        let contents = toml::to_string_pretty(self)?;
        fs::write(path, contents)?;
        Ok(())
    }
}
