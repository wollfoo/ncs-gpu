//! Simple pool client example demonstrating basic pool communication
//!
//! This example shows how to:
//! 1. Create and configure a pool client
//! 2. Connect to a mining pool using Stratum v1
//! 3. Subscribe to mining work
//! 4. Authorize a worker
//! 5. Handle mining work and submit shares
//!
//! Usage:
//! ```bash
//! cargo run --example simple_pool_client
//! ```

use opus_gpu_pool::{
    config::{PoolConfig, StratumConfig, StratumVersion, ConnectionConfig, DifficultyConfig},
    client::PoolClient,
    MiningShare, PoolEvent,
};
use std::collections::HashMap;
use tokio::time::{sleep, Duration};
use uuid::Uuid;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logging
    tracing_subscriber::fmt::init();

    println!("🚀 OPUS-GPU Pool Client Example");
    println!("================================");

    // Create pool configuration
    let pool_config = PoolConfig {
        id: Uuid::new_v4(),
        name: "Example Pool".to_string(),
        url: "stratum+tcp://pool.example.com".to_string(),
        port: 4444,
        user: "your_wallet_address".to_string(),
        worker: "opus-gpu-worker".to_string(),
        password: "x".to_string(),
        priority: 1,
        fee_percent: 1.0,
        use_tls: false,
        stratum: StratumConfig {
            version: StratumVersion::V1,
            user_agent: "OPUS-GPU/1.0.0".to_string(),
            extra_nonce1_size: 4,
            session_id: None,
            compression: false,
            difficulty: DifficultyConfig {
                initial: 1.0,
                minimum: 0.1,
                maximum: 10000.0,
                variance_percent: 15.0,
                target_time: 30,
                retarget_period: 10,
            },
        },
        connection: ConnectionConfig {
            timeout: Duration::from_secs(30),
            max_reconnects: 5,
            reconnect_delay: Duration::from_secs(2),
            max_reconnect_delay: Duration::from_secs(60),
            keepalive_interval: Duration::from_secs(60),
            max_idle_time: Duration::from_secs(300),
            enable_pooling: true,
            pool_size: 5,
            pool_timeout: Duration::from_secs(10),
        },
        settings: HashMap::new(),
    };

    println!("📋 Pool Configuration:");
    println!("  Name: {}", pool_config.name);
    println!("  URL: {}:{}", pool_config.url, pool_config.port);
    println!("  Worker: {}", pool_config.worker);
    println!("  Stratum Version: {}", pool_config.stratum.version);
    println!();

    // Create pool client
    let mut client = PoolClient::new(pool_config.clone());

    // Get event receiver for handling pool events
    let mut event_receiver = client.take_event_receiver()
        .expect("Failed to get event receiver");

    println!("🔌 Connecting to pool...");

    // Note: This is a demonstration. In a real scenario, you would:
    // 1. Have a valid pool URL and credentials
    // 2. Handle connection errors appropriately
    // 3. Implement proper mining logic

    // Since this is an example with potentially invalid pool URL,
    // we'll demonstrate the API usage in a simulated way
    demonstrate_api_usage(&mut client).await;

    // Simulate event handling
    println!("📡 Starting event handler...");
    let event_handler = tokio::spawn(async move {
        let mut processed_events = 0;
        while let Some(event) = event_receiver.recv().await {
            match event {
                PoolEvent::NewWork(work) => {
                    println!("📥 New mining work received:");
                    println!("  Job ID: {:?}", work.job_id);
                    println!("  Clean jobs: {}", work.clean_jobs);
                    println!("  Timestamp: {}", work.timestamp);
                }
                PoolEvent::ShareResult { id, accepted, reason } => {
                    if accepted {
                        println!("✅ Share {} accepted!", id);
                    } else {
                        println!("❌ Share {} rejected: {:?}", id, reason);
                    }
                }
                PoolEvent::DifficultyChanged(difficulty) => {
                    println!("🎯 Difficulty changed to: {}", difficulty);
                }
                PoolEvent::StatusChanged { pool_id, status } => {
                    println!("🔄 Pool {} status changed to: {:?}", pool_id, status);
                }
                PoolEvent::PoolSwitched { from, to } => {
                    println!("🔀 Pool switched from {} to {}", from, to);
                }
                PoolEvent::Error { pool_id, error } => {
                    println!("⚠️ Pool {} error: {}", pool_id, error);
                }
            }

            processed_events += 1;
            if processed_events >= 10 {
                println!("📊 Processed {} events, stopping demonstration", processed_events);
                break;
            }
        }
    });

    // Wait a bit for demonstration
    sleep(Duration::from_secs(2)).await;

    // Cancel the event handler
    event_handler.abort();

    println!("✅ Example completed successfully!");
    Ok(())
}

/// Demonstrate API usage without actual network connections
async fn demonstrate_api_usage(client: &mut PoolClient) {
    println!("🎭 Demonstrating API usage (simulated):");

    // Show initial state
    let state = client.get_state().await;
    println!("  Initial state: {:?}", state);

    let stats = client.get_client_stats().await;
    println!("  Initial stats: connection_attempts={}, uptime={:?}",
             stats.connection_attempts, stats.uptime);

    // Demonstrate share creation
    let example_share = MiningShare {
        id: Uuid::new_v4().to_string(),
        job_id: "example_job_001".to_string(),
        extra_nonce2: vec![0x00, 0x00, 0x00, 0x01],
        nonce: 0x12345678,
        timestamp: chrono::Utc::now().timestamp() as u32,
        worker: "opus-gpu-worker".to_string(),
    };

    println!("  Example share created:");
    println!("    ID: {}", example_share.id);
    println!("    Job ID: {}", example_share.job_id);
    println!("    Nonce: 0x{:08x}", example_share.nonce);
    println!("    Worker: {}", example_share.worker);

    // In a real implementation, you would:
    // 1. Call client.connect().await
    // 2. Call client.subscribe().await
    // 3. Call client.authorize().await
    // 4. Handle mining work and submit shares
    // 5. Monitor pool statistics and events

    println!("  💡 Note: This example demonstrates API usage");
    println!("     In production, you would connect to a real pool");
    println!("     and implement actual mining logic.");
}