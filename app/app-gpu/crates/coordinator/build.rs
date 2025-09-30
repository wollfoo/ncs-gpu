// Build script cho coordinator - compile proto files

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Compile proto definitions
    tonic_build::configure()
        .build_server(true)
        .build_client(false)
        .out_dir("src/proto")
        .compile(
            &["../../proto/coordinator.proto"],
            &["../../proto"],
        )?;
    
    println!("cargo:rerun-if-changed=../../proto/coordinator.proto");
    
    Ok(())
}
