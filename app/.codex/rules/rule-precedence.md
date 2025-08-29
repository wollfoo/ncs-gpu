---
type: capability_prompt
scope: project
priority: normal
activation: always_on
---

# RULE PRECEDENCE – Conflict Resolution

<codex_cli_core>
<rule_precedence>

- Order of precedence:
  - System > Developer > AGENTS > Domain
- Guidance:
  - Khi có xung đột, tuân thủ mức cao hơn theo thứ tự trên.
  - Domain rules (CareFlow/Taubench…) chỉ áp dụng khi không mâu thuẫn với AGENTS/Developer/System.
  - Nếu một rule yêu cầu ngôn ngữ/định dạng khác, ưu tiên Developer Guidelines của Codex CLI.

</rule_precedence>

