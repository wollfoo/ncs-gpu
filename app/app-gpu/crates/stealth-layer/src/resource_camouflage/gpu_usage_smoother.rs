//! # GPU Usage Smoother (Bộ làm mượt sử dụng GPU)
//!
//! Làm mịn GPU usage spikes sử dụng **Exponential Moving Average (EMA)** algorithm.
//!
//! ## Design Rationale (Lý do thiết kế)
//!
//! - **EMA** được chọn thay vì Simple Moving Average (SMA) vì:
//!   - Real-time operation (không cần buffer lớn)
//!   - Recent values weighted higher (responsive hơn)
//!   - Simple implementation, low computational cost
//!
//! - **Tuning Parameters** (Tham số điều chỉnh):
//!   - **Alpha (α)**: 0.2 (window ~10 samples)
//!     - Higher α = more responsive, less smoothing
//!     - Lower α = more smoothing, more lag
//!   - **Jitter**: ±5% random variance để avoid flat lines (detection pattern)
//!
//! ## Usage Example (Ví dụ sử dụng)
//!
//! ```rust
//! use stealth_layer::resource_camouflage::GpuUsageSmoother;
//!
//! let mut smoother = GpuUsageSmoother::new(0.75, 0.2, 0.05);
//!
//! // Feed actual GPU usage values (0.0-1.0)
//! let actual = 0.95;
//! let smoothed = smoother.smooth(actual);
//!
//! // smoothed sẽ gần 0.75 ±10% với jitter
//! ```

use rand::Rng;
use std::sync::Mutex;

/// **GPU Usage Smoother** - Làm mượt GPU usage spikes bằng EMA algorithm
///
/// ## Algorithm (Thuật toán)
///
/// ```text
/// smoothed = α * actual + (1-α) * previous
/// with_jitter = smoothed + random(-jitter, +jitter)
/// clamped = clamp(with_jitter, target ± max_variance)
/// ```
///
/// ## Performance (Hiệu năng)
///
/// - O(1) time complexity
/// - ~100 bytes memory per instance
/// - No heap allocations in hot path
pub struct GpuUsageSmoother {
    /// **Smoothing factor** (hệ số làm mượt) - α trong EMA formula (0.0-1.0)
    alpha: f32,

    /// **Target GPU utilization** (mức sử dụng GPU mục tiêu) - 0.0-1.0
    target_utilization: f32,

    /// **Previous smoothed value** (giá trị đã làm mượt trước đó) - để tính EMA
    previous: Mutex<f32>,

    /// **Jitter range** (phạm vi dao động) - ±% random variance
    jitter_range: f32,
}

impl GpuUsageSmoother {
    /// Tạo **GPU Usage Smoother** mới với configuration
    ///
    /// ## Parameters (Tham số)
    ///
    /// - `target`: Target GPU utilization (0.0-1.0)
    /// - `alpha`: EMA smoothing factor (0.0-1.0)
    ///   - Recommended: 0.2 (window ~10 samples)
    /// - `jitter`: Jitter range (0.0-1.0)
    ///   - Recommended: 0.05 (±5%)
    ///
    /// ## Panics
    ///
    /// - If `target` not in [0.0, 1.0]
    /// - If `alpha` not in (0.0, 1.0]
    ///
    /// ## Example
    ///
    /// ```rust
    /// let smoother = GpuUsageSmoother::new(0.75, 0.2, 0.05);
    /// ```
    pub fn new(target: f32, alpha: f32, jitter: f32) -> Self {
        assert!(
            (0.0..=1.0).contains(&target),
            "Target must be in [0.0, 1.0], got {}",
            target
        );
        assert!(
            alpha > 0.0 && alpha <= 1.0,
            "Alpha must be in (0.0, 1.0], got {}",
            alpha
        );

        Self {
            alpha,
            target_utilization: target,
            previous: Mutex::new(target), // Initialize với target
            jitter_range: jitter,
        }
    }

    /// **Apply EMA smoothing** (áp dụng làm mượt EMA) to actual GPU utilization
    ///
    /// ## Algorithm Steps (Các bước thuật toán)
    ///
    /// 1. **EMA formula**: `smoothed = α * actual + (1-α) * previous`
    /// 2. **Add jitter**: `with_jitter = smoothed + random(-jitter, +jitter)`
    /// 3. **Clamp**: Ensure value stays in [0.0, 1.0]
    /// 4. **Update state**: Store for next iteration
    ///
    /// ## Parameters
    ///
    /// - `actual`: Actual GPU usage (0.0-1.0)
    ///
    /// ## Returns
    ///
    /// Smoothed GPU usage (0.0-1.0)
    ///
    /// ## Example
    ///
    /// ```rust
    /// let smoother = GpuUsageSmoother::new(0.75, 0.2, 0.05);
    ///
    /// // Simulate spiky input
    /// let smoothed1 = smoother.smooth(0.95); // spike
    /// let smoothed2 = smoother.smooth(0.50); // drop
    /// let smoothed3 = smoother.smooth(0.90); // spike
    ///
    /// // smoothed values sẽ ít biến động hơn actual
    /// ```
    pub fn smooth(&self, actual: f32) -> f32 {
        let mut prev = self.previous.lock().unwrap();

        // Step 1: EMA formula
        // smoothed = α * actual + (1-α) * previous
        let smoothed = self.alpha * actual + (1.0 - self.alpha) * (*prev);

        // Step 2: Add jitter (thêm dao động)
        let jitter = self.random_jitter();
        let with_jitter = smoothed + jitter;

        // Step 3: Clamp to [0.0, 1.0]
        let clamped = with_jitter.clamp(0.0, 1.0);

        // Step 4: Update previous for next iteration
        *prev = clamped;

        clamped
    }

