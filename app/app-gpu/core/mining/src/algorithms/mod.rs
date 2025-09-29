//! Mining Algorithm Implementations
//!
//! This module contains implementations of various cryptocurrency mining algorithms
//! optimized for GPU mining with the OPUS-GPU framework.

/// KawPow algorithm implementation for Ravencoin mining
pub mod kawpow;

// Re-export algorithm implementations
pub use kawpow::{KawPowAlgorithm, KawPowConfig};