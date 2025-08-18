---
inclusion: always
---
---
type: capability_prompt
scope: project
priority: normal
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
  - Less proactive → `reasoning_effort: medium` + `<context_gathering>` (early stop, parallel, low tool budget).
  - More proactive → `reasoning_effort: high` + `<persistence>` (do not hand back early; continue until complete).
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

## Budgets & Stop Criteria

- Level `medium`:
  - Balance quality/latency; batch queries in small parallel waves.
  - Stop once you have a minimal action plan and a clear intervention point.

- Level `high`:
  - No hard cap on tool calls; define explicit stop conditions (completion criteria).
  - Apply `<persistence>` to keep going until all tasks are done.
  - Split separable tasks into multiple turns (multi-turn), one task per turn.

## Reasoning context reuse

- Responses API: use `previous_response_id` to pass prior reasoning items across turns, cutting latency and cost.
- Combine with multi-turn strategy to achieve better performance/stability at `high`.

