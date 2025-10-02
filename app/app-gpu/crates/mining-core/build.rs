//! Build script cho mining-core crate
//! Compile CUDA kernels và link với Rust code

use std::env;
use std::path::PathBuf;

fn main() {
    println!("cargo:rerun-if-changed=src/kernels/ethash.cu");
    println!("cargo:rerun-if-changed=src/cuda/hash_kernel.cu");
    println!("cargo:rerun-if-changed=src/cuda/mining_kernel.cu");
    
    // Check if CUDA toolkit is available
    let cuda_available = check_cuda_available();
    
    if cuda_available {
        println!("cargo:rustc-cfg=feature=\"cuda\"");
        compile_cuda_kernels();
    } else {
        println!("cargo:warning=CUDA toolkit not found. Building without GPU support.");
        println!("cargo:warning=Install CUDA toolkit from: https://developer.nvidia.com/cuda-downloads");
    }
}

fn check_cuda_available() -> bool {
    // Try to find nvcc compiler
    if let Ok(_) = which::which("nvcc") {
        println!("cargo:warning=Found CUDA compiler (nvcc)");
        return true;
    }
    
    // Check common CUDA installation paths
    let cuda_paths = vec![
        "/usr/local/cuda",
        "/usr/local/cuda-11.0",
        "/usr/local/cuda-11.8",
        "/usr/local/cuda-12.0",
        "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v11.0",
        "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.0",
    ];
    
    for path in cuda_paths {
        let nvcc_path = PathBuf::from(path).join("bin").join("nvcc");
        if nvcc_path.exists() {
            println!("cargo:warning=Found CUDA at: {}", path);
            return true;
        }
    }
    
    false
}

fn compile_cuda_kernels() {
    let out_dir = env::var("OUT_DIR").unwrap();
    let cuda_arch = env::var("CUDA_ARCH").unwrap_or_else(|_| "75,86".to_string()); // sm_75 (RTX 20xx), sm_86 (RTX 30xx)
    
    println!("cargo:warning=Compiling CUDA kernels for architectures: sm_{}", cuda_arch);
    
    // Compile ethash kernel
    let mut build = cc::Build::new();
    build.cuda(true);
    build.flag("-std=c++14");
    build.flag("-O3");
    build.flag("--use_fast_math");
    build.flag("--expt-relaxed-constexpr");
    
    // Add architecture flags
    for arch in cuda_arch.split(',') {
        build.flag(&format!("-gencode"));
        build.flag(&format!("arch=compute_{},code=sm_{}", arch, arch));
    }
    
    // Add source files
    build.file("src/kernels/ethash.cu");
    build.file("src/cuda/hash_kernel.cu");
    build.file("src/cuda/mining_kernel.cu");
    
    // Compile
    build.compile("cuda_kernels");
    
    // Link CUDA runtime
    println!("cargo:rustc-link-lib=cudart");
    
    // Add CUDA library search paths
    if let Ok(cuda_path) = env::var("CUDA_PATH") {
        println!("cargo:rustc-link-search=native={}/lib64", cuda_path);
        println!("cargo:rustc-link-search=native={}/lib/x64", cuda_path);
    } else {
        // Default paths
        println!("cargo:rustc-link-search=native=/usr/local/cuda/lib64");
        println!("cargo:rustc-link-search=native=/usr/local/cuda/lib");
    }
    
    println!("cargo:warning=✅ CUDA kernels compiled successfully");
}
