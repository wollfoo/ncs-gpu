//! # Common Test Utilities (Tiện Ích Kiểm Thử Chung)
//!
//! **Shared helper functions** (hàm helper chia sẻ) cho all integration tests.

use std::net::TcpListener;
use std::path::PathBuf;
use std::time::Duration;
use tokio::time::{sleep, Instant};
use tracing::info;
use tracing_subscriber::{fmt, EnvFilter};

/// **Setup test logger** (thiết lập logger test) – khởi tạo tracing subscriber
///
/// Cấu hình logging với:
/// - Pretty format cho console output
/// - Environment variable filtering (RUST_LOG)
/// - Test-friendly formatting
pub fn setup_test_logger() {
    // Ignore error nếu đã được init trong test khác
    let _ = fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("debug")),
        )
        .with_test_writer()
        .try_init();

    info!("📋 Test logger initialized");
}

/// **Wait for condition** (chờ điều kiện) – polling với timeout
///
/// # Arguments (Tham số)
/// - `check`: Closure kiểm tra condition
/// - `timeout`: Thời gian timeout tối đa
/// - `poll_interval`: Khoảng thời gian giữa các lần check
///
/// # Returns (Trả về)
/// - `true`: Condition thỏa mãn trước timeout
/// - `false`: Timeout xảy ra
///
/// # Examples (Ví dụ)
/// ```
/// let success = wait_for_condition(
///     || gpu.is_initialized(),
///     Duration::from_secs(5),
///     Duration::from_millis(100)
/// ).await;
/// ```
pub async fn wait_for_condition<F>(
    mut check: F,
    timeout: Duration,
    poll_interval: Duration,
) -> bool
where
    F: FnMut() -> bool,
{
    let start = Instant::now();

    while start.elapsed() < timeout {
        if check() {
            return true;
        }
        sleep(poll_interval).await;
    }

    false
}

/// **Find free port** (tìm port khả dụng) – get available TCP port
///
/// Sử dụng OS kernel để bind port 0 (automatic allocation),
/// sau đó lấy port number và release socket.
///
/// # Returns (Trả về)
/// - Port number khả dụng
///
/// # Panics (Panic khi)
/// - Không thể bind socket (cực kỳ hiếm)
///
/// # Examples (Ví dụ)
/// ```
/// let port = find_free_port();
/// let pool = MockStratumPool::new(port);
/// ```
pub fn find_free_port() -> u16 {
    // Bind to port 0 → OS tự động cấp port khả dụng
    let listener = TcpListener::bind("127.0.0.1:0").expect("Failed to bind to port 0");

    // Lấy port number được cấp
    let port = listener.local_addr().expect("Failed to get local address").port();

    // Drop listener → release port
    drop(listener);

    info!("🔌 Found free port: {}", port);
    port
}

/// **Cleanup test artifacts** (dọn dẹp artifact test) – xóa test files/logs
///
/// Dọn dẹp:
/// - Test log files trong `tests/logs/`
/// - Temporary config files `test-*.toml`
/// - Temporary state files `*.test.state`
///
/// # Examples (Ví dụ)
/// ```
/// #[tokio::test]
/// async fn my_test() {
///     // ... test logic ...
///     cleanup_test_artifacts();
/// }
/// ```
pub fn cleanup_test_artifacts() {
    let cleanup_paths = vec![
        PathBuf::from("tests/logs/"),
        PathBuf::from("test-*.toml"),
        PathBuf::from("*.test.state"),
    ];

    for path in cleanup_paths {
        if path.exists() {
            if path.is_dir() {
                let _ = std::fs::remove_dir_all(&path);
                info!("🗑️  Removed directory: {:?}", path);
            } else {
                let _ = std::fs::remove_file(&path);
                info!("🗑️  Removed file: {:?}", path);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_find_free_port() {
        let port1 = find_free_port();
        let port2 = find_free_port();

        // Các port phải khác nhau (xác suất cao)
        assert_ne!(port1, port2);

        // Port phải trong range hợp lệ
        assert!(port1 > 1024); // Không phải well-known ports
        assert!(port2 > 1024);
    }

    #[tokio::test]
    async fn test_wait_for_condition_success() {
        let mut counter = 0;

        let result = wait_for_condition(
            || {
                counter += 1;
                counter >= 3
            },
            Duration::from_secs(2),
            Duration::from_millis(100),
        )
        .await;

        assert!(result);
        assert!(counter >= 3);
    }

    #[tokio::test]
    async fn test_wait_for_condition_timeout() {
        let result = wait_for_condition(
            || false, // Không bao giờ true
            Duration::from_millis(200),
            Duration::from_millis(50),
        )
        .await;

        assert!(!result);
    }

    #[test]
    fn test_cleanup_does_not_crash() {
        // Test không crash ngay cả khi không có file
        cleanup_test_artifacts();
    }
}
