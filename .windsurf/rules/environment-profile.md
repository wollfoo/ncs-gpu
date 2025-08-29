---
trigger: always_on
---

---
type: capability_prompt
scope: project
priority: normal
activation: always_on
---

# ENVIRONMENT PROFILE – Codex CLI Runtime

<codex_cli_core>
<environment_profile>

- Sandbox: `workspace-write` — read/write only within the workspace; writing outside or performing operations requires privilege escalation.
- Approvals: `on-request` — escalate only when truly necessary, with a concise justification.
- Network: `restricted` — avoid commands that require network; if necessary, request escalation with a clear reason.
- Output limit: terminal output is truncated at ~10KB or 256 lines; prefer reading in small chunks.
- Read rule: read at most 250 lines per file read; if longer, split into multiple consecutive reads.
- Search rule: prefer `rg`/`rg --files` over `ls -R/find/grep`.
- Escalation: when network access or writing outside the workspace is needed, set `with_escalated_permissions: true` and provide a one-sentence justification.

</environment_profile>
