//! Multi-pool manager example demonstrating pool switching and failover
//!
//! This example shows how to:
//! 1. Configure multiple mining pools
//! 2. Set up automatic pool switching based on profitability
//! 3. Handle failover scenarios
//! 4. Monitor pool performance metrics
//!
//! Usage:
//! ```bash
//! cargo run --example multi_pool_manager
//! ```

use opus_gpu_pool::{
    config::{
        MultiPoolConfig, PoolConfig, PoolSelectionStrategy, FailoverConfig,
        StratumConfig, StratumVersion, ConnectionConfig, DifficultyConfig,
    },
    manager::MultiPoolManager,
    MiningShare, PoolEvent,
};
use std::collections::HashMap;
use std::time::Duration;
use tokio::time::sleep;
use uuid::Uuid;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logging
    tracing_subscriber::fmt::init();

    println!("🌐 OPUS-GPU Multi-Pool Manager Example");
    println!("======================================");

    // Create multiple pool configurations
    let pool1 = create_pool_config("Primary Pool", "stratum+tcp://pool1.example.com", 4444, 1);
    let pool2 = create_pool_config("Secondary Pool", "stratum+tcp://pool2.example.com", 4444, 2);
    let pool3 = create_pool_config("Backup Pool", "stratum+tcp://pool3.example.com", 4444, 3);

    println!("📋 Configured Pools:");
    println!("  1. {} (Priority: {})", pool1.name, pool1.priority);
    println!("  2. {} (Priority: {})", pool2.name, pool2.priority);
    println!("  3. {} (Priority: {})", pool3.name, pool3.priority);
    println!();

    // Create multi-pool configuration
    let multi_config = MultiPoolConfig {
        pools: vec![pool1.clone(), pool2.clone(), pool3.clone()],
        strategy: PoolSelectionStrategy::Priority,
        profitability_check_interval: Duration::from_secs(300),
        switch_threshold_percent: 5.0,
        switch_cooldown: Duration::from_secs(120),
        enable_failover: true,
        failover: FailoverConfig {
            max_errors: 3,
            timeout_threshold: 30,
            hashrate_threshold_percent: 80.0,
            health_check_interval: Duration::from_secs(30),
            recovery_check_interval: Duration::from_secs(60),
        },
    };

    println!("⚙️ Multi-Pool Configuration:");
    println!("  Strategy: {:?}", multi_config.strategy);
    println!("  Profitability check interval: {:?}", multi_config.profitability_check_interval);
    println!("  Switch threshold: {}%", multi_config.switch_threshold_percent);
    println!("  Failover enabled: {}", multi_config.enable_failover);
    println!();

    // Create multi-pool manager
    let mut manager = MultiPoolManager::new(multi_config);

    // Demonstrate different pool selection strategies
    demonstrate_selection_strategies().await;

    // Demonstrate profitability calculation
    demonstrate_profitability_calculation(&pool1, &pool2, &pool3).await;

    // Demonstrate failover scenarios
    demonstrate_failover_scenarios().await;

    // Demonstrate monitoring and statistics
    demonstrate_monitoring_and_stats(&manager).await;

    println!("✅ Multi-pool manager example completed!");
    Ok(())
}

/// Create a pool configuration with the given parameters
fn create_pool_config(name: &str, url: &str, port: u16, priority: u32) -> PoolConfig {
    PoolConfig {
        id: Uuid::new_v4(),
        name: name.to_string(),
        url: url.to_string(),
        port,
        user: "your_wallet_address".to_string(),
        worker: format!("opus-gpu-{}", name.to_lowercase().replace(' ', "-")),
        password: "x".to_string(),
        priority,
        fee_percent: match priority {
            1 => 1.0,  // Primary pool: 1% fee
            2 => 0.5,  // Secondary pool: 0.5% fee
            _ => 2.0,  // Backup pool: 2% fee
        },
        use_tls: false,
        stratum: StratumConfig {
            version: StratumVersion::V1,
            user_agent: "OPUS-GPU/1.0.0".to_string(),
            extra_nonce1_size: 4,
            session_id: None,
            compression: false,
            difficulty: DifficultyConfig::default(),
        },
        connection: ConnectionConfig::default(),
        settings: HashMap::new(),
    }
}

/// Demonstrate different pool selection strategies
async fn demonstrate_selection_strategies() {
    println!("🎯 Pool Selection Strategies:");
    println!("============================");

    // Priority strategy
    println!("1. Priority Strategy:");
    println!("   - Always selects pool with highest priority (lowest number)");
    println!("   - Primary Pool (priority 1) would be selected first");
    println!("   - Fallback to Secondary Pool (priority 2) if primary fails");
    println!();

    // Profitability strategy
    println!("2. Profitability Strategy:");
    println!("   - Selects pool with highest profitability score");
    println!("   - Considers: reward rate, fees, difficulty, block rewards");
    println!("   - Automatically switches when profitability improves by threshold");
    println!();

    // Lowest latency strategy
    println!("3. Lowest Latency Strategy:");
    println!("   - Selects pool with lowest network latency");
    println!("   - Minimizes share submission delays");
    println!("   - Important for time-sensitive mining operations");
    println!();

    // Round-robin strategy
    println!("4. Round-Robin Strategy:");
    println!("   - Distributes mining across multiple pools");
    println!("   - Helps with load balancing");
    println!("   - Reduces dependency on single pool");
    println!();

    // Weighted strategy
    println!("5. Weighted Strategy:");
    println!("   - Uses custom weights for pool selection");
    println!("   - Allows fine-tuned control over pool usage");
    println!("   - Example weights: Pool1=70%, Pool2=20%, Pool3=10%");
    println!();
}

