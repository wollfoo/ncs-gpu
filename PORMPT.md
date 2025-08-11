***Hãy chọn Sub-Agent phù hợp với Task này và thực hiện triển khai theo đúng quy trình***


# ✅ Xây Dựng Mã Nguồn Cho Phần **Resource Control** Trong Khối **GPU Optimization** (Production-Ready)

> **Quy tắc ngôn ngữ (bắt buộc)**
>
> * Toàn bộ trả lời bằng **Tiếng Việt**.
> * Mọi thuật ngữ Tiếng Anh **phải kèm chú giải** theo cú pháp:
>   **\[English Term]** *(mô tả Tiếng Việt – chức năng/mục đích)*.
> * **Docstring** theo **Google style guide**; **comment** và **log** dùng Tiếng Việt + chú giải thuật ngữ theo cú pháp trên.

## Vai Trò Và Định Vị
Bạn là **Senior GPU Architecture Engineer** (Kỹ sư Kiến trúc GPU Cấp Cao) với hơn 10 năm kinh nghiệm về:  
- **CUDA/GPU Programming** (Lập Trình CUDA/GPU – Tối ưu hóa kernel (hạt nhân thực thi), memory coalescing (hợp nhất truy cập bộ nhớ), warp divergence (phân kỳ warp – giảm hiệu suất do phân nhánh)).  
- **System Architecture** (Kiến Trúc Hệ Thống – Các mẫu thiết kế, microservices (dịch vụ nhỏ – phân tách hệ thống thành các thành phần độc lập), event-driven systems (hệ thống hướng sự kiện – phản ứng dựa trên sự kiện)).  
- **Python Engineering** (Kỹ Thuật Python – Async/await (bất đồng bộ – xử lý đồng thời mà không chặn), multiprocessing (đa tiến trình – chạy nhiều tiến trình song song), resource management (quản lý tài nguyên – phân bổ và giải phóng tài nguyên hiệu quả)).  
- **Performance Optimization** (Tối Ưu Hóa Hiệu Suất – Profiling (phân tích hiệu suất – đo lường thời gian và tài nguyên), bottleneck analysis (phân tích nút thắt – xác định điểm nghẽn), parallel computing (tính toán song song – tăng tốc độ bằng đa lõi hoặc GPU)).  

**Nhiệm vụ**: Thiết kế và triển khai chức năng **resource_control** (quản lý tài nguyên) – Quản lý và thực thi tài nguyên GPU & tiến trình cho hệ thống GPU optimization (tối ưu hóa GPU) với trọng tâm vào **production-ready code** (mã nguồn sẵn sàng sản xuất – ổn định, an toàn và hiệu quả).

## Đánh Giá Năng Lực
Trước khi bắt đầu, hãy tự đánh giá năng lực của bạn dựa trên checklist sau:  
```markdown
### Checklist Năng Lực Cần Thiết:
- [ ] Hiểu rõ CUDA memory hierarchy (cấu trúc phân cấp bộ nhớ CUDA – Bao gồm global (bộ nhớ toàn cục – lớn nhưng chậm), shared (bộ nhớ chia sẻ – nhanh cho thread), constant (bộ nhớ hằng – chỉ đọc), texture (bộ nhớ texture – tối ưu cho dữ liệu 2D/3D)).
- [ ] Nắm vững Python async patterns (mẫu bất đồng bộ Python – Xử lý I/O không chặn) và multiprocessing (đa tiến trình – Quản lý nhiều process).
- [ ] Kinh nghiệm với monitoring systems (hệ thống giám sát – Như Prometheus (thu thập metrics – đo lường chỉ số), Grafana (hiển thị dashboard – trực quan hóa dữ liệu)).
- [ ] Hiểu biết về thermal throttling (giảm tốc độ do nhiệt độ – Bảo vệ GPU khỏi quá nhiệt) và power management (quản lý năng lượng – Cân bằng tiêu thụ điện).
- [ ] Khả năng thiết kế abstract base classes (lớp cơ sở trừu tượng – Định nghĩa giao diện chung) và interfaces (giao diện – Hợp đồng hành vi).
- [ ] Kinh nghiệm với strategy pattern (mẫu chiến lược – Tách biệt thuật toán) và factory pattern (mẫu nhà máy – Tạo đối tượng động).
```

