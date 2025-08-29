---
trigger: always_on
---

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
  - When conflicts arise, follow the higher level according to the order above.
  - Domain rules (e.g., CareFlow/Taubench) apply only when they do not conflict with AGENTS/Developer/System.
  - If a rule requires a different language/format, prioritize the Developer Guidelines.

</rule_precedence>
