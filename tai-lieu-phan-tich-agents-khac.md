## 3. Phương án khuyến nghị – **Hybrid A′** (điều chỉnh từ Phương án A)

### 3.1 Cấu trúc thư mục đề xuất

```text
/app/mining_environment/gpu_optimization/
│
├── __init__.py
│
├── orchestrator/                      # Điều phối tổng quát
│   ├── __init__.py
│   ├── orchestrator.py
│   └── lifecycle_manager.py
│
├── monitoring/                        # Thu thập & dashboard
│   ├── __init__.py
│   ├── collectors/
│   │   ├── gpu_metrics.py
│   │   ├── process_metrics.py
│   │   └── system_metrics.py
│   ├── dashboard.py                   # gpu_monitoring_dashboard.py
│   └── exporters/
│       ├── prometheus.py
│       └── json_exporter.py
│
├── strategies/                        # Chiến lược tối ưu
│   ├── __init__.py
│   ├── base.py
│   ├── cloak.py                       # cloak_strategies.py
│   ├── aggressive.py
│   ├── balanced.py
│   └── selector.py
│
├── resource_control/                  # Quản lý tài nguyên GPU & tiến trình
│   ├── __init__.py
│   ├── gpu_controller.py
│   ├── power_manager.py
│   ├── thermal_control.py
│   └── pid_mapper.py
│
├── coordination/                      # Liên tiến trình / DAG
│   ├── __init__.py
│   ├── dag_synchronization.py
│   ├── cross_process_coordination.py
│   └── semaphore_pool.py
│
├── profiling/                         # Hiệu năng & báo cáo
│   ├── __init__.py
│   ├── performance_profiler.py
│   ├── cuda_tracer.py
│   └── report_generator.py
│
├── parallel_execution/                # Thực thi song song
│   ├── __init__.py
│   └── parallel_strategy_executor.py
│
├── config/
│   ├── __init__.py
│   ├── default.yaml
│   └── loader.py
│
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   ├── validators.py
│   └── exceptions.py
│
└── tests/ (unit, integration, fixtures)
```

### 3.2 Lý do chọn

1. **Đơn giản & rõ concern** – mỗi khả năng (`monitoring`, `strategies`, `profiling`, …) tách thư mục độc lập.  
2. **Đầy đủ chức năng** – tất cả file liệt kê đã có nơi chứa cụ thể.  
3. **Tuân thủ best practice Python** – package con với `__init__.py`, cấp sâu tối đa 2-3.  
4. **Mở rộng tương lai** – thêm package mới chỉ cần tạo thư mục ngang cấp.  
5. **Giảm script rời rạc** – mọi script di chuyển vào package tương ứng, chỉ để lại một CLI wrapper (nếu cần) ở `bin/` hoặc `scripts/`.

### 3.3 Ưu điểm / Nhược điểm

| Tiêu chí | Ưu điểm | Nhược điểm |
|----------|---------|-----------|
| Tính rõ ràng | Dễ tra cứu, concern tách bạch | Nhiều thư mục hơn phương án C |
| Bảo trì | Thêm-bớt module không ảnh hưởng package khác | Cần refactor import path |
| Khả năng mở rộng | Tự nhiên hỗ trợ plugin strategy mới | N/A |
| Phù hợp code hiện tại | 90 % – vì tên thư mục gần khớp, chỉ cần di chuyển | Refactor tương đối lớn cho `scripts/*.py` |

---

## 4. Kế hoạch migration

| Bước | Mô tả | Công cụ |
|------|-------|---------|
| 1 | Tạo thư mục mới `gpu_optimization/` theo tree A′ | `mkdir -p …` |
| 2 | Di chuyển file: <br>• `gpu_optimization_orchestrator.py` → `orchestrator/orchestrator.py` <br>• `gpu_resource_monitor.py` → `monitoring/collectors/process_metrics.py` <br>• `gpu_monitoring_dashboard.py` → `monitoring/dashboard.py` <br>• `parallel_strategy_executor.py` → `parallel_execution/parallel_strategy_executor.py` <br>• `performance_profiler.py` → `profiling/performance_profiler.py` <br>• `dag_synchronization.py` → `coordination/dag_synchronization.py` <br>• `cross_process_coordination.py` → `coordination/cross_process_coordination.py` <br>• `cloak_strategies.py` → `strategies/cloak.py` <br>• `resource_control.py` → `resource_control/gpu_controller.py` | `git mv` |
| 3 | Cập nhật import path trong toàn codebase (grep `from .*gpu_.* import`) | automate sed/ruff |
| 4 | Thêm `__init__.py` & re-export public API cho backwards-compat | code edit |
| 5 | Chạy test / lint để bảo đảm ổn định | pytest, ruff |
| 6 | Xoá thư mục `scripts/` cũ (hoặc giữ file CLI wrapper gọi vào package mới) | cleanup |
| 7 | Cập nhật tài liệu `README`, `docs/` & config path | doc update |

**Thời gian ước tính**: 1-2 ngày (bao gồm test & review).

---

### Kết luận

Phương án **Hybrid A′** đáp ứng tốt nhất các tiêu chí đơn giản − rõ ràng − đầy đủ − mở rộng. Việc migration chủ yếu là **di chuyển file & cập nhật import**, không thay đổi logic, nên rủi ro thấp và có thể thực hiện nhanh chóng.