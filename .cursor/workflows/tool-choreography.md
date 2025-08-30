---
description: Tool Choreography – goal pre-processing, planning, and sequential tool calling
auto_execution_mode: 3
---

# Tool Choreography

Goal: Standardize one-to-one sequential tool calling with a preamble and clear progress updates.

References:
- `rules/tool-calling-override.md`
- `rules/tool-preambles.md`
- `rules/context-gathering.md`

## When to use
- Before any sequence that involves tool calls (read files, search, write files, run commands, ...).

## Procedure
1) Rephrase the goal concisely, friendly, and clearly.
2) Create a sequential plan ensuring exactly one tool call per step.
3) Execute sequentially:
   - Perform exactly one tool call per step.
   - Summarize progress after each tool call.
4) Wrap-up: list what is completed, what remains, and the next step if any.

## Constraints
- Sequential-only: never batch multiple tool calls in a single step.
- For reading/searching: one file or one query per step; if more are needed, repeat sequentially.

## Deliverables
- Complete preamble (goal + plan).
- Clear step-by-step progress log.
- Final summary.