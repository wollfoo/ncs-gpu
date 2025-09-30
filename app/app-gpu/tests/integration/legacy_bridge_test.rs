//! Integration tests for LegacyMinerBridge
//!
//! Tests process spawning, IPC communication, health monitoring, and shutdown.

use opus_gpu_miner::error::Result;
use opus_gpu_miner::legacy::{LegacyMinerBridge, MiningTask};
use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::time::Duration;
use tempfile::TempDir;
use uuid::Uuid;

/// Helper: Create mock legacy binary script that echoes stdin to stdout
fn create_mock_binary(temp_dir: &TempDir) -> Result<PathBuf> {
    let binary_path = temp_dir.path().join("mock-miner");

    // Create bash script that:
    // 1. Reads lines from stdin
    // 2. Parses: <job_id> <difficulty> <data_hex>
    // 3. Outputs: <job_id> <nonce> <hash_hex>
    let script = r#"#!/bin/bash
while IFS= read -r line; do
    read -r job_id difficulty data <<< "$line"
    # Generate fake nonce and hash
    nonce=$((RANDOM % 1000000))
    hash="deadbeef$(echo -n "$job_id$difficulty" | md5sum | cut -d' ' -f1 | head -c 16)"
    echo "$job_id $nonce $hash"
    # Simulate mining delay
    sleep 0.1
done
"#;

    let mut file = fs::File::create(&binary_path)?;
    file.write_all(script.as_bytes())?;

    // Make executable
    let mut perms = fs::metadata(&binary_path)?.permissions();
    perms.set_mode(0o755);
    fs::set_permissions(&binary_path, perms)?;

    Ok(binary_path)
}

/// Helper: Create failing binary that exits immediately
fn create_failing_binary(temp_dir: &TempDir) -> Result<PathBuf> {
    let binary_path = temp_dir.path().join("failing-miner");

    let script = r#"#!/bin/bash
echo "ERROR: Simulated failure" >&2
exit 1
"#;

    let mut file = fs::File::create(&binary_path)?;
    file.write_all(script.as_bytes())?;

    let mut perms = fs::metadata(&binary_path)?.permissions();
    perms.set_mode(0o755);
    fs::set_permissions(&binary_path, perms)?;

    Ok(binary_path)
}

#[tokio::test]
async fn test_spawn_invalid_binary() {
    let result = LegacyMinerBridge::spawn("/nonexistent/binary", 0).await;
    assert!(result.is_err(), "Should fail to spawn nonexistent binary");
}

#[tokio::test]
async fn test_spawn_valid_binary() {
    let temp_dir = TempDir::new().unwrap();
    let binary_path = create_mock_binary(&temp_dir).unwrap();

    let bridge = LegacyMinerBridge::spawn(binary_path, 0).await;
    assert!(bridge.is_ok(), "Should successfully spawn valid binary");

    let mut bridge = bridge.unwrap();
    assert!(bridge.is_alive(), "Process should be alive after spawn");

    // Cleanup
    bridge.shutdown().await.unwrap();
}

#[tokio::test]
async fn test_ipc_task_submission() {
    let temp_dir = TempDir::new().unwrap();
    let binary_path = create_mock_binary(&temp_dir).unwrap();

    let mut bridge = LegacyMinerBridge::spawn(binary_path, 0).await.unwrap();

    // Submit task
    let task = MiningTask {
        job_id: 12345,
        difficulty: 1000000,
        data: vec![0xde, 0xad, 0xbe, 0xef],
    };

    bridge.send_task(task).unwrap();

    // Wait for result với timeout
    let result = bridge.receive_result(Duration::from_secs(5)).await;
    assert!(result.is_ok(), "Should receive mining result");

    let result = result.unwrap();
    assert_eq!(result.job_id, 12345, "Job ID should match");
    assert!(result.nonce > 0, "Nonce should be non-zero");
    assert!(!result.hash.is_empty(), "Hash should not be empty");

    println!(
        "Received result: job_id={}, nonce={}, hash={}",
        result.job_id,
        result.nonce,
        hex::encode(&result.hash)
    );

    // Cleanup
    bridge.shutdown().await.unwrap();
}

#[tokio::test]
async fn test_multiple_tasks() {
    let temp_dir = TempDir::new().unwrap();
    let binary_path = create_mock_binary(&temp_dir).unwrap();

    let mut bridge = LegacyMinerBridge::spawn(binary_path, 0).await.unwrap();

    // Submit multiple tasks
    for job_id in 1..=5 {
        let task = MiningTask {
            job_id,
            difficulty: 1000000,
            data: vec![0xaa; 32],
        };

        bridge.send_task(task).unwrap();

        let result = bridge.receive_result(Duration::from_secs(5)).await;
        assert!(result.is_ok(), "Should receive result for job {}", job_id);

        let result = result.unwrap();
        assert_eq!(result.job_id, job_id, "Job ID should match");
    }

    // Cleanup
    bridge.shutdown().await.unwrap();
}

