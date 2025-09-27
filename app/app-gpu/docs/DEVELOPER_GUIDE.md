# 👨‍💻 OPUS-GPU v2.0 Developer Guide

## 📚 Table of Contents
1. [Getting Started](#getting-started)
2. [Architecture Overview](#architecture-overview)
3. [Development Setup](#development-setup)
4. [Plugin Development](#plugin-development)
5. [Testing](#testing)
6. [Debugging](#debugging)
7. [Performance Optimization](#performance-optimization)
8. [Best Practices](#best-practices)

---

## 🚀 Getting Started

### Prerequisites
- **Rust** >= 1.75.0
- **CUDA Toolkit** >= 12.0
- **Docker** (optional)
- **Git**

### Quick Setup
```bash
# Clone repository
git clone https://github.com/opus-gpu/v2.git
cd opus-gpu/app/app-gpu

# Install Rust (if not installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Build project
make build

# Run tests
make test

# Run application
make run
```

---

## 🏗️ Architecture Overview

### Core Components

```
┌─────────────────────────────────────┐
│         Core Runtime (Rust)         │
├─────────────────────────────────────┤
│  • Event Loop (Tokio)               │
│  • Plugin Manager                   │
│  • IPC Manager                      │
│  • Configuration                    │
│  • Error Handling                   │
│  • Logging                          │
└─────────────────────────────────────┘
           ↓            ↓
    ┌──────────┐  ┌──────────┐
    │  Plugin  │  │  Plugin  │
    │   GPU    │  │ Monitor  │
    └──────────┘  └──────────┘
```

### Module Organization

| Module | Path | Purpose |
|--------|------|---------|
| **Runtime** | `src/runtime/` | Main event loop và orchestration |
| **Plugin** | `src/plugin/` | Plugin management system |
| **IPC** | `src/ipc/` | Inter-process communication |
| **Config** | `src/config/` | Configuration management |
| **Error** | `src/error/` | Error handling và recovery |
| **Logging** | `src/logging.rs` | Structured logging |

---

## 💻 Development Setup

### 1. Environment Setup

```bash
# Set environment variables
export RUST_LOG=debug
export OPUS_CONFIG_PATH=./config.yaml
export OPUS_PLUGIN_DIR=./plugins
```

### 2. IDE Configuration

#### VS Code
```json
{
  "rust-analyzer.cargo.features": ["cuda"],
  "rust-analyzer.checkOnSave.command": "clippy",
  "editor.formatOnSave": true
}
```

#### IntelliJ IDEA
- Install Rust plugin
- Enable format on save
- Configure Cargo features: `cuda`

### 3. Build Configurations

```bash
# Debug build (fast compile, slow runtime)
cargo build

# Release build (slow compile, fast runtime)
cargo build --release

# Release with optimizations
cargo build --release --features cuda,optimize
```

---

## 🔌 Plugin Development

### Plugin Template

```rust
use opus_gpu_core::{Plugin, PluginTask, PluginOutput, PluginMetadata};
use async_trait::async_trait;

pub struct MyPlugin {
    // Plugin state
    config: MyConfig,
}

#[async_trait]
impl Plugin for MyPlugin {
    fn metadata(&self) -> PluginMetadata {
        PluginMetadata {
            name: "my-plugin".to_string(),
            version: "1.0.0".to_string(),
            author: "Your Name".to_string(),
            description: "Plugin description".to_string(),
            capabilities: vec!["compute".to_string()],
        }
    }
    
    async fn initialize(&mut self) -> anyhow::Result<()> {
        // Initialize resources
        Ok(())
    }
    
    async fn execute(&self, task: PluginTask) -> anyhow::Result<PluginOutput> {
        // Process task
        Ok(PluginOutput {
            task_id: task.id,
            status: TaskStatus::Success,
            result: vec![],
            metrics: HashMap::new(),
        })
    }
    
    async fn shutdown(&mut self) -> anyhow::Result<()> {
        // Cleanup resources
        Ok(())
    }
    
    fn health_check(&self) -> HealthStatus {
        HealthStatus {
            healthy: true,
            uptime_seconds: 0,
            tasks_completed: 0,
            tasks_failed: 0,
            memory_usage_mb: 0.0,
        }
    }
}

// Export plugin
opus_gpu_core::export_plugin!(MyPlugin);
```

### Building Plugin

```toml
# plugin/Cargo.toml
[package]
name = "my-plugin"
version = "1.0.0"

[lib]
crate-type = ["cdylib"]

[dependencies]
opus-gpu-core = { path = "../../core" }
async-trait = "0.1"
```

```bash
# Build plugin
cd plugins/my-plugin
cargo build --release

# Copy to plugin directory
cp target/release/libmy_plugin.so ../../plugins/
```

---

## 🧪 Testing

### Unit Tests

```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_functionality() {
        // Test implementation
        assert_eq!(2 + 2, 4);
    }
    
    #[tokio::test]
    async fn test_async_functionality() {
        // Async test
        let result = async_function().await;
        assert!(result.is_ok());
    }
}
```

### Integration Tests

```rust
// tests/integration_test.rs
use opus_gpu_core::Runtime;

#[tokio::test]
async fn test_full_workflow() {
    let config = Config::default();
    let mut runtime = Runtime::new(config).await.unwrap();
    
    // Test workflow
    runtime.shutdown().await.unwrap();
}
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test
cargo test test_name

# Run with output
cargo test -- --nocapture

# Run benchmarks
make bench

# Generate coverage report
make test-coverage
```

---

## 🐛 Debugging

### Logging Levels

```bash
# Set log level
export RUST_LOG=trace  # trace, debug, info, warn, error

# Filter by module
export RUST_LOG=opus_gpu_core::runtime=debug,opus_gpu_core::plugin=trace
```

### Debug Tools

```bash
# Run with backtrace
RUST_BACKTRACE=full cargo run

# Use GDB
rust-gdb target/debug/opus-gpu

# Use LLDB
rust-lldb target/debug/opus-gpu

# Memory profiling với Valgrind
valgrind --leak-check=full target/debug/opus-gpu
```

### Common Issues

| Issue | Solution |
|-------|----------|
| **Plugin not loading** | Check file permissions và path |
| **IPC timeout** | Increase shared memory size |
| **High memory usage** | Enable memory profiling |
| **Slow performance** | Use release build và profiling |

---

## ⚡ Performance Optimization

### Compilation Optimizations

```toml
# Cargo.toml
[profile.release]
opt-level = 3        # Maximum optimizations
lto = true          # Link-time optimization
codegen-units = 1   # Single codegen unit
strip = true        # Strip symbols
panic = "abort"     # Smaller binary
```

### Runtime Optimizations

1. **Memory Allocation**
```rust
// Use pre-allocated buffers
let mut buffer = Vec::with_capacity(1024 * 1024);

// Reuse allocations
buffer.clear();
buffer.extend_from_slice(&data);
```

2. **Lock-Free Data Structures**
```rust
use crossbeam::channel;
use parking_lot::RwLock;

// Prefer lock-free channels
let (sender, receiver) = channel::unbounded();
```

3. **Async Optimization**
```rust
// Batch operations
let futures: Vec<_> = tasks.iter()
    .map(|task| process_task(task))
    .collect();
    
let results = futures::future::join_all(futures).await;
```

### Profiling

```bash
# CPU profiling với perf
perf record --call-graph=dwarf target/release/opus-gpu
perf report

# Flamegraph
cargo install flamegraph
cargo flamegraph

# GPU profiling với Nsight
nsys profile --stats=true target/release/opus-gpu
```

---

## ✅ Best Practices

### Code Style

```rust
// Good: Clear naming
pub struct GpuTaskQueue {
    tasks: VecDeque<Task>,
    capacity: usize,
}

// Bad: Unclear naming
pub struct GTQ {
    t: VecDeque<T>,
    c: usize,
}
```

### Error Handling

```rust
// Good: Contextual errors
let config = Config::load()
    .context("Failed to load configuration")?;

// Bad: Generic errors
let config = Config::load()?;
```

### Documentation

```rust
/// Process GPU task với given priority.
/// 
/// # Arguments
/// * `task` - Task to process
/// * `priority` - Priority level (0-255)
/// 
/// # Returns
/// * `Ok(output)` - Processing result
/// * `Err(error)` - Processing error
/// 
/// # Example
/// ```
/// let output = process_task(task, 100)?;
/// ```
pub fn process_task(task: Task, priority: u8) -> Result<Output> {
    // Implementation
}
```

### Testing Strategy

1. **Unit tests** cho individual functions
2. **Integration tests** cho workflows
3. **Property tests** cho invariants
4. **Benchmarks** cho performance-critical code
5. **Fuzz tests** cho security-critical code

---

## 📖 Additional Resources

- [Rust Book](https://doc.rust-lang.org/book/)
- [Async Book](https://rust-lang.github.io/async-book/)
- [CUDA Programming Guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/)
- [Tokio Documentation](https://tokio.rs/)

## 🤝 Contributing

Please read [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines.

## 📄 License

See [LICENSE](../LICENSE) for details.

---

*Last updated: 2025-01-27*
