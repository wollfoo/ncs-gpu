// Build script cho CLI - compile proto files

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Compile proto definitions (client side)
    tonic_build::configure()
        .build_server(false)
        .build_client(true)
        .out_dir("src/proto")
        .compile(
            &["../../proto/coordinator.proto"],
            &["../../proto"],
        )?;
    
    println!("cargo:rerun-if-changed=../../proto/coordinator.proto");
    
    Ok(())
}