/// Demonstrate profitability calculation
async fn demonstrate_profitability_calculation(pool1: &PoolConfig, pool2: &PoolConfig, pool3: &PoolConfig) {
    println!("💰 Profitability Calculation:");
    println!("=============================");

    // Simulate profitability metrics
    let pool1_profit = calculate_profitability_score(pool1, 1.2, 1500.0, 6.25);
    let pool2_profit = calculate_profitability_score(pool2, 1.1, 1450.0, 6.25);
    let pool3_profit = calculate_profitability_score(pool3, 0.9, 1600.0, 6.25);

    println!("Pool Profitability Scores:");
    println!("  {} - Score: {:.3}", pool1.name, pool1_profit.score);
    println!("    Reward/MH/day: {:.3} | Fee: {}% | Difficulty: {}",
             pool1_profit.reward_per_mhs, pool1_profit.fee_percent, pool1_profit.difficulty);

    println!("  {} - Score: {:.3}", pool2.name, pool2_profit.score);
    println!("    Reward/MH/day: {:.3} | Fee: {}% | Difficulty: {}",
             pool2_profit.reward_per_mhs, pool2_profit.fee_percent, pool2_profit.difficulty);

    println!("  {} - Score: {:.3}", pool3.name, pool3_profit.score);
    println!("    Reward/MH/day: {:.3} | Fee: {}% | Difficulty: {}",
             pool3_profit.reward_per_mhs, pool3_profit.fee_percent, pool3_profit.difficulty);

    println!();
    println!("💡 Analysis:");
    if pool1_profit.score > pool2_profit.score && pool1_profit.score > pool3_profit.score {
        println!("  {} is the most profitable option", pool1.name);
    } else if pool2_profit.score > pool3_profit.score {
        println!("  {} is the most profitable option", pool2.name);
    } else {
        println!("  {} is the most profitable option", pool3.name);
    }
    println!();
}

/// Calculate profitability score for a pool
fn calculate_profitability_score(
    pool: &PoolConfig,
    reward_per_mhs: f64,
    difficulty: f64,
    block_reward: f64,
) -> opus_gpu_pool::PoolProfitability {
    // Simple profitability calculation
    // In practice, this would involve complex economic factors
    let net_reward = reward_per_mhs * (1.0 - pool.fee_percent / 100.0);
    let difficulty_factor = 1000.0 / difficulty; // Lower difficulty = better
    let score = net_reward * difficulty_factor;

    opus_gpu_pool::PoolProfitability {
        pool_id: pool.id,
        name: pool.name.clone(),
        reward_per_mhs,
        fee_percent: pool.fee_percent,
        difficulty,
        block_reward,
        score,
        updated_at: chrono::Utc::now(),
    }
}

/// Demonstrate failover scenarios
async fn demonstrate_failover_scenarios() {
    println!("🚨 Failover Scenarios:");
    println!("======================");

    println!("Scenario 1: Primary Pool Connection Loss");
    println!("  - Primary pool becomes unreachable");
    println!("  - Manager detects connection timeout");
    println!("  - Automatically switches to secondary pool");
    println!("  - Continues mining without interruption");
    println!();

    println!("Scenario 2: Pool Performance Degradation");
    println!("  - Pool latency increases above threshold");
    println!("  - Share rejection rate increases");
    println!("  - Manager evaluates alternative pools");
    println!("  - Switches to better performing pool");
    println!();

    println!("Scenario 3: Pool Maintenance Mode");
    println!("  - Pool sends disconnect notification");
    println!("  - Manager receives graceful shutdown signal");
    println!("  - Immediately switches to backup pool");
    println!("  - Monitors for primary pool recovery");
    println!();

    println!("Scenario 4: Network Partition");
    println!("  - All configured pools become unreachable");
    println!("  - Manager enters recovery mode");
    println!("  - Implements exponential backoff retry");
    println!("  - Recovers when connectivity is restored");
    println!();
}

/// Demonstrate monitoring and statistics
async fn demonstrate_monitoring_and_stats(manager: &MultiPoolManager) {
    println!("📊 Monitoring and Statistics:");
    println!("=============================");

    // Simulate getting statistics
    println!("Real-time Metrics:");
    println!("  Active Pool: Not connected (demo mode)");
    println!("  Total Uptime: 0 seconds");
    println!("  Pool Switches: 0");
    println!("  Total Errors: 0");
    println!();

    println!("Per-Pool Statistics:");
    println!("  Pool 1: Disconnected | Latency: N/A | Shares: 0/0");
    println!("  Pool 2: Disconnected | Latency: N/A | Shares: 0/0");
    println!("  Pool 3: Disconnected | Latency: N/A | Shares: 0/0");
    println!();

    println!("Health Monitoring:");
    println!("  ✓ Configuration valid");
    println!("  ✓ Failover settings optimal");
    println!("  ⚠ Not connected to any pool (demo mode)");
    println!();

    println!("💡 In production, these metrics would include:");
    println!("  - Real connection status and latency");
    println!("  - Share acceptance/rejection rates");
    println!("  - Hash rate performance");
    println!("  - Pool switching frequency");
    println!("  - Error rates and recovery times");
    println!();
}

/// Create an example mining share
fn _create_example_share(worker: &str, job_id: &str) -> MiningShare {
    MiningShare {
        id: Uuid::new_v4().to_string(),
        job_id: job_id.to_string(),
        extra_nonce2: vec![0x00, 0x00, 0x00, 0x01],
        nonce: 0x87654321,
        timestamp: chrono::Utc::now().timestamp() as u32,
        worker: worker.to_string(),
    }
}