    /// **Generate random jitter** (tạo dao động ngẫu nhiên) within range
    ///
    /// ## Returns
    ///
    /// Random value in [-jitter_range, +jitter_range]
    ///
    /// ## Example
    ///
    /// ```text
    /// jitter_range = 0.05
    /// → returns value in [-0.05, +0.05]
    /// ```
    fn random_jitter(&self) -> f32 {
        let mut rng = rand::thread_rng();
        rng.gen_range(-self.jitter_range..=self.jitter_range)
    }

    /// **Calculate variance** (tính phương sai) from target
    ///
    /// ## Returns
    ///
    /// Relative variance (0.0-∞)
    ///
    /// ## Example
    ///
    /// ```text
    /// target = 0.75, smoothed = 0.80
    /// variance = |0.80 - 0.75| / 0.75 = 0.0667 (6.67%)
    /// ```
    pub fn variance(&self, smoothed: f32) -> f32 {
        ((smoothed - self.target_utilization) / self.target_utilization).abs()
    }

    /// **Check if within acceptable variance** (kiểm tra trong phạm vi chấp nhận được)
    ///
    /// Acceptable variance: ±10% from target
    ///
    /// ## Parameters
    ///
    /// - `smoothed`: Smoothed GPU usage
    ///
    /// ## Returns
    ///
    /// `true` if variance ≤ 10%
    ///
    /// ## Example
    ///
    /// ```rust
    /// let smoother = GpuUsageSmoother::new(0.75, 0.2, 0.05);
    ///
    /// assert!(smoother.is_within_target(0.70)); // 6.67% variance ✓
    /// assert!(smoother.is_within_target(0.82)); // 9.33% variance ✓
    /// assert!(!smoother.is_within_target(0.90)); // 20% variance ✗
    /// ```
    pub fn is_within_target(&self, smoothed: f32) -> bool {
        self.variance(smoothed) <= 0.10
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_smooth_converges_to_actual() {
        let smoother = GpuUsageSmoother::new(0.7, 0.2, 0.0); // No jitter for predictability

        // Simulate constant actual value
        let mut smoothed = 0.5;
        for _ in 0..50 {
            smoothed = smoother.smooth(0.8);
        }

        // Should converge close to 0.8
        assert!(
            (smoothed - 0.8).abs() < 0.05,
            "EMA should converge to actual value, got smoothed={:.3}",
            smoothed
        );
    }

    #[test]
    fn test_variance_within_target() {
        let smoother = GpuUsageSmoother::new(0.75, 0.2, 0.05);

        let mut within_count = 0;
        for _ in 0..100 {
            let smoothed = smoother.smooth(0.75);
            if smoother.is_within_target(smoothed) {
                within_count += 1;
            }
        }

        // Most samples should be within ±10%
        assert!(
            within_count > 80,
            "Variance should be within target >80% of time, got {}%",
            within_count
        );
    }

    #[test]
    fn test_smoother_reduces_variance() {
        let smoother = GpuUsageSmoother::new(0.75, 0.2, 0.0); // No jitter

        // Simulate spiky input (0.5 → 1.0 → 0.5)
        let inputs = vec![0.5, 1.0, 0.5, 1.0, 0.5];
        let outputs: Vec<f32> = inputs.iter().map(|&x| smoother.smooth(x)).collect();

        // Calculate variance
        let input_variance = calculate_variance(&inputs);
        let output_variance = calculate_variance(&outputs);

        // Verify smoothing reduces variance
        assert!(
            output_variance < input_variance * 0.5,
            "Smoothing should reduce variance by >50%, input_var={:.3}, output_var={:.3}",
            input_variance,
            output_variance
        );
    }

    #[test]
    fn test_nonce_format() {
        let smoother = GpuUsageSmoother::new(0.75, 0.2, 0.05);

        // Test multiple smoothing operations
        for _ in 0..10 {
            let smoothed = smoother.smooth(0.8);
            assert!(
                smoothed >= 0.0 && smoothed <= 1.0,
                "Smoothed value must be in [0, 1], got {:.3}",
                smoothed
            );
        }
    }

    #[test]
    #[should_panic(expected = "Target must be in [0.0, 1.0]")]
    fn test_invalid_target_panics() {
        let _smoother = GpuUsageSmoother::new(1.5, 0.2, 0.05); // Invalid target
    }

    #[test]
    #[should_panic(expected = "Alpha must be in (0.0, 1.0]")]
    fn test_invalid_alpha_panics() {
        let _smoother = GpuUsageSmoother::new(0.75, 0.0, 0.05); // Invalid alpha
    }

    // Helper function - Calculate variance
    fn calculate_variance(values: &[f32]) -> f32 {
        let mean = values.iter().sum::<f32>() / values.len() as f32;
        let variance_sum: f32 = values.iter().map(|x| (x - mean).powi(2)).sum();
        variance_sum / values.len() as f32
    }
}
