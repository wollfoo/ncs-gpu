# GPU Mining System v2.0

**[Production-Ready GPU Mining System]** (hệ thống khai thác GPU sẵn sàng sản xuất – phiên bản thương mại hoàn chỉnh)

## Kiến trúc

Hệ thống được thiết kế theo **[Microservices Architecture]** (kiến trúc vi dịch vụ – các thành phần độc lập) với:
- **[API Gateway]** (cổng API – điểm vào duy nhất) sử dụng Go/gRPC
- **[GPU Workers]** (công nhân GPU – tiến trình xử lý) viết bằng Rust
- **[Orchestrator]** (bộ điều phối – quản lý tác vụ) với Go
- **[Monitoring]** (giám sát – theo dõi hệ thống) qua Prometheus/Grafana

## Cấu trúc thư mục

```
app-gpu/
├── cmd/                  # Entry points cho các services
│   ├── api/             # API Gateway service
│   ├── orchestrator/    # Orchestrator service  
│   └── worker/          # GPU Worker service
├── internal/            # Private packages
│   ├── gpu/            # GPU management
│   ├── mining/         # Mining algorithms
│   └── metrics/        # Telemetry
├── pkg/                # Public packages
│   ├── protocol/       # gRPC definitions
│   └── utils/          # Shared utilities
├── configs/            # Configuration files
├── deployments/        # Docker & K8s manifests
└── tests/             # Test suites
```

## Yêu cầu hệ thống

- **[NVIDIA GPU]** với CUDA 12.0+
- **[Docker]** 24.0+ với nvidia-container-toolkit
- **[Go]** 1.22+ để build orchestrator
- **[Rust]** 1.75+ để build workers

## Cài đặt nhanh

```bash
# Build toàn bộ hệ thống
make build

# Chạy với Docker Compose
docker-compose up -d

# Kiểm tra trạng thái
make status
```

## Wallet Configuration

Tạo file `.env` với thông tin wallet RVN:
```env
RVN_WALLET_ADDRESS=your_wallet_address
POOL_URL=stratum+tcp://pool.example.com:3333
WORKER_NAME=gpu-worker-01
```

## Performance Tuning

Hệ thống hỗ trợ các chế độ tối ưu:
- **[Low Power]** (công suất thấp – tiết kiệm điện): 70% GPU usage
- **[Balanced]** (cân bằng – hiệu năng ổn định): 85% GPU usage  
- **[Performance]** (hiệu năng – tốc độ tối đa): 95% GPU usage

## Security

- **[Non-root containers]** (container không root – bảo mật cao)
- **[Encrypted communication]** (giao tiếp mã hoá – bảo vệ dữ liệu)
- **[Rate limiting]** (giới hạn tốc độ – chống DDoS)
- **[Audit logging]** (ghi log kiểm toán – theo dõi hoạt động)

## License

Proprietary - All rights reserved
