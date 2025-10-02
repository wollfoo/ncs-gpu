//! # Stratum Mining Protocol Client (Khách hàng giao thức khai thác Stratum)
//!
//! Robust implementation của Stratum protocol client sử dụng actor pattern
//! với message passing cho reliable và high-performance mining pool communications.
//!
//! ## Features (Tính năng)
//! - **Actor-based architecture** (Kiến trúc dựa trên actor) – message passing giữa components
//! - **Multi-pool failover** (Failover đa pool) – tự động chuyển tiếp khi pool fail
//! - **Exponential backoff reconnection** (Tái kết nối với backoff mũ) – smart connection handling
//! - **Job queue management** (Quản lý hàng đợi job) – efficient work distribution
//! - **Share batching** (Gom nhóm share) – optimized submission rates
//! - **SSL/TLS support** (Hỗ trợ SSL/TLS) – secure connections
//! - **Connection health monitoring** (Giám sát sức khỏe kết nối) – automatic recovery
//! - **Difficulty management** (Quản lý độ khó) – local và network difficulty handling

pub mod client;
pub mod error;
pub mod protocol;

pub use client::{StratumClient, StratumConfig, PoolConfig};
pub use error::StratumError;
pub use protocol::{Message, Notification, Request, Response, WorkPackage, Solution};