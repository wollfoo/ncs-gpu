# Agent-GPU Pool Communication Module

Advanced pool communication module for Agent-GPU mining platform, supporting Stratum protocols, multi-pool management, and intelligent failover capabilities.

## Features

### 🌐 **Stratum Protocol Support**
- **Stratum v1**: Complete implementation with JSON-RPC messaging
- **Stratum v2**: Support for next-generation mining protocol
- **Protocol Detection**: Automatic protocol version detection
- **Message Handling**: Robust message parsing and validation

### 🔗 **Connection Management**
- **Connection Pooling**: Efficient connection reuse and management
- **TLS/SSL Support**: Secure encrypted connections
- **WebSocket Support**: Modern WebSocket-based communication
- **Failover**: Automatic connection recovery with exponential backoff
- **Keep-Alive**: Connection health monitoring and maintenance

### 🏊 **Multi-Pool Management**
- **Pool Selection Strategies**: Priority, profitability, latency-based, round-robin, weighted
- **Automatic Switching**: Intelligent pool switching based on performance metrics
- **Profitability Monitoring**: Real-time profitability calculation and comparison
- **Health Monitoring**: Continuous pool health and performance assessment
- **Failover Management**: Seamless failover between pools

### 📊 **Monitoring & Statistics**
- **Real-time Metrics**: Connection status, latency, error rates
- **Share Tracking**: Submission, acceptance, and rejection statistics
- **Performance Analytics**: Hashrate monitoring and optimization
- **Event System**: Comprehensive event notifications for monitoring

### 🛡️ **Security & Reliability**
- **TLS Encryption**: Secure communication with certificate validation
- **Authentication**: Worker authorization and session management
- **Error Handling**: Comprehensive error classification and recovery
- **Rate Limiting**: Protection against abuse and DoS attacks

## Architecture

```text
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Pool Client   │───▶│  Stratum Layer  │───▶│   Connection    │
│                 │    │                 │    │      Pool       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Pool Manager   │    │  Protocol       │    │   Failover      │
│                 │    │   Handler       │    │    Manager      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Quick Start

### Basic Pool Client

```rust
use opus_gpu_pool::{
    config::{PoolConfig, StratumConfig, StratumVersion},
    client::PoolClient,
    MiningShare,
};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create pool configuration
    let config = PoolConfig {
        id: uuid::Uuid::new_v4(),
        name: "My Mining Pool".to_string(),
        url: "stratum+tcp://pool.example.com".to_string(),
        port: 4444,
        user: "your_wallet_address".to_string(),
        worker: "worker1".to_string(),
        password: "x".to_string(),
        stratum: StratumConfig {
            version: StratumVersion::V1,
            user_agent: "Agent-GPU/1.0.0".to_string(),
            ..Default::default()
        },
        ..Default::default()
    };

    // Create and connect client
    let mut client = PoolClient::new(config);
    client.full_setup().await?;

    // Submit a mining share
    let share = MiningShare {
        id: uuid::Uuid::new_v4().to_string(),
        job_id: "job_001".to_string(),
        extra_nonce2: vec![0x00, 0x00, 0x00, 0x01],
        nonce: 0x12345678,
        timestamp: chrono::Utc::now().timestamp() as u32,
        worker: "worker1".to_string(),
    };

    let accepted = client.submit_share(share).await?;
    println!("Share accepted: {}", accepted);

    Ok(())
}
```

### Multi-Pool Manager

```rust
use opus_gpu_pool::{
    config::{MultiPoolConfig, PoolSelectionStrategy},
    manager::MultiPoolManager,
};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Configure multiple pools
    let pool1 = create_pool_config("Primary Pool", "pool1.example.com", 1);
    let pool2 = create_pool_config("Backup Pool", "pool2.example.com", 2);

    let multi_config = MultiPoolConfig {
        pools: vec![pool1, pool2],
        strategy: PoolSelectionStrategy::Profitability,
        enable_failover: true,
        ..Default::default()
    };

    // Create and start multi-pool manager
    let mut manager = MultiPoolManager::new(multi_config);
    manager.start().await?;

    // Manager automatically handles pool switching and failover
    // Submit shares through the active pool
    let share = create_mining_share();
    let accepted = manager.submit_share(share).await?;

    Ok(())
}
```

## Configuration

### Pool Configuration

```rust
use opus_gpu_pool::config::{PoolConfig, StratumConfig, ConnectionConfig};
use std::time::Duration;

