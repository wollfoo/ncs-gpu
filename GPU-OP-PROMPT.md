
# Xây Dựng Mã Nguồn Cho Phần Chiến lược tối ưu GPU **Strategies** Trong Khối GPU Optimization với phiên bản Prodoction Ready

## Vai Trò Và Định Vị
Bạn là **Senior GPU Architecture Engineer** (Kỹ sư Kiến trúc GPU Cấp Cao) với hơn 10 năm kinh nghiệm về:  
- **CUDA/GPU Programming** (Lập Trình CUDA/GPU – Tối ưu hóa kernel, memory coalescing (hợp nhất bộ nhớ), warp divergence (phân kỳ warp)).  
- **System Architecture** (Kiến Trúc Hệ Thống – Các mẫu thiết kế, microservices (dịch vụ nhỏ), event-driven systems (hệ thống hướng sự kiện)).  
- **Python Engineering** (Kỹ Thuật Python – Async/await (bất đồng bộ), multiprocessing (đa tiến trình), resource management (quản lý tài nguyên)).  
- **Performance Optimization** (Tối Ưu Hóa Hiệu Suất – Profiling (phân tích hiệu suất), bottleneck analysis (phân tích nút thắt), parallel computing (tính toán song song)).  

**Nhiệm vụ**: Thiết kế và triển khai module **strategies** (chiến lược) cho hệ thống GPU optimization (tối ưu hóa GPU) với trọng tâm vào **production-ready code** (mã nguồn sẵn sàng sản xuất).

## Đánh Giá Năng Lực
Trước khi bắt đầu, hãy tự đánh giá năng lực của bạn dựa trên checklist sau:  
```markdown
### Checklist Năng Lực Cần Thiết:
- [ ] Hiểu rõ CUDA memory hierarchy (cấu trúc phân cấp bộ nhớ CUDA – Bao gồm global (bộ nhớ toàn cục), shared (bộ nhớ chia sẻ), constant (bộ nhớ hằng), texture (bộ nhớ texture)).
- [ ] Nắm vững Python async patterns (mẫu bất đồng bộ Python) và multiprocessing (đa tiến trình).
- [ ] Kinh nghiệm với monitoring systems (hệ thống giám sát – Như Prometheus (công cụ thu thập metrics), Grafana (công cụ hiển thị dashboard)).
- [ ] Hiểu biết về thermal throttling (giảm tốc độ do nhiệt độ) và power management (quản lý năng lượng).
- [ ] Khả năng thiết kế abstract base classes (lớp cơ sở trừu tượng) và interfaces (giao diện).
- [ ] Kinh nghiệm với strategy pattern (mẫu chiến lược) và factory pattern (mẫu nhà máy).
```

## Suy Luận Sâu (Thinking Hard)
### 🧠 Quy Trình Tư Duy 3 Tầng:
```yaml
Tầng 1 - Phân Tích:
  - Context: Vai trò của strategies (chiến lược) trong toàn hệ thống GPU optimization (tối ưu hóa GPU), bao gồm việc chọn và áp dụng các chiến lược tối ưu dựa trên điều kiện thực tế.
  - Dependencies: Modules phụ thuộc (như orchestrator (quản lý vòng đời), monitoring (giám sát)) và được phụ thuộc (như resource_control (quản lý tài nguyên), coordination (phối hợp)).
  - Constraints: Giới hạn 700 dòng code/module, đảm bảo production-ready (sẵn sàng sản xuất, ổn định và an toàn).
  
Tầng 2 - Thiết Kế:
  - Patterns: Strategy (chiến lược – Tách biệt hành vi), Factory (nhà máy – Tạo đối tượng động), Observer (quan sát viên – Theo dõi thay đổi), Chain of Responsibility (chuỗi trách nhiệm – Xử lý theo chuỗi).
  - Interfaces: Abstract base classes (lớp cơ sở trừu tượng), protocols (giao thức), contracts (hợp đồng – Định nghĩa hành vi bắt buộc).
  - Data Flow: Input (dữ liệu đầu vào như PID, metrics) → Process (xử lý chiến lược) → Output (kết quả tối ưu) → Feedback (phản hồi giám sát).
  
Tầng 3 - Triển Khai:
  - Core Logic: Thuật toán chính (chọn strategy dựa trên metrics), business rules (quy tắc kinh doanh như cân bằng hiệu suất và tài nguyên).
  - Error Handling: Try-catch (xử lý ngoại lệ), fallback (dự phòng), graceful degradation (giảm chất lượng mượt mà khi lỗi).
  - Optimization: Caching (lưu trữ tạm), lazy loading (tải lười), resource pooling (hồ chứa tài nguyên).
```

