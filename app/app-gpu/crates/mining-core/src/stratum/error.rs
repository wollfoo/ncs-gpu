//! # Stratum Error Types (Loại lỗi Stratum)
//!
//! Comprehensive error handling cho Stratum protocol operations
//! với detailed context và recovery information.

use std::fmt;
use thiserror::Error;
use tokio::time::error::Elapsed;

/// Main Stratum error types (Loại lỗi chính cho Stratum)
#[derive(Debug, Error)]
pub enum StratumError {
    /// Connection errors (Lỗi kết nối)
    #[error("Connection error: {source}")]
    Connection {
        #[from]
        source: ConnectionError,
    },

    /// Protocol errors (Lỗi giao thức)
    #[error("Protocol error: {source}")]
    Protocol {
        #[from]
        source: ProtocolError,
    },

    /// Authentication errors (Lỗi xác thực)
    #[error("Authentication failed: {source}")]
    Auth {
        #[from]
        source: AuthError,
    },

    /// Job management errors (Lỗi quản lý job)
    #[error("Job error: {source}")]
    Job {
        #[from]
        source: JobError,
    },

    /// Share submission errors (Lỗi nộp share)
    #[error("Share submission error: {source}")]
    Share {
        #[from]
        source: ShareError,
    },

    /// Pool failover errors (Lỗi chuyển tiếp pool)
    #[error("Pool failover error: {source}")]
    Failover {
        #[from]
        source: FailoverError,
    },

    /// Configuration errors (Lỗi cấu hình)
    #[error("Configuration error: {source}")]
    Config {
        #[from]
        source: ConfigError,
    },

    /// Internal errors (Lỗi nội bộ)
    #[error("Internal error: {message}")]
    Internal { message: String },
}

/// Connection-related errors (Lỗi liên quan đến kết nối)
#[derive(Debug, Error)]
pub enum ConnectionError {
    #[error("Failed to resolve hostname: {hostname}")]
    DnsResolution { hostname: String },

    #[error("Connection timeout after {timeout_secs}s")]
    Timeout { timeout_secs: u64 },

    #[error("Connection refused by {host}:{port}")]
    ConnectionRefused { host: String, port: u16 },

    #[error("SSL/TLS handshake failed: {reason}")]
    SslHandshake { reason: String },

    #[error("Network unreachable: {host}:{port}")]
    NetworkUnreachable { host: String, port: u16 },

    #[error("Connection lost after {uptime_secs}s")]
    ConnectionLost { uptime_secs: u64 },

    #[error("Unexpected disconnection")]
    UnexpectedDisconnect,

    #[error("Socket read error: {message}")]
    SocketRead { message: String },

    #[error("Socket write error: {message}")]
    SocketWrite { message: String },

    #[error("Malformed packet received")]
    MalformedPacket,
}

/// Protocol-level errors (Lỗi cấp độ giao thức)
#[derive(Debug, Error)]
pub enum ProtocolError {
    #[error("Invalid JSON-RPC format: {details}")]
    InvalidJsonFormat { details: String },

    #[error("Missing required field: {field}")]
    MissingField { field: String },

    #[error("Invalid parameter: {parameter} = {value}")]
    InvalidParameter { parameter: String, value: String },

    #[error("Method not supported: {method}")]
    MethodNotSupported { method: String },

    #[error("Protocol version not supported: {version}")]
    UnsupportedVersion { version: String },

    #[error("Request ID mismatch: expected {expected}, got {actual}")]
    IdMismatch { expected: u64, actual: u64 },

    #[error("Message too large: {size} bytes (max {max_size})")]
    MessageTooLarge { size: usize, max_size: usize },

    #[error("Invalid hex encoding: {hex}")]
    InvalidHexEncoding { hex: String },

    #[error("Unknown notification: {method}")]
    UnknownNotification { method: String },
}

/// Authentication errors (Lỗi xác thực)
#[derive(Debug, Error)]
pub enum AuthError {
    #[error("Invalid worker name format: {worker_name}")]
    InvalidWorkerName { worker_name: String },

    #[error("Wallet address format invalid: {wallet}")]
    InvalidWalletAddress { wallet: String },

    #[error("Authentication rejected by pool")]
    AuthRejected,

    #[error("Worker banned by pool")]
    WorkerBanned,

    #[error("Authentication timeout")]
    AuthTimeout,

    #[error("Password required for this pool")]
    PasswordRequired,
}

/// Job management errors (Lỗi quản lý jobs)
#[derive(Debug, Error)]
pub enum JobError {
    #[error("Invalid job ID: {job_id}")]
    InvalidJobId { job_id: String },

    #[error("Malformed header hash: {reason}")]
    MalformedHeaderHash { reason: String },

    #[error("Malformed seed hash: {reason}")]
    MalformedSeedHash { reason: String },

    #[error("Invalid target difficulty: {target}")]
    InvalidTarget { target: String },

    #[error("Stale job: {job_id} (current {current_job})")]
    StaleJob { job_id: String, current_job: String },

