---
trigger: always_on
---

---
type: capability_prompt
scope: project
priority: normal
activation: always_on
---

# LANGUAGE RULES
- **MANDATORY**: Respond in Vietnamese.  
- **WITH EXPLANATION**: Every English term must include a Vietnamese description.

## Standard Syntax
**\<English Term\>** (Vietnamese description – function/purpose)

## Code Comments / Logs / Docstrings – Language usage
- Default: Code comments (comments), log messages (logs), and docstrings must be in Vietnamese, in accordance with `rules/language-rules.md`.
- Bilingual at critical places: For module-level and Public API docstrings, as well as operational guides, provide bilingual content when the team primarily uses Vietnamese:
  - First line: Vietnamese (prioritized for internal users).
  - Immediately after: English (for industry-standard compatibility and tool ecosystem support).
- Guidance for structured logging: keep keys/fields in English (stable for machine parsing), and the `message` in Vietnamese; optionally add a short English sentence when the log is an important cross-language communication.
- Valid exceptions: when a library/standard requires English (e.g., linter tag/naming conventions, machine-readable schemas), prioritize compatibility and add a nearby Vietnamese note when necessary.
- Standard citation: when mentioning an English term in comments/logs/docstrings, include a brief Vietnamese description following the format in “Standard Syntax”.

## Example
**Tool Calling** (gọi công cụ – kích hoạt hàm/bên ngoài để thực hiện tác vụ)

## Example
**Responses API** (API phản hồi – tái sử dụng ngữ cảnh/lập luận giữa các lần gọi công cụ)

## Example
**Reasoning Effort** (mức độ lập luận – kiểm soát độ sâu tư duy và xu hướng gọi công cụ)

## Example
**Persistence** (kiên trì – tiếp tục cho đến khi hoàn tất yêu cầu trước khi kết thúc lượt)

## Example
**Markdown** (định dạng – dùng đúng ngữ nghĩa; backticks cho tên file/thư mục/hàm/lớp; \( \) và \[ \] cho công thức)

## Example
**Apply Patch** (áp bản vá – chỉnh sửa file bằng diff chuẩn V4A qua công cụ apply_patch)