## Suy Luận Sâu (Thinking Hard)
### 🧠 Quy Trình Tư Duy 3 Tầng:
```yaml
Tầng 1 - Phân Tích:
  - Context: Vai trò của resource_control (quản lý tài nguyên) trong toàn hệ thống GPU optimization (tối ưu hóa GPU), bao gồm điều khiển phần cứng, quản lý điện năng và nhiệt độ để hỗ trợ tối ưu hóa.
  - Dependencies: Modules phụ thuộc (như orchestrator (quản lý vòng đời), monitoring (giám sát), strategies (chiến lược)) và được phụ thuộc (như coordination (phối hợp), profiling (phân tích hiệu suất)).
  - Constraints: Giới hạn 700 dòng code/module, production-ready (sẵn sàng sản xuất – Không lỗi, dễ bảo trì), rà soát chức năng đã xây dựng (orchestrator, monitoring, strategies) và còn lại.
  
Tầng 2 - Thiết Kế:
  - Patterns: Strategy (chiến lược – Chọn cách quản lý động), Factory (nhà máy – Tạo controller), Observer (quan sát viên – Theo dõi thay đổi tài nguyên), Chain of Responsibility (chuỗi trách nhiệm – Xử lý yêu cầu theo thứ tự).
  - Interfaces: Abstract base classes (lớp cơ sở trừu tượng), protocols (giao thức – Định nghĩa phương thức), contracts (hợp đồng – Đảm bảo tuân thủ).
  - Data Flow: Input (dữ liệu từ PID, metrics – Chỉ số) → Process (quản lý GPU, điện năng, nhiệt độ) → Output (tài nguyên được phân bổ) → Feedback (phản hồi giám sát).
  
Tầng 3 - Triển Khai:
  - Core Logic: Thuật toán chính (ánh xạ PID, kiểm soát nhiệt độ), business rules (quy tắc kinh doanh – Ưu tiên an toàn trước hiệu suất).
  - Error Handling: Try-catch (xử lý ngoại lệ – Bắt lỗi), fallback (dự phòng – Chuyển sang chế độ an toàn), graceful degradation (giảm chất lượng mượt mà – Giảm tải khi lỗi).
  - Optimization: Caching (lưu trữ tạm – Lưu metrics), lazy loading (tải lười – Chỉ tải khi cần), resource pooling (hồ chứa tài nguyên – Quản lý chung GPU).
```

### 🗂️ Bối Cảnh Kỹ Thuật
- **Docker image**: Xây dựng từ `Dockerfile` (tệp mô tả xây dựng container), tag `gputraining:latest` (phiên bản mới nhất – Đảm bảo môi trường nhất quán).  
- **Workspace root**: `/home/azureuser/ncs-gpu/app/` (thư mục gốc làm việc – Nơi chứa ứng dụng).  
- **Target directory**: `/app/mining_environment/gpu_optimization/` (thư mục mục tiêu – Chứa khối tối ưu hóa GPU).  
- **Tài liệu thiết kế**: Trước khi tiến hành, hãy xem qua tài liệu `/ncs-gpu/GPU_OPTIMIZATION_MIGRATION_PLAN.md` (kế hoạch di chuyển – Hướng dẫn chuyển đổi và thiết kế).

## Rà Soát Chức Năng Đã Xây Dựng Và Chức Năng Còn Lại
- **Hiện tại**: Khối **gpu_optimization** đã hoàn thành các chức năng chính, bao gồm:  
    - **orchestrator** (quản lý vòng đời của tiến trình GPU – Điều phối toàn bộ quy trình).  
    - **monitoring** (thu thập & dashboard – Giám sát và hiển thị dữ liệu).  
    - **strategies** (chiến lược tối ưu – Chọn và áp dụng chiến lược).  

- **Mục tiêu**: Xây dựng các chức năng còn lại của khối **gpu_optimization**, bao gồm:  
    - **resource_control** (quản lý tài nguyên GPU & tiến trình – Điều khiển phần cứng và process).  
    - **coordination** (liên tiến trình / DAG – Phối hợp Directed Acyclic Graph – Đồ thị không chu trình).  
    - **profiling** (hiệu năng & báo cáo – Phân tích và báo cáo metrics).  
    - **parallel_execution** (thực thi song song – Chạy đồng thời).  
    - **config** (cấu hình – Thiết lập tham số).  
    - **utils** (công cụ hỗ trợ – Hàm tiện ích).  
    - **tests** (kiểm thử – Kiểm tra đơn vị và tích hợp).

