// Build script for OPUS-GPU Monitor module

use std::env;

fn main() {
    // Add conditional compilation flags based on features
    println!("cargo:rerun-if-changed=build.rs");

    // Enable NVIDIA features if available
    if cfg!(feature = "nvidia") {
        println!("cargo:rustc-cfg=feature=\"nvidia\"");
    }

    // Check for system dependencies
    if env::var("CARGO_FEATURE_PROMETHEUS").is_ok() {
        println!("cargo:rustc-cfg=feature=\"prometheus\"");
    }

    if env::var("CARGO_FEATURE_OPENTELEMETRY").is_ok() {
        println!("cargo:rustc-cfg=feature=\"opentelemetry\"");
    }

    // Print build information
    println!("cargo:rustc-env=BUILD_TIME={}", chrono::Utc::now().timestamp());
    println!("cargo:rustc-env=BUILD_VERSION={}", env::var("CARGO_PKG_VERSION").unwrap_or_default());

    // Link system libraries if needed
    #[cfg(target_os = "linux")]
    {
        println!("cargo:rustc-link-lib=dl");
    }
}