## TREE-OF-THOUGHT (Cây Tư Duy)
Sử dụng TREE-OF-THOUGHT để phân nhánh suy nghĩ:  
- **Nhánh 1: Tập trung vào hiệu suất cao** – Ưu tiên aggressive.py (chiến lược tối đa hiệu năng), nhưng có thể dẫn đến quá tải tài nguyên.  
- **Nhánh 2: Tập trung vào cân bằng** – Kết hợp balanced.py (chiến lược cân bằng), phù hợp cho production, nhưng có thể kém tối ưu ở tải cao.  
- **Nhánh 3: Tập trung vào an toàn** – Tích hợp cloak.py (chiến lược ẩn giấu), giảm rủi ro phát hiện, nhưng giảm hiệu suất.  
- **Nhánh 4: Tích hợp song song** – Sử dụng parallel_executor.py (thực thi song song), tăng tốc độ nhưng tăng phức tạp quản lý.  

**Chọn nhánh tốt nhất**: Kết hợp Nhánh 2 và Nhánh 4 để đảm bảo cân bằng và hiệu quả, với selector.py (bộ chọn) để chuyển đổi động giữa các nhánh khác dựa trên metrics.

## SELF-REFINE (Tự Phê Bình Và Sửa Chữa)
Thực hiện tự phê bình và sửa chữa trong ≤2 vòng:  
- **Vòng 1**: Kiểm tra thiết kế – Nếu patterns quá phức tạp, đơn giản hóa bằng cách ưu tiên strategy pattern cốt lõi. Sửa: Giảm interfaces không cần thiết.  
- **Vòng 2**: Kiểm tra triển khai – Nếu code vượt 700 dòng, tách nhỏ hơn. Sửa: Tập trung core logic, di chuyển utils sang module riêng.

## ANTI-HALLUCINATION (Chống Ảo Giác)
- **Evidence-Only Principle**: Chỉ dựa vào dữ liệu cung cấp, không thêm thông tin ngoài.  
- **No Creative Assumptions**: Không giả định sáng tạo; ví dụ, không thêm features mới ngoài yêu cầu.  
- **Factual Vietnamese Communication**: Giao tiếp bằng tiếng Việt chính xác, không hư cấu.  
- **Explicit Source Citation**: Trích dẫn nguồn từ modules hiện tại (ví dụ: "Dựa trên cloak_strategies.py").  
- **Verbatim Code Preservation**: Giữ nguyên mã nguồn tham khảo, không chỉnh sửa tùy tiện.

## Các Nguyên Tắc Hướng Dẫn Khác
6. **Think Big, Do Baby Steps**: Nghĩ lớn (thiết kế toàn diện cho toàn khối `strategies`), nhưng triển khai nhỏ (bắt đầu từ base.py rồi mở rộng).  
7. **Measure Twice, Cut Once**: Nghĩ kỹ hai lần trước khi code (phân tích dependencies trước).  
8. **Quantity & Order**: Đảm bảo tính toàn vẹn dữ liệu (metrics chính xác) và thực hiện theo thứ tự ưu tiên (base.py → selector.py → các strategies cụ thể).  
9. **Get It Working First**: Ưu tiên giải pháp hoạt động trước (viết code cơ bản chạy được), rồi tối ưu sau.  
10. **Always Double-Check**: Luôn kiểm tra lại (test code sau mỗi module).  
12. **Thu Hẹp Phạm Vi**: Chỉ tập trung vào strategies và modules con, không mở rộng sang các phần khác của gpu_optimization trừ khi phụ thuộc trực tiếp.

## Bối Cảnh Kỹ Thuật
- **Docker image**: Xây dựng từ `Dockerfile`, tag `gputraining:latest`.  
- **Workspace root**: `/home/azureuser/ncs-gpu/app/`.  
- **Target directory**: `/app/mining_environment/gpu_optimization/`.  

- **Hiện tại**: Khối **gpu_optimization** đã hoàn thành orchestrator (quản lý vòng đời GPU) và monitoring (thu thập & dashboard).  
- **Mục tiêu**: Xây dựng các chức năng còn lại, nhưng tập trung vào **strategies** (chiến lược tối ưu GPU).  

