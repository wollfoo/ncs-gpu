---
description: Deep Reasoning – reasoning depth control and disciplined tool calling
auto_execution_mode: 3
---

# Deep Reasoning

Goal: Maintain high reasoning quality, control cost/latency, and adhere to the persistence principle.

References:
- `rules/reasoning-effort.md`
- `rules/persistence.md`
- `rules/tool-preambles.md`

## When to use
- Multi-step, ambiguous, high-risk tasks, or tasks with many dependencies.

## Procedure
1) Rephrase the goal concisely and clearly.
2) Set the Reasoning Effort:
   - Default: high (prioritize quality and coverage).
   - Lower to medium when flow is stable and inputs/outputs are clear.
3) Plan per `tool-preambles.md` and follow it during execution.
4) Execute sequentially (sequential-only): one tool call per step, narrate progress.
5) Persistence: do not finish early; continue until the objective is fully met.
6) Minimal reasoning (when needed): add a brief reasoning summary at the start of the answer.

## Heuristics
- Raise effort to high when: context conflicts, repeated errors, or many interdependent steps appear.
- Lower effort when: the process is smooth, a stable baseline exists, and response time matters.

## Deliverables
- Brief reasoning summary (if complex).
- Plan and step-by-step completion status.