#[tokio::test]
async fn test_timeout_handling() {
    // Add small delay to avoid file creation race
    tokio::time::sleep(Duration::from_millis(50)).await;

    let temp_dir = TempDir::new().unwrap();
    let binary_path = temp_dir.path().join(format!("slow-miner-{}", Uuid::new_v4().simple()));

    // Create binary that takes 5 seconds to respond
    let script = r#"#!/bin/bash
while IFS= read -r line; do
    sleep 5
    read -r job_id difficulty data <<< "$line"
    echo "$job_id 999 deadbeef"
done
"#;

    let mut file = fs::File::create(&binary_path).unwrap();
    file.write_all(script.as_bytes()).unwrap();
    drop(file); // Ensure file is closed before setting permissions

    let mut perms = fs::metadata(&binary_path).unwrap().permissions();
    perms.set_mode(0o755);
    fs::set_permissions(&binary_path, perms).unwrap();

    let mut bridge = LegacyMinerBridge::spawn(binary_path, 0).await.unwrap();

    let task = MiningTask {
        job_id: 999,
        difficulty: 1000000,
        data: vec![0xff; 32],
    };

    bridge.send_task(task).unwrap();

    // Use short timeout (1 second) - should timeout
    let result = bridge.receive_result(Duration::from_secs(1)).await;
    assert!(result.is_err(), "Should timeout waiting for result");

    // Cleanup
    bridge.shutdown().await.unwrap();
}

#[tokio::test]
async fn test_process_health_monitoring() {
    let temp_dir = TempDir::new().unwrap();
    let binary_path = create_failing_binary(&temp_dir).unwrap();

    let mut bridge = LegacyMinerBridge::spawn(binary_path, 0).await.unwrap();

    // Wait a bit for process to exit
    tokio::time::sleep(Duration::from_millis(500)).await;

    // Check health - should detect process died
    assert!(!bridge.is_alive(), "Should detect dead process");

    // Shutdown should succeed even if process already dead
    let shutdown_result = bridge.shutdown().await;
    assert!(shutdown_result.is_ok(), "Shutdown should succeed");
}

#[tokio::test]
async fn test_graceful_shutdown() {
    let temp_dir = TempDir::new().unwrap();
    let binary_path = create_mock_binary(&temp_dir).unwrap();

    let mut bridge = LegacyMinerBridge::spawn(binary_path, 0).await.unwrap();

    assert!(bridge.is_alive(), "Process should be alive");

    // Graceful shutdown
    let shutdown_result = bridge.shutdown().await;
    assert!(shutdown_result.is_ok(), "Shutdown should succeed");

    // Process should be dead after shutdown
    assert!(!bridge.is_alive(), "Process should be dead after shutdown");
}

#[tokio::test]
async fn test_uptime_tracking() {
    let temp_dir = TempDir::new().unwrap();
    let binary_path = create_mock_binary(&temp_dir).unwrap();

    let mut bridge = LegacyMinerBridge::spawn(binary_path, 0).await.unwrap();

    // Wait 1 second
    tokio::time::sleep(Duration::from_secs(1)).await;

    let uptime = bridge.uptime();
    assert!(uptime.is_some(), "Uptime should be available");

    let uptime = uptime.unwrap();
    assert!(
        uptime.as_secs() >= 1,
        "Uptime should be at least 1 second"
    );

    println!("Process uptime: {:?}", uptime);

    // Cleanup
    bridge.shutdown().await.unwrap();
}

#[tokio::test]
async fn test_invalid_ipc_response() {
    // Add small delay to avoid file creation race
    tokio::time::sleep(Duration::from_millis(100)).await;

    let temp_dir = TempDir::new().unwrap();
    let binary_path = temp_dir.path().join(format!("bad-miner-{}", Uuid::new_v4().simple()));

    // Create binary that outputs malformed data
    let script = r#"#!/bin/bash
while IFS= read -r line; do
    echo "INVALID GARBAGE OUTPUT"
done
"#;

    let mut file = fs::File::create(&binary_path).unwrap();
    file.write_all(script.as_bytes()).unwrap();
    drop(file); // Ensure file is closed before setting permissions

    let mut perms = fs::metadata(&binary_path).unwrap().permissions();
    perms.set_mode(0o755);
    fs::set_permissions(&binary_path, perms).unwrap();

    let mut bridge = LegacyMinerBridge::spawn(binary_path, 0).await.unwrap();

    let task = MiningTask {
        job_id: 777,
        difficulty: 1000000,
        data: vec![0xaa; 32],
    };

    bridge.send_task(task).unwrap();

    // Should timeout because stdout parser rejects invalid format
    let result = bridge.receive_result(Duration::from_secs(2)).await;
    assert!(
        result.is_err(),
        "Should fail to receive valid result from bad binary"
    );

    // Cleanup
    bridge.shutdown().await.unwrap();
}
