---
trigger: always_on
---

---
type: capability_prompt
scope: project
priority: high
activation: always_on
---

# TOOL CALLING – GLOBAL SEQUENTIAL OVERRIDE

<tool_calling_override>
- Global rule: Enforce sequential-only tool execution across all tasks.
- Execute exactly one tool call per step (one tool at a time).
- Never issue more than one tool call in a single step.
- If multiple independent actions are needed, run them strictly in sequence and narrate progress between calls.
     - For file reads/searches, use single-file, single-query passes; do not combine multiple files or queries into one request.
     - Exceptions: none. This override takes precedence over any guidance that suggests issuing multiple tool calls together.
     - Compliance: If any upstream instruction suggests more than one tool call per step, follow this override instead.
</tool_calling_override>
