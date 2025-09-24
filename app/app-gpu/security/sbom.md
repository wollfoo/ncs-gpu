# SBOM Process

1. Chạy `make sbom` để sinh [SBOM] (danh sách thành phần – kiểm kê phụ thuộc) dạng SPDX.
2. Lệnh dùng `syft packages . -o spdx-json > security/sbom.json` và sinh attestation `security/sbom.att.json`.
3. Lưu trữ artifact vào kho bảo mật theo chính sách Zero Trust.
