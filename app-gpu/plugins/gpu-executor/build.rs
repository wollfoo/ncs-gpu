//! Build script for GPU Executor plugin
//! Compiles CUDA kernels and links with Rust code

use std::env;
use std::path::PathBuf;

fn main() {
    // Only build CUDA kernels if feature is enabled
    if cfg!(feature = "cuda") {
        compile_cuda_kernels();
    }
    
    // Link CUDA libraries
    link_cuda_libraries();
}

fn compile_cuda_kernels() {
    let cuda_path = env::var("CUDA_PATH")
        .unwrap_or_else(|_| "/usr/local/cuda".to_string());
    
    let out_dir = env::var("OUT_DIR").unwrap();
    let kernel_path = "src/cuda/kernels.cu";
    let output_path = PathBuf::from(&out_dir).join("kernels.o");
    
    println!("cargo:rerun-if-changed={}", kernel_path);
    
    // Use cuda-builder if available, otherwise use cc
    #[cfg(feature = "cuda-builder")]
    {
        use cuda_builder::CudaBuilder;
        
        CudaBuilder::new(kernel_path)
            .out_dir(&out_dir)
            .build()
            .expect("Failed to build CUDA kernels");
    }
    
    #[cfg(not(feature = "cuda-builder"))]
    {
        // Fallback to manual nvcc compilation
        cc::Build::new()
            .cuda(true)
            .cudart("static")
            .file(kernel_path)
            .flag("-gencode")
            .flag("arch=compute_80,code=sm_80") // Ampere
            .flag("-gencode")
            .flag("arch=compute_86,code=sm_86") // Ampere
            .flag("-gencode")
            .flag("arch=compute_89,code=sm_89") // Ada Lovelace
            .flag("-O3")
            .flag("--use_fast_math")
            .flag("-Xcompiler")
            .flag("-fPIC")
            .include(&format!("{}/include", cuda_path))
            .compile("cuda_kernels");
    }
    
    println!("cargo:rustc-link-search=native={}", out_dir);
    println!("cargo:rustc-link-lib=static=cuda_kernels");
}

fn link_cuda_libraries() {
    let cuda_path = env::var("CUDA_PATH")
        .unwrap_or_else(|_| "/usr/local/cuda".to_string());
    
    // Link directories
    println!("cargo:rustc-link-search=native={}/lib64", cuda_path);
    println!("cargo:rustc-link-search=native={}/lib", cuda_path);
    
    // Link CUDA libraries
    println!("cargo:rustc-link-lib=cudart");
    println!("cargo:rustc-link-lib=cuda");
    println!("cargo:rustc-link-lib=nvml");
    
    // Optional libraries
    if cfg!(feature = "profiling") {
        println!("cargo:rustc-link-lib=nvToolsExt");
        println!("cargo:rustc-link-lib=cupti");
    }
}