    #[error("Difficulty too high: {difficulty} > {max_difficulty}")]
    DifficultyTooHigh { difficulty: f64, max_difficulty: f64 },

    #[error("Job queue overflow: {size} jobs")]
    JobQueueOverflow { size: usize },

    #[error("No active jobs available")]
    NoActiveJobs,
}

/// Share submission errors (Lỗi nộp shares)
#[derive(Debug, Error)]
pub enum ShareError {
    #[error("Solution rejected: low difficulty")]
    LowDifficulty,

    #[error("Solution rejected: duplicate share")]
    DuplicateShare,

    #[error("Solution rejected: stale job")]
    StaleJob,

    #[error("Solution rejected: hardware error")]
    HardwareError,

    #[error("Submission throttled: {rate_limit} shares/s")]
    RateLimited { rate_limit: f64 },

    #[error("Submission batch too large: {size} shares")]
    BatchTooLarge { size: usize },

    #[error("Invalid nonce format: {nonce}")]
    InvalidNonce { nonce: String },

    #[error("Invalid hash format: {hash}")]
    InvalidHash { hash: String },

    #[error("Invalid mix hash format: {mix_hash}")]
    InvalidMixHash { mix_hash: String },

    #[error("Job not found: {job_id}")]
    JobNotFound { job_id: String },

    #[error("Submission timeout after {timeout_secs}s")]
    SubmissionTimeout { timeout_secs: u64 },

    #[error("Submission rate exceeded: {current_rate} > {limit_rate} shares/s")]
    RateExceeded { current_rate: f64, limit_rate: f64 },
}

/// Pool failover errors (Lỗi chuyển tiếp pool)
#[derive(Debug, Error)]
pub enum FailoverError {
    #[error("No backup pools available")]
    NoBackupPools,

    #[error("All pools failed")]
    AllPoolsFailed,

    #[error("Pool marked as dead: {pool}")]
    PoolDead { pool: String },

    #[error("Automatic failover disabled")]
    FailoverDisabled,

    #[error("Failover timeout: {timeout_secs}s")]
    FailoverTimeout { timeout_secs: u64 },

    #[error("Failed to recover from failure mode")]
    RecoveryFailed,
}

/// Configuration errors (Lỗi cấu hình)
#[derive(Debug, Error)]
pub enum ConfigError {
    #[error("Invalid pool URL format: {url}")]
    InvalidPoolUrl { url: String },

    #[error("Unsupported protocol: {protocol}")]
    UnsupportedProtocol { protocol: String },

    #[error("Invalid port number: {port}")]
    InvalidPort { port: u64 },

    #[error("Missing required parameter: {parameter}")]
    MissingParameter { parameter: String },

    #[error("Conflicting parameters: {param1} vs {param2}")]
    ConflictingParameters { param1: String, param2: String },

    #[error("Value out of range: {parameter} = {value}, expected {min}..{max}")]
    OutOfRange {
        parameter: String,
        value: f64,
        min: f64,
        max: f64,
    },

    #[error("Invalid configuration file: {reason}")]
    InvalidConfigFile { reason: String },
}

impl From<std::io::Error> for StratumError {
    fn from(err: std::io::Error) -> Self {
        use std::io::ErrorKind::*;
        match err.kind() {
            TimedOut => StratumError::Connection {
                source: ConnectionError::Timeout { timeout_secs: 30 }
            },
            ConnectionRefused => StratumError::Connection {
                source: ConnectionError::ConnectionRefused {
                    host: "unknown".to_string(),
                    port: 0,
                }
            },
            NetworkUnreachable => StratumError::Connection {
                source: ConnectionError::NetworkUnreachable {
                    host: "unknown".to_string(),
                    port: 0,
                }
            },
            Interrupted | BrokenPipe | ConnectionAborted => StratumError::Connection {
                source: ConnectionError::UnexpectedDisconnect,
            },
            _ => StratumError::Connection {
                source: ConnectionError::SocketRead {
                    message: err.to_string(),
                }
            },
        }
    }
}

impl From<serde_json::Error> for StratumError {
    fn from(err: serde_json::Error) -> Self {
        StratumError::Protocol {
            source: ProtocolError::InvalidJsonFormat {
                details: err.to_string(),
            },
        }
    }
}

impl From<Elapsed> for StratumError {
    fn from(_err: Elapsed) -> Self {
        StratumError::Connection {
            source: ConnectionError::Timeout { timeout_secs: 30 },
        }
    }
}

impl From<String> for StratumError {
    fn from(message: String) -> Self {
        StratumError::Internal { message }
    }
}

impl From<anyhow::Error> for StratumError {
    fn from(err: anyhow::Error) -> Self {
        StratumError::Internal {
            message: err.to_string(),
        }
    }
}

impl From<hex::FromHexError> for StratumError {
    fn from(err: hex::FromHexError) -> Self {
        StratumError::Protocol {
            source: ProtocolError::InvalidHexEncoding {
                hex: err.to_string(),
            },
        }
    }
}

// Helper alias for Results
pub type Result<T> = std::result::Result<T, StratumError>;