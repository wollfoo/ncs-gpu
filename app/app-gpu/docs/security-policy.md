# Chính sách bảo mật nền – Phase 1

## Mục tiêu
- Thiết lập nền tảng Zero Trust cho toàn bộ control plane ⇄ scheduler ⇄ executor.
- Áp dụng mTLS bắt buộc, quản lý secret tập trung và quy trình xoay vòng khoá.

## Thành phần cốt lõi
- **PKI nội bộ**: script `scripts/deploy/bootstrap_pki.sh` sinh CA gốc và cert dịch vụ.
- **Hồ sơ mTLS**: `configs/default/security/mtls.yaml` mô tả các subject, SAN và chu kỳ sống.
- **Quản lý secret**: tất cả khóa riêng và CA phải được lưu trong Vault/SOPS; repository chỉ chứa tài liệu và script.

## Nguyên tắc vận hành
1. Mọi service bắt buộc xác thực lẫn nhau bằng chứng thư hợp lệ do CA nội bộ cấp.
2. Chứng thư phải được xoay vòng ≤ 90 ngày, với thời gian chồng lấn tối thiểu 24 giờ để đảm bảo không gián đoạn.
3. Key và cert lưu ở dạng mã hoá; triển khai sản xuất phải tải từ secret manager trong quá trình bootstrap.
4. Log audit các sự kiện cấp phát, xoay vòng và thu hồi chứng thư.

## Bước kế tiếp
- Tích hợp script vào pipeline CI/CD để tạo sandbox PKI.
- Kết nối Vault (hoặc backend tương đương) nhằm phát hành dynamic secret cho từng service account.
