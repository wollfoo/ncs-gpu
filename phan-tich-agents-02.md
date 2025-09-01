Tiến hành triển khai cải tiến mã nguồn với các yêu cầu sau:

1. Refactor nhánh A bao gồm:
   - Run-epoch reset
   - One-writer RM
   - Grace + dwell
   - Registry-first
   - Hệ thống logging chuẩn

2. Ưu tiên hiệu năng ổn định:
   - Bật chế độ clock lock có điều kiện (ALLOW_CLOCK_LOCK=1)
   - Chỉ kích hoạt sau bước VERIFY khi đáp ứng:
     * Nhiệt độ hệ thống < ngưỡng quy định
     * Hash rate tăng tối thiểu X% trong khoảng thời gian T giây
   - Giá trị mặc định: ALLOW_CLOCK_LOCK=0

3. Yêu cầu chung:
   - Đảm bảo tính ổn định của hệ thống
   - Tối ưu hiệu năng theo điều kiện đã định
   - Tuân thủ quy trình logging chuẩn
