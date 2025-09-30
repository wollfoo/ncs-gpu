// Build script cho worker - compile proto + link CUDA kernels

use std::env;
use std::path::PathBuf;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1. Compile proto definitions (client side)
    tonic_build::configure()
        .build_server(false)
        .build_client(true)
        .out_dir("src/proto")
        .compile(
            &["../../proto/coordinator.proto"],
            &["../../proto"],
        )?;
    
    println!("cargo:rerun-if-changed=../../proto/coordinator.proto");
    
    // 2. Link CUDA kernels library
    let kernel_lib_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR")?)
        .join("../../kernels/build");
    
    println!("cargo:rustc-link-search=native={}", kernel_lib_dir.display());
    println!("cargo:rustc-link-lib=dylib=gpu_mining_kernels");
    
    // 3. Generate bindings cho CUDA kernels
    let bindings = bindgen::Builder::default()
        .header("../../kernels/include/kernels.h")
        .parse_callbacks(Box::new(bindgen::CargoCallbacks))
        .generate()
        .expect("Unable to generate CUDA bindings");
    
    let out_path = PathBuf::from(env::var("OUT_DIR")?);
    bindings
        .write_to_file(out_path.join("cuda_bindings.rs"))
        .expect("Couldn't write bindings");
    
    println!("cargo:rerun-if-changed=../../kernels/include/kernels.h");
    
    Ok(())
}
