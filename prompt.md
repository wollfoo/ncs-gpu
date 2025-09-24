## xây dựng prompt với nội dung như bên dưới

## nội dung:


```markdown

## ✅ Language Rules
- **MANDATORY**: Respond in Vietnamese.  
- **WITH EXPLANATION**: Every English term must include a Vietnamese description.

### Standard Syntax
**[English Term]** (Vietnamese description – function/purpose)


### 🗂️ Bối Cảnh Kỹ Thuật
- Toàn bộ codebase trong `directory: ~/opus-gpu/app`.
- Docker image: xây dựng từ `Dockerfile`, tag `api-models:latest`.  

### Nhiệm vụ :
- Phân tích, rà soát kỹ codebase `directory: ~/opus-gpu/app`.

Đề xuất phương án tái cấu trúc kiến trúc chương trình thành một repo mới `~/opus-gpu/app/app-gpu` với các yêu cầu sau:
1. Giảm thiểu độ trễ bằng cách tối ưu hóa luồng xử lý và giảm phụ thuộc giữa các module
2. Loại bỏ các lỗi tiềm ẩn thông qua việc áp dụng kiểm thử tự động và thiết kế phòng thủ
3. Thiết kế hệ thống module hóa để dễ dàng quản lý và bảo trì
4. Xây dựng kiến trúc mở rộng để hỗ trợ thêm chức năng trong tương lai mà không ảnh hưởng đến hệ thống hiện có
- Tương lai tích hợp các chức năng sau:
   1. Bảo vệ và Ngụy trang Tiến trình: Che giấu và bảo vệ các tiến trình hệ thống quan trọng
   2. Bảo vệ Lưu lượng Mạng: Mã hóa và bảo mật tất cả lưu lượng mạng
   4. Binary Hijacking & Legitimate Replacement (chiếm dụng nhị phân & thay thế hợp lệ)
   5. Argument Vector Sophisticated Manipulation (thao tác vectơ tham số ở mức tinh vi)
   6. Process Tree Legitimacy Engineering (thiết kế tính hợp lệ của cây tiến trình)
   7. Network Traffic Advanced Obfuscation (Giai đoạn 2 – làm nhiễu lưu lượng mạng nâng cao; mục tiêu: 9.5/10)
     - Protocol Layer Deep Camouflage (ngụy trang sâu ở tầng giao thức)
     - DNS Covert Channel Implementation (triển khai kênh bí mật qua DNS)
     - CDN/Cloud Service Traffic Mimicry (bắt chước lưu lượng qua CDN/dịch vụ đám mây)
   8. GPU Resource Advanced Camouflage (Giai đoạn 3 – ngụy trang tài nguyên GPU nâng cao; mục tiêu: 9.5/10)
     - Dynamic Machine Learning Workload Simulation (mô phỏng tải công việc học máy động)
     - Advanced Thermal & Power Management (quản lý nhiệt & công suất nâng cao)
     - Intelligent Academic Schedule Simulation (mô phỏng lịch nghiên cứu học thuật thông minh)
   9. Advanced Detection Evasion (Giai đoạn 4 – né tránh phát hiện nâng cao; mục tiêu: 9.5/10).
     - Behavioral Analysis Countermeasures (biện pháp đối phó phân tích hành vi)
     - Performance Counter Obfuscation (làm nhiễu bộ đếm hiệu năng).
     - Advanced Sandbox & VM Detection (phát hiện sandbox & máy ảo nâng cao).
   10. Advanced Detection Methodologies (các phương pháp phát hiện nâng cao)
     - Multi-Layer Behavioral Analysis (phân tích hành vi đa tầng)
     - Machine Learning-Based Detection (phát hiện dựa trên học máy)
     - Advanced Network Analysis (phân tích mạng nâng cao)
  
- Và các tính năng khác .. mà không phá vỡ hệ hiện hữu chức năng cốt lõi chương trình 

   1. Bảo vệ Danh tính và Quyền truy cập: Quản lý chặt chẽ danh tính và kiểm soát truy cập
   2. Điều chỉnh Hành vi và Vượt qua Phát hiện: Tối ưu hóa hành vi hệ thống để tránh bị phát hiện
   3. Điều chỉnh Cảnh báo và Phản ứng Tự động: Tự động hóa quy trình cảnh báo và xử lý sự cố
   4. Vượt qua Tường lửa và Kiểm tra Gói tin: Đảm bảo khả năng hoạt động qua các hệ thống bảo mật
   5. Tăng Cường Tuân Thủ và Bảo mật Zero Trust: Áp dụng triệt để nguyên tắc zero trust trong bảo mật


Về ngôn ngữ lập trình thay thế:
- Ưu tiên ngôn ngữ hỗ trợ đa luồng và xử lý song song để tối ưu phần cứng mining 
- Ưu tiên phù hợp với tất cả các chức năng vừa liệt kê ở trên được tích hợp vào chương trình
- Lựa chọn ngôn ngữ có tính ẩn danh cao, hỗ trợ mã hóa và bảo mật dữ liệu
- Xem xét các ngôn ngữ có hiệu năng cao và khả năng tương thích với phần cứng chuyên dụng


## Prompt có các yêu cầu sau:

* **Bối cảnh**
* **Vai trò**
* **Đánh giá**
    * Đánh giá năng lực:
    * Checklist Năng Lực Cần Thiết:
* **Suy luận sâu (thinking hard)**:
    * Quy trình suy luận 3 tầng:
* **Mục Tiêu**
* **Ràng buộc**
* **TREE-OF-THOUGHT** (😭): Phân nhánh nhiều hướng, tự chọn hướng tốt nhất.
* **SELF-REFINE**: Tự phê bình & chỉnh sửa tối đa 2 vòng.
* **ANTI-HALLUCINATION**:
  * Chỉ dựa trên **chứng cứ** (Evidence-Only).
  * Không giả định sáng tạo.
  * Giao tiếp bằng Tiếng Việt chuẩn xác.
  * **Trích dẫn** rõ nguồn , file, đường dẫn.
  * **Giữ nguyên** verbatim code gốc khi nhắc lại.
* **Think Big, Do Baby Steps**: Nghĩ tổng thể, triển khai từng bước nhỏ.
* **Measure Twice, Cut Once**: Suy nghĩ kỹ trước khi đề xuất.
* **Quantity & Order**: Bảo đảm toàn vẹn dữ liệu, ưu tiên thứ tự thực thi.
* **Always Double-Check**: Luôn xác minh; không bao giờ chủ quan.
* **Quy trình thực hiện**:
    * Hiểu dữ liệu:
    * Lên kế hoạch phân tích:
    * Thực hiện phân tích:
    * Xác thực kết quả:
    * Tái cấu trúc chương trình

* **Kết quả**:
## Sản phẩm bàn giao (Deliverables)

1) 01 repository hoàn chỉnh: /opus-gpu/app/app-gpu sẵn sàng chạy (Docker/compose), có mã nguồn, cấu hình, script đã sẵn sàng cho triển khai sản xuất và có thể chạy ngay lập tức.
2) 01 báo cáo kỹ thuật định dạng Markdown với các yêu cầu:
  - Cấu trúc rõ ràng với heading, bullet points
  - Bao gồm các code block khi cần thiết
  - Trình bày mạch lạc về mặt logic
  - Kèm theo cây thư mục chi tiết
  - Mô tả trách nhiệm cụ thể của từng module
- 01 sơ đồ kiến trúc hệ thống, có thể trình bày bằng:
  - ASCII art
  (Lưu ý: Sơ đồ phải tương ứng với nhánh code được chọn)
- 01 bộ kiểm thử đầy đủ bao gồm:
  - Unit test
  - Integration test
  - Performance test
  - Kèm theo các tiêu chí định lượng rõ ràng để xác định pass/fail

```

