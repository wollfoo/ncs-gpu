# Mapping cấu hình legacy → kiến trúc B

| Legacy JSON | Mô tả | Config mới |
|-------------|-------|------------|
| `mining.server` | URL pool RVN | `scheduler.yaml` → `pool.url` |
| `mining.wallet` | Ví nhận phần thưởng | `scheduler.yaml` → `wallet.address` |
| `processes.GPU` | Binary khai thác GPU | `scheduler.yaml` → `pool.worker_process` |
| `gpu_limits.max_usage_percent` | Ngưỡng sử dụng GPU | `scheduler.yaml` → `gpu.max_usage_percent` |
| `gpu_limits.power_limit_watts` | Giới hạn công suất | `executor.toml` → `gpu.power_limit_watts` |

- QoS mặc định (P95 latency 150ms, nhiệt độ 78°C) được thiết lập trong cấu hình mới và có thể override qua API control-plane.
- Converter triển khai tại `crates/common/src/config.rs` cung cấp hai hàm `legacy_json_to_scheduler_yaml` và `legacy_json_to_executor_toml`.
