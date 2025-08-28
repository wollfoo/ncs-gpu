# Markdown Style Guide

Mục tiêu: đảm bảo tất cả tài liệu *.md thống nhất, dễ đọc và dễ hợp nhất vào `AGENTS.md`.

## Cấu trúc

- Phần mở đầu: có thể dùng front‑matter YAML (tùy chọn) với `title`, `weight`.
- Tiêu đề: dùng `#` đến `######` với 1 khoảng trắng sau ký hiệu, không bỏ trống tiêu đề.
- Độ sâu: nội dung trong mỗi tệp nên bắt đầu từ H2 trở xuống (builder sẽ dịch nếu cần).
- Mục lục: không cần tự chèn, builder sẽ tạo ở `AGENTS.md`.

## Định dạng

- Dòng mới: dùng LF, không CRLF.
- Khoảng trắng: không để dấu cách ở cuối dòng; tab → 4 dấu cách.
- Đoạn văn: tránh hơn 2 dòng trống liền nhau.
- Code fence: dùng ``` hoặc ~~~; ưu tiên ``` với chỉ định ngôn ngữ khi có thể (```python).
- Liên kết: dùng dạng `[text](relative/path.md#anchor)` cho liên kết chéo giữa các tệp nguồn.

## Tiêu đề & Anchor

- Nội dung tiêu đề ngắn gọn, nhất quán; tránh ký tự đặc biệt.
- Builder tạo anchor theo dạng GitHub và tiền tố theo slug tệp; không cần tự chèn anchor.

## Front‑matter (tùy chọn)

```yaml
---
title: Principles
weight: 10
---
```

- `title`: tiêu đề hiển thị khi ghép vào `AGENTS.md`.
- `weight`: xác định thứ tự ưu tiên (số nhỏ trước) khi không có `--order-file`.

## Ví dụ vòng đời chỉnh sửa

1. Tạo/ chỉnh `.md` trong `.codex/rules`, tuân thủ hướng dẫn này.
2. (Tuỳ chọn) cập nhật file thứ tự `AGENTS_ORDER`.
3. Chạy builder: `make agents`.
4. Xem lại `AGENTS.md` và liên kết/anchor.

