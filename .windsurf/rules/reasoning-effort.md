---
trigger: always_on
---

---
trigger: always_on
---

---
trigger: always_on
---
---
type: capability_prompt
scope: project
priority: high
activation: always_on
---

# REASONING EFFORT – CONTROL THINKING DEPTH + TOOL CALLING

<reasoning_effort>
- Default: `high` — prioritize reasoning quality and coverage; accept higher cost/latency, especially for complex/multi-step tasks.
- `medium` — balanced depth vs. latency for most tasks; moderate exploration, leverage `<context_gathering>` selectively to keep responsiveness while preserving quality.
- `high` — multi-step/hard/ambiguous tasks: increase tool-calling persistence, broaden context with explicit stop criteria; split work across agent turns; adhere to `<persistence>`.
    - Heuristics:
      - Raise to `high` when context conflicts, repeated errors, or many interdependent steps appear.
      - Lower to `medium` when the flow is stable, inputs/outputs are clear, and latency matters.
    - Links:
      - Less proactive → `reasoning_effort: medium` + `<context_gathering>` (early stop, sequential-only, low tool budget).
      - More proactive → `reasoning_effort: high` + `<persistence>` (do not hand back early; continue until complete).
      - When in architecture comprehension mode (see `<context_gathering>`), execute one tool at a time for file reading; prefer sequential deep reading.
      - Global rule: For all tasks, execute one tool call at a time (sequential-only). Never issue more than one tool call at the same time.
    
    - Parameter: `reasoning_effort` (controls how deeply to think and how readily to call tools; default `high`). Scale up/down with task difficulty; for complex/multi-step tasks, prefer `high` for best output quality.
    - Multi-turn optimization: best performance when separable tasks are split across multiple agent turns, one task per turn, before proceeding.
- Calibrating eagerness:
  - Decrease eagerness: lower `reasoning_effort`; use `<context_gathering>` with a low budget and early stop; provide an “escape hatch” like “even if it might not be fully correct” to proceed once essential context is sufficient.
  - Increase eagerness: raise `reasoning_effort` and apply `<persistence>` to increase persistence and reduce clarifying questions; define explicit stop conditions and safe action boundaries.
</reasoning_effort>

## Minimal reasoning – Guidance

<minimal_reasoning_guidelines>
1) Provide a brief summary of your thought process at the start of the final answer (e.g., bullets) to improve performance on difficult tasks.
2) Maintain a preamble describing the plan and progress during tool calls, per `<tool_preambles>`.
3) Disambiguate tool instructions as much as possible; insert `<persistence>` reminders to prevent handing back early.
4) Plan explicitly before calling tools because the reasoning budget is limited.
</minimal_reasoning_guidelines>

<minimal_reasoning_snippet>
Remember, you are an agent - please keep going until the user's query is completely resolved, before ending your turn and yielding back to the user. Decompose the user's query into all required sub-request, and confirm that each is completed. Do not stop after completing only part of the request. Only terminate your turn when you are sure that the problem is solved. You must be prepared to answer multiple queries and only finish the call once the user has confirmed they're done.

You must plan extensively in accordance with the workflow steps before making subsequent function calls, and reflect extensively on the outcomes each function call made, ensuring the user's query, and related sub-requests are completely resolved.
</minimal_reasoning_snippet>