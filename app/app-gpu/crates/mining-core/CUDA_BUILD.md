# CUDA Build System Documentation

## Overview (Tổng quan)

**CUDA Build System** cho GPU Mining System - Hệ thống biên dịch CUDA kernels với automatic detection và graceful degradation.

## Architecture (Kiến trúc)

```
mining-core/
├── build.rs              # CUDA build configuration
├── Cargo.toml            # Dependencies với CUDA feature flag
└── src/
    └── cuda/
        ├── mining_kernel.cu    # Mining operations kernel
        └── hash_kernel.cu      # Hash functions kernel
```

## CUDA Toolkit Requirements (Yêu cầu CUDA Toolkit)

### Minimum Requirements
- **CUDA Version**: 11.0 or higher (recommended: 11.8+, 12.0+)
- **GPU Architecture**: Compute Capability 7.5+ (sm_75)
  - RTX 20xx series (Turing)
  - RTX 30xx series (Ampere)
  - RTX 40xx series (Ada Lovelace)
  - A100, H100 (data center GPUs)

### Installation Paths

Build system automatically detects CUDA in these locations:

1. **Environment Variable**: `CUDA_PATH`
2. **Standard Paths**:
   - `/usr/local/cuda` (default symlink)
   - `/usr/local/cuda-12.0`
   - `/usr/local/cuda-11.8`
   - `/usr/local/cuda-11.0`
   - `/opt/cuda`
   - `/usr/cuda`
3. **PATH Detection**: `which nvcc`

### Manual Installation

**Ubuntu/Debian**:
```bash
# Add NVIDIA CUDA repository
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb
sudo dpkg -i cuda-keyring_1.0-1_all.deb
sudo apt-get update

# Install CUDA toolkit
sudo apt-get install cuda-toolkit-12-0

# Set environment variable (add to ~/.bashrc)
export CUDA_PATH=/usr/local/cuda-12.0
export PATH=$CUDA_PATH/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_PATH/lib64:$LD_LIBRARY_PATH
```

**Manual Download**:
1. Visit: https://developer.nvidia.com/cuda-downloads
2. Select your platform
3. Follow installation instructions
4. Verify: `nvcc --version`

## Build Configuration (Cấu hình Build)

### CUDA Compiler Flags

Build system uses these `nvcc` flags:

```bash
--device-c                    # Compile device code only
-arch=sm_75                   # Target compute capability 7.5+
-O3                          # Maximum optimization
--compiler-options -fPIC      # Position-independent code
--default-stream per-thread   # Per-thread default stream
-Xptxas -v                   # Verbose PTX compilation
--use_fast_math              # Fast math operations
```

### Compute Capability Selection

Default: `sm_75` (RTX 20xx/30xx)

To change target architecture, edit `build.rs`:

```rust
compute_capability: "sm_86".to_string(), // RTX 30xx (Ampere)
compute_capability: "sm_89".to_string(), // RTX 40xx (Ada)
```

### Library Linking

Build system automatically links these CUDA libraries:

- `cudart` - CUDA Runtime API
- `cuda` - CUDA Driver API
- `nvrtc` - CUDA Runtime Compilation

## Build Process (Quy trình Build)

### 1. CUDA Detection Phase

```rust
cargo build
```

Output:
```
warning: CUDA toolkit detected successfully
warning: Found CUDA toolkit at: "/usr/local/cuda"
warning: CUDA version: Cuda compilation tools, release 12.0
```

### 2. Kernel Compilation Phase

Build system compiles:
- `src/cuda/mining_kernel.cu`
- `src/cuda/hash_kernel.cu`

### 3. Linking Phase

Links compiled CUDA kernels with Rust code.

### 4. Feature Flag Activation

If successful, enables `cuda` feature:
```rust
#[cfg(feature = "cuda")]
```

## Graceful Degradation (Giảm cấp)

### CPU-Only Mode

If CUDA toolkit not found:

```
warning: CUDA toolkit not detected: CUDA toolkit not found
warning: Building without CUDA support (CPU-only mode)
warning: To enable CUDA: Install CUDA toolkit 11.0+ or set CUDA_PATH
warning: Build completed
```

Build **succeeds** but runs in CPU-only mode using:
- Rayon for CPU parallelization
- Native Rust hash implementations

### Partial Build Success

If CUDA detected but kernel compilation fails:
- Build continues without CUDA support
- Logs detailed error messages
- Falls back to CPU implementation

## Verification (Xác minh)

### Check CUDA Feature

```bash
# Check if CUDA feature is enabled
cargo build -vv 2>&1 | grep "rustc-cfg=feature=\"cuda\""
```

