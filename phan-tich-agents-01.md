

### Tác động và bước tiếp
- Sau khi chuẩn hóa:  
  - Không còn WARNING “Unknown metric type”.  
  - `Periodic stats update` hiển thị số nhóm metric > 0.  
  - File JSON export có thống kê và mẫu thô cho 8 nhóm chuẩn.  
- Giám sát: theo dõi `/app/mining_environment/logs/unified.log` và `/tmp/gpu_metrics/metrics_*.json`.

- Nếu bạn muốn, tôi sẽ soạn sẵn các “edits” tối thiểu vào `gpu_optimization_orchestrator.py` (điểm ghi metric) và `cloak_strategies.py` (nơi Adapter nhỏ trước `add_metric`) để bạn duyệt.

- Tất cả đề xuất trên không tạo module mới và không đổi cấu trúc thư mục.