let config = PoolConfig {
    id: uuid::Uuid::new_v4(),
    name: "Example Pool".to_string(),
    url: "stratum+tcp://pool.example.com".to_string(),
    port: 4444,
    user: "wallet_address".to_string(),
    worker: "worker_name".to_string(),
    password: "password".to_string(),
    priority: 1,
    fee_percent: 1.0,
    use_tls: true,  // Enable TLS encryption

    stratum: StratumConfig {
        version: StratumVersion::V1,
        user_agent: "Agent-GPU/1.0.0".to_string(),
        extra_nonce1_size: 4,
        compression: false,
        ..Default::default()
    },

    connection: ConnectionConfig {
        timeout: Duration::from_secs(30),
        max_reconnects: 5,
        reconnect_delay: Duration::from_secs(2),
        keepalive_interval: Duration::from_secs(60),
        enable_pooling: true,
        pool_size: 10,
        ..Default::default()
    },

    ..Default::default()
};
```

### Multi-Pool Configuration

```rust
use opus_gpu_pool::config::{MultiPoolConfig, PoolSelectionStrategy, FailoverConfig};

let multi_config = MultiPoolConfig {
    pools: vec![pool1, pool2, pool3],

    // Selection strategy
    strategy: PoolSelectionStrategy::Profitability,

    // Profitability monitoring
    profitability_check_interval: Duration::from_secs(300),
    switch_threshold_percent: 5.0,
    switch_cooldown: Duration::from_secs(120),

    // Failover configuration
    enable_failover: true,
    failover: FailoverConfig {
        max_errors: 3,
        timeout_threshold: 30,
        hashrate_threshold_percent: 80.0,
        health_check_interval: Duration::from_secs(30),
        recovery_check_interval: Duration::from_secs(60),
    },
};
```

## Pool Selection Strategies

### 1. Priority Strategy
```rust
strategy: PoolSelectionStrategy::Priority,
```
Always uses the pool with the highest priority (lowest priority number).

### 2. Profitability Strategy
```rust
strategy: PoolSelectionStrategy::Profitability,
```
Automatically switches to the most profitable pool based on:
- Reward rates
- Pool fees
- Network difficulty
- Block rewards

### 3. Lowest Latency Strategy
```rust
strategy: PoolSelectionStrategy::LowestLatency,
```
Selects the pool with the lowest network latency for optimal performance.

### 4. Round Robin Strategy
```rust
strategy: PoolSelectionStrategy::RoundRobin,
```
Distributes mining work across multiple pools in rotation.

### 5. Weighted Strategy
```rust
use std::collections::HashMap;

let mut weights = HashMap::new();
weights.insert(pool1_id, 0.7);  // 70%
weights.insert(pool2_id, 0.3);  // 30%

strategy: PoolSelectionStrategy::Weighted(weights),
```
Uses custom weights to control pool usage distribution.

## Event Handling

```rust
use opus_gpu_pool::PoolEvent;

let mut event_receiver = client.take_event_receiver().unwrap();

tokio::spawn(async move {
    while let Some(event) = event_receiver.recv().await {
        match event {
            PoolEvent::NewWork(work) => {
                println!("New work: job_id={:?}", work.job_id);
                // Handle new mining work
            },
            PoolEvent::ShareResult { id, accepted, reason } => {
                if accepted {
                    println!("Share {} accepted", id);
                } else {
                    println!("Share {} rejected: {:?}", id, reason);
                }
            },
            PoolEvent::DifficultyChanged(difficulty) => {
                println!("Difficulty changed to: {}", difficulty);
            },
            PoolEvent::StatusChanged { pool_id, status } => {
                println!("Pool {} status: {:?}", pool_id, status);
            },
            PoolEvent::PoolSwitched { from, to } => {
                println!("Switched from pool {} to {}", from, to);
            },
            PoolEvent::Error { pool_id, error } => {
                println!("Pool {} error: {}", pool_id, error);
            },
        }
    }
});
```

## Statistics and Monitoring

### Client Statistics

```rust
let stats = client.get_client_stats().await;
println!("Connection attempts: {}", stats.connection_attempts);
println!("Acceptance rate: {:.2}%", stats.acceptance_rate());
println!("Average latency: {:.2}ms", stats.avg_latency_ms);
println!("Uptime: {:?}", stats.uptime);
```

### Pool Statistics

```rust
let pool_stats = client.get_pool_stats().await?;
println!("Pool: {}", pool_stats.url);
println!("Status: {:?}", pool_stats.status);
println!("Shares: {}/{}", pool_stats.shares_accepted, pool_stats.shares_submitted);
println!("Difficulty: {}", pool_stats.difficulty);
println!("Connected since: {}", pool_stats.connected_since);
```

### Multi-Pool Statistics

```rust
let all_stats = manager.get_all_pool_stats().await?;
for (pool_id, stats) in all_stats {
    println!("Pool {}: status={:?}, latency={:.2}ms",
             pool_id, stats.status, stats.latency_ms);
}