### Test CUDA Availability

```rust
#[cfg(feature = "cuda")]
fn has_cuda() -> bool {
    true
}

#[cfg(not(feature = "cuda"))]
fn has_cuda() -> bool {
    false
}

println!("CUDA support: {}", has_cuda());
```

### Runtime Detection

```rust
use mining_core::gpu::detect_cuda_devices();

if let Ok(devices) = detect_cuda_devices() {
    println!("Found {} CUDA devices", devices.len());
} else {
    println!("No CUDA devices available - using CPU");
}
```

## Troubleshooting (Khắc phục sự cố)

### Issue: CUDA Not Detected

**Symptoms**:
```
warning: CUDA toolkit not detected
```

**Solutions**:
1. Install CUDA toolkit 11.0+
2. Set `CUDA_PATH` environment variable:
   ```bash
   export CUDA_PATH=/usr/local/cuda
   ```
3. Add nvcc to PATH:
   ```bash
   export PATH=/usr/local/cuda/bin:$PATH
   ```

### Issue: Version Mismatch

**Symptoms**:
```
warning: CUDA version 11.0+ required
```

**Solution**: Upgrade CUDA toolkit to version 11.0 or higher.

### Issue: Compilation Errors

**Symptoms**:
```
error: CUDA compilation failed
```

**Solutions**:
1. Check CUDA installation: `nvcc --version`
2. Verify GPU compute capability: `nvidia-smi`
3. Check build.rs logs for detailed error messages
4. Ensure C++ compiler is installed: `g++ --version`

### Issue: Linking Errors

**Symptoms**:
```
error: linking with `cc` failed
```

**Solutions**:
1. Check library paths:
   ```bash
   ls /usr/local/cuda/lib64/libcudart.so
   ```
2. Add to `LD_LIBRARY_PATH`:
   ```bash
   export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
   ```

## Performance Optimization (Tối ưu hóa hiệu năng)

### Build-time Optimizations

- **Parallel Compilation**: `cc` crate with `parallel` feature
- **Release Profile**: LTO, optimization level 3
- **Fast Math**: CUDA `--use_fast_math` flag

### Runtime Optimizations

- **Per-thread Streams**: Avoid default stream synchronization
- **Async Operations**: Use CUDA streams for parallel execution
- **Memory Pooling**: Reuse GPU memory allocations

## Development Workflow (Quy trình phát triển)

### Adding New CUDA Kernels

1. Create `.cu` file in `src/cuda/`
2. Add to `cuda_sources` in `build.rs`:
   ```rust
   let cuda_sources = vec![
       "mining_kernel.cu",
       "hash_kernel.cu",
       "your_kernel.cu",  // Add here
   ];
   ```
3. Rebuild: `cargo clean && cargo build`

### Testing CUDA Code

```rust
#[cfg(all(test, feature = "cuda"))]
mod cuda_tests {
    #[test]
    fn test_cuda_kernel() {
        // Your CUDA tests here
    }
}
```

### Debugging CUDA Kernels

1. Enable verbose compilation:
   ```bash
   RUST_LOG=debug cargo build
   ```

2. Use `cuda-gdb` for kernel debugging:
   ```bash
   cuda-gdb target/debug/mining-core
   ```

3. Check kernel launch errors:
   ```rust
   unsafe {
       launch_kernel(...);
       cudaDeviceSynchronize();
       let err = cudaGetLastError();
       assert_eq!(err, cudaSuccess);
   }
   ```

## CI/CD Integration (Tích hợp CI/CD)

### GitHub Actions Example

```yaml
- name: Install CUDA Toolkit
  uses: Jimver/cuda-toolkit@v0.2.11
  with:
    cuda: '12.0.0'

- name: Build with CUDA
  run: |
    export CUDA_PATH=/usr/local/cuda
    cargo build --release --features cuda
```

### Docker Build

```dockerfile
FROM nvidia/cuda:12.0.0-devel-ubuntu22.04

RUN apt-get update && apt-get install -y \
    curl \
    build-essential

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

WORKDIR /app
COPY . .

RUN cargo build --release
```

## References (Tài liệu tham khảo)

- [CUDA Toolkit Documentation](https://docs.nvidia.com/cuda/)
- [CUDA C Programming Guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/)
- [NVCC Compiler Options](https://docs.nvidia.com/cuda/cuda-compiler-driver-nvcc/)
- [Rust FFI Guide](https://doc.rust-lang.org/nomicon/ffi.html)

## License

MIT License - See project root LICENSE file.
