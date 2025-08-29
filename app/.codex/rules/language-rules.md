---
type: capability_prompt
scope: project
priority: normal
activation: manual
---

# LANGUAGE RULES – Profiles

<language_profile>

- Default: tuân theo Developer Guidelines của Codex CLI (ngôn ngữ/định dạng do Developer quy định).
- VI Profile (kích hoạt thủ công):
  - Phản hồi bằng tiếng Việt.
  - Với thuật ngữ tiếng Anh, thêm mô tả ngắn tiếng Việt khi cần rõ nghĩa.
- EN Profile (kích hoạt thủ công):
  - Phản hồi bằng tiếng Anh tiêu chuẩn.

## Standard Syntax (khi dùng chú giải thuật ngữ)
`<English Term>` (mô tả tiếng Việt – chức năng/mục đích)

## Ví dụ
- `Tool Calling` (gọi công cụ – kích hoạt hàm/bên ngoài để thực hiện tác vụ)
- `Responses API` (API phản hồi – tái sử dụng ngữ cảnh/lập luận giữa các lần gọi công cụ)
- `Reasoning Effort` (mức độ lập luận – kiểm soát độ sâu tư duy và xu hướng gọi công cụ)
- `Persistence` (kiên trì – tiếp tục cho đến khi hoàn tất yêu cầu trước khi kết thúc lượt)
- `Markdown` (định dạng – dùng đúng ngữ nghĩa; backticks cho tên file/thư mục/hàm/lớp; \( \) và \[ \] cho công thức)
- `Apply Patch` (áp bản vá – chỉnh sửa file bằng diff chuẩn V4A qua `apply_patch`)

</language_profile>
