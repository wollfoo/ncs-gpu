
## Quy tắc Ngôn ngữ
- **BẮT BUỘC**: Trả lời bằng **Tiếng Việt**.  
- **KÈM GIẢI THÍCH**: Mọi thuật ngữ Tiếng Anh phải được giải thích bằng Tiếng Việt.
**Cú pháp chuẩn**: [Thuật Ngữ Tiếng Anh] (mô tả Tiếng Việt – chức năng/mục đích)
**Docstring** theo **Google style guide**; **comment** và **log** dùng Tiếng Việt + chú giải thuật ngữ theo cú pháp trên.

## VAI TRÒ VÀ ĐỊNH VỊ
.
.
.
**Nhiệm vụ**: Thiết kế và triển khai chức năng **config** cấu hình cho hệ thống GPU optimization với focus vào **production-ready code**.

## ĐÁNH GIÁ NĂNG LỰC
.
.
.
Trước khi bắt đầu, hãy tự đánh giá:
```markdown
### Checklist Năng Lực Cần Thiết:
.
.
.
```

## THINKING HARD - SUY LUẬN SÂU 

### 🧠 Quy Trình Tư Duy 3 Tầng:

```yaml
Tầng 1 - Phân Tích:
  - Context: Vai trò của config trong toàn hệ thống
  - Dependencies: Modules phụ thuộc và được phụ thuộc
  - Constraints: Giới hạn 700 dòng/module, production-ready
  
Tầng 2 - Thiết Kế:
  - Patterns: Strategy, Factory, Observer, Chain of Responsibility
  - Interfaces: Abstract base classes, protocols, contracts
  - Data Flow: Input → Process → Output → Feedback
  
Tầng 3 - Triển Khai:
  - Core Logic: Thuật toán chính, business rules
  - Error Handling: Try-catch, fallback, graceful degradation
  - Optimization: Caching, lazy loading, resource pooling
```

### 🗂️ Bối Cảnh Kỹ Thuật
- **Docker image**: xây dựng từ `Dockerfile`, tag `gputraining:latest`  
- **Workspace root**: `/home/azureuser/ncs-gpu/app/`
- **Target directory**: `/app/mining_environment/gpu_optimization/`
- **Tài liệu thiết kế**: - Trước khi tiến hành hãy xem qua tài liệu `/ncs-gpu/GPU_OPTIMIZATION_MIGRATION_PLAN.md`

## Hãy rà soát các chức năng đã xây dựng và chức năng còn lại**
- **Hiện tại** : khối **gpu_optimization** đã hoàn thành các chức năng chính, bao gồm:
    - **orchestrator**: Quản lý vòng đời của tiến trình GPU
    - **monitoring**: Thu thập & dashboard
    - **strategies**: Chiến lược tối ưu
    - **resource_control**: Quản lý tài nguyên GPU & tiến trình
    - **coordination**: Liên tiến trình / DAG
    - **profiling**: Hiệu năng & báo cáo
    - **parallel_execution**: Thực thi song song
- **Mục tiêu**: Xây dưng các chức năng còn lại của khối **gpu_optimization** bao gồm :
    - **config**: Cấu hình
    - **utils**: Công cụ hỗ trợ
    - **tests**: Kiểm thử

### Cấu trúc thư mục **gpu_optimization**
```
/app/mining_environment/gpu_optimization/
├── __init__.py               # Khởi tạo gói **Central manager - quản lý trung tâm**  ( Đã xây dựng ) 
├── orchestrator/             # Điều phối tổng quát ( Đã xây dựng )
├── monitoring/               # Thu thập & dashboard ( Đã xây dựng )
├── strategies/               # Chiến lược tối ưu ( Đã xây dựng )
├── resource_control/         # Quản lý thực thi tài nguyên GPU & tiến trình ( Đã Xây dựng )
├── coordination/             # Liên tiến trình / DAG ( Đã Xây dựng )
├── profiling/                # Hiệu năng & báo cáo ( Đã tục Xây dựng )
├── parallel_execution/       # Thực thi song song ( Đã xây dựng )
├── config/                   # Cấu hình ( tiếp tục xây dựng )
├── utils/                    # Công cụ hỗ trợ ( Xây dựng sau )
└── tests/

```

### Nhiệm vụ : TRIỂN KHAI XÂY DỰNG **config** cấu hình thuộc thuộc khối **gpu_optimization**

```python
/app/mining_environment/gpu_optimization/config/    # cấu hình 
├── __init__.py                             
├── default.yaml
└── loader.py

```

### Yêu cầu kỹ thuật
- **Xây dựng mới hoàn toàn**: Rà soát kỹ **gpu_optimization** để xây dựng cấu hình phù hợp với khối **gpu_optimization**

### Luồng xử lý mong đợi
1. `start_mining.py` (khởi động hệ thống)
2. `stealth_inference_cuda.py` (khởi tạo tiến trình GPU)
3. `HookCoordinator` → `DirectPIDRegistry` (đăng ký PID)
4. `ResourceManager` (kích hoạt tối ưu với PID)
5. `gpu_optimization` (tiếp nhận PID và triển khai toàn bộ chức năng tối ưu GPU)

### Kết quả :
1. Đảm bảo hoàn thành cấu hình của **config** phiên bản Production ready
2. **Tích hợp liền mạch** với **luồng xử lý mong đợi** và các chức năng khác của **`gpu_optimization`**
   *(`start_mining.py` → `stealth_inference_cuda.py` → `HookCoordinator` → `DirectPIDRegistry` → `ResourceManager` → `gpu_optimization`), bao gồm `orchestrator` (điều phối), `monitoring` (giám sát), và `strategies` (chiến lược).* và `resource_control` (quản lý và thực thi tài nguyên ).*
   và `coordination` (liên kết giữa các tiến trình và DAG) và `profiling` (hiệu năng & báo cáo) và `parallel_execution` (thực thi song song) và `config` (cấu hình) và `utils` (công cụ hỗ trợ) và `tests` (kiểm thử)

# Yêu cầu khi làm việc

1 – Vai trò
2 – Đánh giá
3 - Suy luận sâu (thinking hard)
3 – TREE-OF-THOUGHT (😭) – Đẻ nhiều nhánh, tự chọn nhánh cấu hình tốt nhất và phù hợp với Logic chính của chương trình trong codebase.
4 – SELF-REFINE – Tự phê bình, tự sửa nhiều vòng (≤2 vòng)
5 – ANTI-HALLUCINATION 
  - Evidence-Only Principle
  - No Creative Assumptions
  - Factual Vietnamese Communication
  - Explicit Source Citation
  - Verbatim Code Preservation
6.  **Think Big, Do Baby Steps**: Think big, but implement in small steps.
7.  **Measure Twice, Cut Once**: Think carefully before acting.
8.  **Quantity & Order**: Ensure data integrity and execute in a prioritized sequence.
9.  **Get It Working First**: Prioritize a working solution before optimization.
10.  **Always Double-Check**: Always verify; never assume.
11 – Định dạng đầu ra
12 – Thu hẹp phạm vi

