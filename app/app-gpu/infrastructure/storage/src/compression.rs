use anyhow::Result;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CompressionType {
    None,
    Zstd,
    Gzip,
    Lz4,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompressionConfig {
    pub algorithm: CompressionType,
    pub level: i32,
    pub min_size: usize,
}

pub struct CompressionEngine {
    config: CompressionConfig,
}

impl CompressionEngine {
    pub fn new(config: CompressionConfig) -> Self {
        Self { config }
    }

    pub fn compress(&self, data: &[u8]) -> Result<Vec<u8>> {
        match self.config.algorithm {
            CompressionType::Zstd => {
                zstd::encode_all(data, self.config.level)
                    .map_err(|e| anyhow::anyhow!("Zstd compression failed: {}", e))
            }
            CompressionType::None => Ok(data.to_vec()),
            _ => Ok(data.to_vec()), // TODO: Implement other algorithms
        }
    }

    pub fn decompress(&self, data: &[u8]) -> Result<Vec<u8>> {
        match self.config.algorithm {
            CompressionType::Zstd => {
                zstd::decode_all(data)
                    .map_err(|e| anyhow::anyhow!("Zstd decompression failed: {}", e))
            }
            CompressionType::None => Ok(data.to_vec()),
            _ => Ok(data.to_vec()), // TODO: Implement other algorithms
        }
    }
}

impl Default for CompressionConfig {
    fn default() -> Self {
        Self {
            algorithm: CompressionType::Zstd,
            level: 3,
            min_size: 1024,
        }
    }
}