let manager_stats = manager.get_multi_manager_stats().await;
println!("Active pool: {:?}", manager_stats.active_pool);
println!("Pool switches: {}", manager_stats.pool_switches);
println!("Total errors: {}", manager_stats.total_errors);
```

## Error Handling

The module provides comprehensive error handling with detailed error types:

```rust
use opus_gpu_pool::{PoolError, PoolResult};

match client.connect().await {
    Ok(()) => println!("Connected successfully"),
    Err(PoolError::Connection(msg)) => {
        println!("Connection error: {}", msg);
        // Implement retry logic
    },
    Err(PoolError::Authentication(msg)) => {
        println!("Authentication failed: {}", msg);
        // Check credentials
    },
    Err(PoolError::Timeout(msg)) => {
        println!("Operation timed out: {}", msg);
        // Try different pool or adjust timeouts
    },
    Err(e) => {
        println!("Other error: {}", e);
        // Generic error handling
    }
}
```

### Error Recovery

```rust
if let Err(e) = client.submit_share(share).await {
    if e.is_recoverable() {
        // Implement retry logic
        tokio::time::sleep(Duration::from_secs(1)).await;
        let _ = client.submit_share(share).await;
    }

    if e.requires_reconnection() {
        // Reconnect to pool
        let _ = client.reconnect().await;
    }
}
```

## Examples

Run the included examples to see the module in action:

```bash
# Basic pool client
cargo run --example simple_pool_client

# Multi-pool management
cargo run --example multi_pool_manager
```

## Testing

Run the test suite:

```bash
# Unit tests
cargo test

# Integration tests
cargo test --test integration

# All tests with output
cargo test -- --nocapture
```

## Performance Considerations

### Connection Pooling
- Enable connection pooling for better resource utilization
- Configure appropriate pool sizes based on expected load
- Monitor connection pool statistics

### Latency Optimization
- Use lowest latency pool selection strategy for time-sensitive operations
- Configure appropriate timeout values
- Enable compression for high-throughput scenarios

### Memory Usage
- Connection pools reuse connections to minimize memory overhead
- Event channels are bounded to prevent memory leaks
- Statistics are collected efficiently with minimal overhead

## Security Best Practices

### TLS Configuration
```rust
config.use_tls = true;
```

### Worker Authentication
```rust
// Use strong passwords and secure credential storage
config.password = env::var("MINING_PASSWORD").unwrap_or_else(|_| "secure_password".to_string());
```

### Certificate Validation
The module automatically validates TLS certificates for secure connections.

## Troubleshooting

### Common Issues

#### Connection Timeouts
```rust
// Increase timeout values
config.connection.timeout = Duration::from_secs(60);
config.connection.max_reconnect_delay = Duration::from_secs(120);
```

#### Authentication Failures
- Verify wallet address and worker credentials
- Check pool-specific authentication requirements
- Ensure worker name format matches pool requirements

#### High Latency
- Use `PoolSelectionStrategy::LowestLatency`
- Configure multiple pools in different geographic regions
- Monitor and optimize network connectivity

#### Share Rejections
- Verify work validation logic
- Check difficulty settings
- Monitor pool-specific requirements

## Contributing

Contributions are welcome! Please see the main Agent-GPU repository for contribution guidelines.

## License

This module is part of the Agent-GPU project and is licensed under the MIT License.