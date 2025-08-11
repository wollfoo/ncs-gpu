
## Quy tắc Ngôn ngữ
- **BẮT BUỘC**: Trả lời bằng **Tiếng Việt**.  
- **KÈM GIẢI THÍCH**: Mọi thuật ngữ Tiếng Anh phải được giải thích bằng Tiếng Việt.
**Cú pháp chuẩn**: [Thuật Ngữ Tiếng Anh] (mô tả Tiếng Việt – chức năng/mục đích)
**Docstring** theo **Google style guide**; **comment** và **log** dùng Tiếng Việt + chú giải thuật ngữ theo cú pháp trên.

## VAI TRÒ VÀ ĐỊNH VỊ
.
.
.
**Nhiệm vụ**: Thiết kế và triển khai chức năng **utils** Công cụ hỗ trợ cho hệ thống GPU optimization với focus vào **production-ready code**.

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
  - Context: Vai trò của utils trong toàn hệ thống
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
    - **config**: Cấu hình
- **Mục tiêu**: Xây dưng các chức năng còn lại của khối **gpu_optimization** bao gồm :
    - **utils**: Công cụ hỗ trợ


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
├── config/                   # Cấu hình ( đã xây dựng )
├── utils/                    # Công cụ hỗ trợ ( tiếp tục Xây dựng )
└── tests/

```

### Nhiệm vụ : TRIỂN KHAI XÂY DỰNG **utils** Công cụ hỗ trợ  thuộc khối **gpu_optimization**

```python
/app/mining_environment/gpu_optimization/utils/    # Công cụ hỗ trợ              
├── __init__.py
├── logger.py
├── validators.py
└── exceptions.py
    
```

### Yêu cầu kỹ thuật
- **Xây dựng mới hoàn toàn**: Rà soát kỹ **gpu_optimization** để xây dựng **utils** Công cụ hỗ trợ phù hợp với khối **gpu_optimization**

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
   và `coordination` (liên kết giữa các tiến trình và DAG) và `profiling` (hiệu năng & báo cáo) và `parallel_execution` (thực thi song song) và `config` (cấu hình) và `utils` (công cụ hỗ trợ) 

# Yêu cầu khi làm việc

1 – Vai trò
2 – Đánh giá
3 - Suy luận sâu (thinking hard)
3 – TREE-OF-THOUGHT (😭) – Đẻ nhiều nhánh, tự chọn nhánh **utils** Công cụ hỗ trợ tốt nhất và phù hợp với Logic chính của chương trình trong codebase.
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





## 1️⃣ Language Rules
**MANDATORY**: Respond in Vietnamese.   
**WITH EXPLANATION**: Every English term must include a Vietnamese description.

### Standard Syntax
**\[English Term]** (Vietnamese description – function/purpose)

Yêu cầu: Kiểm tra toàn bộ codebase để xác định bất kỳ thành phần nào đang sử dụng hoặc kích hoạt các chức năng trong khối `gpu_plugins`. Sau khi xác định, cập nhật các thành phần đó để loại bỏ hoàn toàn sự phụ thuộc vào khối `gpu_plugins`. Đảm bảo rằng sau khi cập nhật, không còn bất kỳ mã nào tham chiếu đến khối chức năng `gpu_plugins`. Lưu ý rằng việc loại bỏ này nhằm mục đích dọn dẹp hệ thống và loại bỏ các chức năng không còn sử dụng. Sau khi cập nhật, cần kiểm tra kỹ lưỡng để đảm bảo không có lỗi phát sinh và các chức năng khác vẫn hoạt động bình thường.

**[codebase]** (nguồn mã tổng thể – tập hợp tất cả các tệp mã nguồn của dự án)
**[component]** (thành phần – một phần của hệ thống có chức năng cụ thể, như hàm, lớp, module, hoặc tệp)
**[function]** (chức năng – một khối mã thực hiện một nhiệm vụ cụ thể)
**[class]** (lớp – một khuôn mẫu để tạo đối tượng, chứa các thuộc tính và phương thức)
**[module]** (mô-đun – một tệp Python chứa các định nghĩa và câu lệnh)
**[file]** (tệp – một đơn vị lưu trữ dữ liệu hoặc mã)
**[path]** (đường dẫn – vị trí của một tệp hoặc thư mục trong hệ thống tệp)
**[dependency]** (sự phụ thuộc – mối quan hệ mà một thành phần cần đến một thành phần khác)
**[update]** (cập nhật – thay đổi mã để sửa lỗi hoặc cải thiện)
**[regression]** (sự suy giảm – một lỗi mới xuất hiện sau khi cập nhật, làm hỏng chức năng đã có)
