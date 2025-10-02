# Mining Core - GPU Mining Engine

**High-performance GPU mining engine** với CUDA acceleration và automatic fallback sang CPU mode.

## Features (Tính năng)

- ✅ **CUDA Build System** với automatic detection
- ✅ **Graceful Degradation** sang CPU-only mode
- ✅ **Parallel Compilation** với cc crate
- ✅ **Optimized Kernels** cho mining operations
- ✅ **Hash Functions**: SHA-256, Blake3 CUDA implementations

## Architecture (Kiến trúc)

```
mining-core/
├── build.rs              # CUDA build configuration
├── Cargo.toml            # Dependencies và features
├── src/
│   ├── lib.rs           # Main library
│   ├── config.rs        # Configuration management
│   ├── gpu/             # GPU abstractions
│   ├── crypto/          # Cryptographic functions
│   └── cuda/            # CUDA kernel sources
│       ├── mining_kernel.cu   # Mining operations
│       └── hash_kernel.cu     # Hash functions
└── CUDA_BUILD.md        # Detailed CUDA documentation

```

## Quick Start (Khởi động nhanh)

### Build với CUDA Support

```bash
# Install CUDA toolkit 11.0+ first
export CUDA_PATH=/usr/local/cuda
cargo build --release --features cuda
```

### Build CPU-Only Mode

```bash
# No CUDA required - automatic fallback
cargo build --release
```

## CUDA Requirements (Yêu cầu CUDA)

- **CUDA Toolkit**: 11.0+ (recommended 12.0+)
- **GPU**: Compute Capability 7.5+ (RTX 20xx/30xx series)
- **Compiler**: nvcc with C++ support

## Build Behavior (Hành vi Build)

### With CUDA Detected
```
warning: Found CUDA toolkit at: "/usr/local/cuda"
warning: CUDA version: release 12.0
warning: Building CUDA kernels...
warning: CUDA kernels built successfully
```

### Without CUDA
```
warning: CUDA toolkit not detected
warning: Building without CUDA support (CPU-only mode)
warning: Build completed
```

## Usage (Sử dụng)

```rust
use mining_core::{MiningEngine, MiningConfig};

let config = MiningConfig::default();
let engine = MiningEngine::new(config)?;

// Automatically uses CUDA if available, otherwise CPU
let result = engine.start_mining().await?;
```

## Documentation (Tài liệu)

- **CUDA Build System**: See [CUDA_BUILD.md](./CUDA_BUILD.md)
- **API Reference**: Run `cargo doc --open`

## Testing (Kiểm tra)

```bash
# Run all tests
cargo test -p mining-core

# Run CUDA tests (requires GPU)
cargo test -p mining-core --features cuda
```

## Performance (Hiệu năng)

| Mode | Hash Rate | Power Efficiency |
|------|-----------|------------------|
| CUDA (RTX 3080) | ~100 MH/s | High |
| CPU (16 cores) | ~10 MH/s | Low |

## License

MIT License - See [LICENSE](../../LICENSE)