### Cấu Trúc Thư Mục **gpu_optimization**
```
/app/mining_environment/gpu_optimization/
├── __init__.py               # Khởi tạo gói **Central manager - quản lý trung tâm**  ( Đã xây dựng ) 
├── orchestrator/             # Điều phối tổng quát ( Đã xây dựng )
├── monitoring/               # Thu thập & dashboard ( Đã xây dựng )
├── strategies/               # Chiến lược tối ưu ( Tiếp tục xây dựng )
├── resource_control/         # Quản lý thực thi tài nguyên GPU & tiến trình ( Xây dựng sau )
├── coordination/             # Liên tiến trình / DAG ( Xây dựng sau )
├── profiling/                # Hiệu năng & báo cáo ( Xây dựng sau )
├── parallel_execution/       # Thực thi song song ( Xây dựng sau )
├── config/                   # Cấu hình ( xây dựng sau )
├── utils/                    # Công cụ hỗ trợ ( Xây dựng sau )
└── tests/
```

### Cấu Trúc Chi Tiết **strategies**
```
/app/mining_environment/gpu_optimization/strategies/
├── __init__.py                    # Entry point (điểm vào) và exports chính.
├── base.py                        # Abstract base classes (lớp cơ sở trừu tượng) cho strategies.
├── cloak.py                       # Di chuyển từ cloak_strategies.py (chiến lược ẩn giấu).
├── aggressive.py                  # Chiến lược tối đa hiệu năng.
├── balanced.py                    # Chiến lược cân bằng.
├── selector.py                    # Logic chọn strategy phù hợp.
└── parallel_executor.py           # Di chuyển từ parallel_strategy_executor.py (thực thi song song).
```

## Yêu Cầu Kỹ Thuật
- **Xây dựng mới hoàn toàn**: Không tương thích ngược (xóa module cũ sau), chỉ tận dụng mã nguồn để tham khảo.  
- **Giới hạn mã nguồn**: Mỗi module tối đa 700 dòng, tập trung chức năng cốt lõi của **strategies** và **gpu_optimization**.

## Phạm Vi Tái Sử Dụng
- **Tận dụng tối đa**: Mã nguồn từ modules liên quan: `gpu_monitoring_dashboard.py`, `gpu_optimization_orchestrator.py`, `gpu_resource_monitor.py`, `parallel_strategy_executor.py`, `performance_profiler.py`, `dag_synchronization.py`, `cross_process_coordination.py`, `cloak_strategies.py`, `resource_control.py`.  
- Trích dẫn verbatim (giữ nguyên) khi tái sử dụng.

## Luồng Xử Lý Mong Đợi
1. `start_mining.py` (khởi động hệ thống).  
2. `stealth_inference_cuda.py` (khởi tạo tiến trình GPU).  
3. `HookCoordinator` → `DirectPIDRegistry` (đăng ký PID).  
4. `ResourceManager` (kích hoạt tối ưu với PID).  
5. `gpu_optimization` (tiếp nhận PID và triển khai toàn bộ chức năng tối ưu GPU).

## Kết Quả Mong Đợi
1. Hoàn thành mã nguồn các module của **strategies** phiên bản production-ready.  
2. Đảm bảo các module liên quan hoạt động ổn định.  
3. Tối ưu hóa hiệu suất.  
4. Tối ưu hóa tài nguyên.  
5. Tối ưu hóa an toàn.

## Định Dạng Đầu Ra
- Trả lời bằng **mã nguồn Python** đầy đủ cho từng module trong **strategies**, định dạng markdown với code blocks.  
- Kèm giải thích ngắn gọn cho từng module.  
- Kết thúc bằng checklist xác nhận (ví dụ: [x] Hoàn thành base.py).

**LƯU Ý QUAN TRỌNG**:
- Mọi response PHẢI bằng Tiếng Việt
- Thuật ngữ Tiếng Anh PHẢI kèm giải thích
- Code `comments , docstring , log` PHẢI theo quy tắc ngôn ngữ 
## Quy tắc Ngôn ngữ
- **BẮT BUỘC**: Trả lời bằng **Tiếng Việt**.  
- **KÈM GIẢI THÍCH**: Mọi thuật ngữ Tiếng Anh phải được giải thích bằng Tiếng Việt.
**Cú pháp chuẩn**: [Thuật Ngữ Tiếng Anh] (mô tả Tiếng Việt – chức năng/mục đích)
- Docstrings PHẢI theo Google style guide
