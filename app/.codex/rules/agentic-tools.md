---
trigger: always_on
---

---
trigger: always_on
---

---
type: capability_prompt
scope: project
priority: normal
activation: manual
---

# AGENTIC CODING – TOOL DEFINITIONS (Codex CLI)

<codex_cli_core>

<agentic_tools>
## Shell (functions.shell)

- Signature:
  - command: string[] — danh sách lệnh shell để thực thi (chuỗi lệnh/đối số)
  - workdir?: string — thư mục làm việc
  - timeout_ms?: number — thời gian tối đa (ms)
  - with_escalated_permissions?: boolean — bật khi cần vượt hạn chế sandbox (ví dụ: ghi ngoài workspace, network)
  - justification?: string — bắt buộc khi bật with_escalated_permissions; mô tả 1 câu lý do

- Ghi chú:
  - Dùng để chạy `apply_patch` CLI khi chỉnh sửa file.
  - Ưu tiên dùng `rg` cho tìm kiếm tệp/nội dung.

## Update Plan (functions.update_plan)

- Signature:
  - explanation?: string — diễn giải ngắn cho lần cập nhật kế hoạch
  - plan: { step: string; status: 'pending'|'in_progress'|'completed' }[] — danh sách bước, chỉ 1 bước `in_progress` tại một thời điểm

- Ghi chú:
  - Dùng cho tác vụ nhiều bước, tạo/duy trì tiến độ rõ ràng.

## View Image (functions.view_image)

- Signature:
  - path: string — đường dẫn ảnh cục bộ cần đính kèm vào ngữ cảnh

- Ghi chú:
  - Phục vụ review tài liệu/ảnh chụp màn hình cục bộ trong workspace.

## Chỉnh sửa file bằng apply_patch (chuẩn duy nhất)

- Luôn dùng `functions.shell` để gọi CLI `apply_patch` với định dạng một lệnh duy nhất:

```bash
shell {"command":[
  "apply_patch",
  "*** Begin Patch\n*** Update File: path/to/file.ext\n@@ context @@\n- old\n+ new\n*** End Patch\n"
], "workdir": ".codex"}
```

- Nguyên tắc diff V4A:
  - `*** Add/Update/Delete File: <path>`
  - Dùng 3 dòng ngữ cảnh trên/dưới; nếu cần, dùng `@@` để định vị class/hàm.
  - Đường dẫn chỉ tương đối; không bao giờ tuyệt đối.
</agentic_tools>
