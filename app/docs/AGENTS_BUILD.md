# AGENTS.md Build Guide

Purpose:
- Chuẩn hoá và hợp nhất nhiều tệp Markdown (.md) thành một tệp duy nhất `AGENTS.md`.
- Tạo mục lục (ToC), đảm bảo tiêu đề/anchor thống nhất, dễ bảo trì và mở rộng.

## Nhanh gọn

- Xây dựng tệp từ đường dẫn chuẩn:
  - `make agents` (yêu cầu quyền ghi ra thư mục repo gốc)
  - Hoặc: `PYTHONPATH=. python tools/agents_md_builder.py build --source ../.codex/rules --dest ../AGENTS.md --toc-depth 3 --min-level 2`

- Kiểm tra tính nhất quán Markdown của nguồn:
  - `make agents-check`
  - Hoặc: `python tools/agents_md_builder.py check --source ../.codex/rules`

## Nguồn và Thứ tự

- Nguồn mặc định: `../.codex/rules` (thư mục chứa tất cả các quy tắc dạng *.md).
- Thứ tự hợp nhất ưu tiên theo:
  1. `--order-file` (TXT: mỗi dòng một path tương đối; hoặc YAML tối giản với khoá `order:`)
  2. Front‑matter `weight: <int>` trong từng file
  3. Tiền tố số trong tên file (ví dụ `01-intro.md`) rồi đến thứ tự chữ cái

Ví dụ `AGENTS_ORDER` (TXT):

```
00-overview.md
01-principles.md
10-tools.md
```

Ví dụ YAML tối giản:

```
order:
  - 00-overview.md
  - 01-principles.md
  - 10-tools.md
```

## Chuẩn hoá nội dung

- Dòng: chuẩn hoá EOL về LF, bỏ khoảng trắng cuối dòng, tab → 4 dấu cách, tối đa 2 dòng trống liên tiếp.
- Tiêu đề: buộc có 1 khoảng trắng sau `#`, dịch mức tiêu đề để phần nội dung bắt đầu tại cấp `--min-level` (mặc định H2).
- Anchor: tạo anchor duy nhất theo kiểu GitHub, có tiền tố theo slug của tệp (tránh trùng lặp giữa các tệp).
- Liên kết chéo: `[text](other.md#anchor)` → `[text](#other-anchor)` nếu tìm được tệp/anchor tương ứng.
- Mục lục: sinh tự động dựa trên tiêu đề đã dịch (độ sâu `--toc-depth`).

## Tuỳ chọn lệnh

- `--source <dir>`: thư mục nguồn chứa *.md (mặc định `../.codex/rules`).
- `--dest <path>`: đường dẫn xuất ra `AGENTS.md` (mặc định `../AGENTS.md`).
- `--order-file <path>`: file xác định thứ tự hợp nhất (TXT/YAML tối giản).
- `--toc-depth <n>`: độ sâu mục lục (mặc định 3).
- `--min-level <n>`: cấp tiêu đề tối thiểu cho nội dung ghép (mặc định 2).
- `--include/--exclude`: các pattern glob tương đối để lọc tệp.

## Quy trình đề xuất (CI/Local)

1. Sửa nội dung trong `../.codex/rules` theo [Markdown Style Guide](./markdown_style_guide.md).
2. (Tuỳ chọn) Cập nhật `AGENTS_ORDER` để kiểm soát thứ tự.
3. Chạy `make agents` để sinh `AGENTS.md` ở gốc repo (cần quyền ghi ngoài `app/`).
   - Nếu không có quyền ghi, dùng `make agents-local` để sinh `app/AGENTS.md` (bản preview).
4. Chạy `make agents-check` để lint nội dung nguồn.
5. Commit thay đổi: `AGENTS.md`, tệp nguồn đã chỉnh, và (nếu có) file thứ tự.

## Lỗi thường gặp

- Không tìm thấy nguồn: đảm bảo `--source` trỏ tới thư mục có *.md.
- Liên kết chéo không đổi: xác minh đường dẫn `.md` và anchor khớp với tiêu đề.
- Trùng anchor: builder tự thêm hậu tố `-1`, `-2`… khi cần.