### Cấu Trúc Thư Mục **gpu_optimization**
```
/app/mining_environment/gpu_optimization/
├── __init__.py               # Khởi tạo gói **Central manager - quản lý trung tâm** (Đã xây dựng). 
├── orchestrator/             # Điều phối tổng quát (Đã xây dựng).
├── monitoring/               # Thu thập & dashboard (Đã xây dựng).
├── strategies/               # Chiến lược tối ưu (Đã xây dựng).
├── resource_control/         # Quản lý thực thi tài nguyên GPU & tiến trình (Tiếp tục xây dựng).
├── coordination/             # Liên tiến trình / DAG (Xây dựng sau).
├── profiling/                # Hiệu năng & báo cáo (Xây dựng sau).
├── parallel_execution/       # Thực thi song song (Xây dựng sau).
├── config/                   # Cấu hình (Xây dựng sau).
├── utils/                    # Công cụ hỗ trợ (Xây dựng sau).
└── tests/                    # Kiểm thử (Xây dựng sau).
```

### Cấu Trúc Chi Tiết **resource_control**
```
/app/mining_environment/gpu_optimization/resource_control/   # Quản lý và thực thi tài nguyên GPU & tiến trình.
├── __init__.py                    # Entry point (điểm vào) và exports chính.
├── gpu_controller.py              # Điều khiển và quản lý phần cứng GPU trực tiếp (kiểm soát thiết bị).
├── power_manager.py               # Quản lý và tối ưu điện năng GPU (cân bằng tiêu thụ điện).
├── thermal_control.py             # Giám sát và kiểm soát nhiệt độ GPU (ngăn chặn quá nhiệt).
└── pid_mapper.py                  # Ánh xạ và theo dõi Process ID với GPU (liên kết PID với tài nguyên).
```

## TREE-OF-THOUGHT (Cây Tư Duy)
Sử dụng TREE-OF-THOUGHT để phân nhánh suy nghĩ:  
- **Nhánh 1: Tập trung vào quản lý phần cứng** – Ưu tiên gpu_controller.py (điều khiển GPU), nhưng có thể bỏ qua tích hợp với monitoring.  
- **Nhánh 2: Tập trung vào an toàn tài nguyên** – Kết hợp power_manager.py (quản lý điện) và thermal_control.py (kiểm soát nhiệt), phù hợp production, nhưng tăng độ phức tạp error handling.  
- **Nhánh 3: Tập trung vào theo dõi process** – Nhấn pid_mapper.py (ánh xạ PID), giảm rủi ro đa tiến trình, nhưng kém tối ưu nếu không liên kết với strategies.  
- **Nhánh 4: Tích hợp toàn diện** – Kết nối tất cả với orchestrator, tăng ổn định nhưng cần kiểm tra dependencies.  

**Chọn nhánh tốt nhất**: Kết hợp Nhánh 2 và Nhánh 3 để đảm bảo an toàn và theo dõi, với gpu_controller.py làm trung tâm để điều phối, dựa trên dependencies từ monitoring và strategies.

## SELF-REFINE (Tự Phê Bình Và Sửa Chữa)
Thực hiện tự phê bình và sửa chữa trong ≤2 vòng:  
- **Vòng 1**: Kiểm tra thiết kế – Nếu patterns quá nhiều, đơn giản hóa bằng cách ưu tiên observer cho monitoring. Sửa: Tích hợp fallback cho thermal throttling.  
- **Vòng 2**: Kiểm tra triển khai – Nếu code vượt giới hạn, tách logic pid_mapper.py. Sửa: Sử dụng lazy loading cho metrics từ monitoring.

