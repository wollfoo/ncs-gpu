---
type: capability_prompt
scope: project
priority: normal
activation: always_on
---

# ENVIRONMENT PROFILE – Codex CLI Runtime

<codex_cli_core>
<environment_profile>

- Sandbox: `workspace-write` — chỉ đọc/ghi trong workspace; ghi ngoài/thao tác yêu cầu nâng quyền.
- Approvals: `on-request` — chỉ nâng quyền khi thực sự cần, kèm `justification` súc tích.
- Network: `restricted` — tránh lệnh cần mạng; nếu bắt buộc, yêu cầu nâng quyền rõ lý do.
- Output limit: terminal cắt bớt khoảng ~10KB hoặc 256 dòng; ưu tiên đọc theo khối nhỏ.
- Read rule: đọc tệp tối đa 250 dòng/lần; nếu dài hơn, chia nhiều lượt đọc liên tiếp.
- Search rule: ưu tiên `rg`/`rg --files` thay cho `ls -R/find/grep`.
- Escalation: khi cần network/ghi ngoài workspace, đặt `with_escalated_permissions: true` và cung cấp `justification` 1 câu.

</environment_profile>

