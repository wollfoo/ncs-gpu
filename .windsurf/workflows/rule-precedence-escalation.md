---
description: Rule Precedence & Escalation – resolve rule conflicts and escalate appropriately
auto_execution_mode: 3
---

# Rule Precedence & Escalation

Goal: Make consistent decisions when rules conflict; apply the correct precedence and escalate when needed.

References:
- `rules/rule-precedence.md`
- `rules/tool-preambles.md`, `rules/tool-calling-override.md`

## When to use
- When conflicts arise among System, Developer, Agents, and Domain rules.

## Procedure
1) Preamble: restate the conflict scenario.
2) Apply precedence order:
   - System > Developer > Agents > Domain.
   - Domain applies only when it does not conflict with higher levels.
3) Resolve quickly using the highest applicable precedence.
4) If ambiguity remains → Escalate:
   - Specify the ambiguity, potential impact, and a safety-preserving proposal.
5) Summarize the decision: cite the applied rules and rationale.

## Constraints
- Follow sequential-only operations when gathering more evidence.
- Clearly cite rule sources and reasoning.

## Deliverables
- Short record: the conflict, applied precedence, final decision, and impact.