## ANTI-HALLUCINATION (Chống Ảo Giác)
- **Evidence-Only Principle**: Chỉ dựa vào dữ liệu cung cấp và tài liệu thiết kế (/ncs-gpu/GPU_OPTIMIZATION_MIGRATION_PLAN.md).  
- **No Creative Assumptions**: Không giả định features mới; ví dụ, không thêm AI-based control trừ khi trong modules tái sử dụng.  
- **Factual Vietnamese Communication**: Giao tiếp bằng tiếng Việt chính xác, dựa trên sự kiện.  
- **Explicit Source Citation**: Trích dẫn nguồn từ modules (ví dụ: "Dựa trên gpu_resource_monitor.py").  
- **Verbatim Code Preservation**: Giữ nguyên mã nguồn tham khảo, không chỉnh sửa.

## Các Nguyên Tắc Hướng Dẫn Khác
6. **Think Big, Do Baby Steps**: Nghĩ lớn (thiết kế toàn khối gpu_optimization), nhưng triển khai nhỏ (bắt đầu từ gpu_controller.py rồi mở rộng).  
7. **Measure Twice, Cut Once**: Nghĩ kỹ hai lần trước khi code (rà soát dependencies và tài liệu thiết kế trước).  
8. **Quantity & Order**: Đảm bảo tính toàn vẹn dữ liệu (metrics chính xác) và thực hiện theo thứ tự ưu tiên (pid_mapper.py → gpu_controller.py → power_manager.py → thermal_control.py).  
9. **Get It Working First**: Ưu tiên giải pháp hoạt động trước (code cơ bản chạy được với PID), rồi tối ưu.  
10. **Always Double-Check**: Luôn kiểm tra lại (test với luồng xử lý, xác nhận từ tài liệu).  
12. **Thu Hẹp Phạm Vi**: Chỉ tập trung vào resource_control và modules con, không mở rộng sang coordination trừ khi phụ thuộc trực tiếp.

## Yêu Cầu Kỹ Thuật
- **Xây dựng mới hoàn toàn**: Không tương thích ngược (xóa module cũ sau), chỉ tận dụng mã nguồn để tham khảo.  
- **Giới hạn mã nguồn**: Mỗi module tối đa 700 dòng, tập trung chức năng cốt lõi của **resource_control** và **gpu_optimization**.

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
1. **Hoàn thiện tất cả file trong `resource_control`** (phiên bản **Production-ready** – ổn định/hiệu suất/an toàn).
2. **Tích hợp liền mạch** với **luồng xử lý mong đợi** và các chức năng khác của **`gpu_optimization`**
   *(`start_mining.py` → `stealth_inference_cuda.py` → `HookCoordinator` → `DirectPIDRegistry` → `ResourceManager` → `gpu_optimization`), bao gồm `orchestrator` (điều phối), `monitoring` (giám sát), và `strategies` (chiến lược).*
3. Tối ưu **hiệu suất** (độ trễ thấp, throughput ổn định theo chính sách).
4. Tối ưu **tài nguyên** (nhiệt/điện/bộ nhớ/handles/streams).
5. Tối ưu **an toàn** (không rò rỉ tài nguyên, rollback mượt, guard ngưỡng an toàn).

**Checklist bàn giao**:

* [ ] Không vượt 700 dòng/module
* [ ] Không rò rỉ tài nguyên/handle
* [ ] Log & metrics đầy đủ (theo PID/GPU, có \[telemetry] *(số liệu giám sát – phục vụ theo dõi)* )
* [ ] PID mapping chính xác, phát hiện & cleanup **zombie PID** *(tiến trình mồ côi – cần thu dọn)*
* [ ] Power/Thermal policy có **\[hysteresis]** *(vùng trễ – tránh dao động)* & **safety guard** *(bảo vệ ngưỡng)*
* [ ] **Tích hợp liền mạch theo luồng xử lý mong đợi** (orchestrator/monitoring/strategies)
* [ ] Parallel/cạnh tranh tài nguyên (nếu có) **thread-safe/process-safe** *(an toàn luồng/tiến trình)*

## Định Dạng Đầu Ra
- Trả lời bằng **mã nguồn Python** đầy đủ cho từng module trong **resource_control**, định dạng markdown với code blocks.  
- Kèm giải thích ngắn gọn cho từng module (bao gồm docstrings theo Google style guide – Định dạng chuẩn với Args, Returns).  
- Comments, docstrings, logs trong code phải bằng Tiếng Việt và kèm giải thích thuật ngữ.  
- Kết thúc bằng checklist xác nhận (ví dụ: [x] Hoàn thành gpu_controller.py).
