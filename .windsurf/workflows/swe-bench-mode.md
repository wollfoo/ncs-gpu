---
description: SWE-Bench Mode – rigorously verified development mode
auto_execution_mode: 3
---

# SWE-Bench Mode

Goal: Make small, focused code changes via patches, verify thoroughly, cover edge cases, and only finish when correctness is certain.

References:
- `rules/swe-bench.md` (Verified Developer Instructions)
- `rules/environment-profile.md`
- `rules/tool-preambles.md`, `rules/tool-calling-override.md`, `rules/persistence.md`

## When to use
- When fixing bugs or building high-risk features that require high reliability.

## Procedure
1) Preamble: restate the goal and outline a sequential plan.
2) Prepare the patch in standard format (V4A apply_patch):
   - Keep changes minimal; preserve exact context lines.
3) Apply changes in small steps; after each step:
   - Assess impact and record progress.
4) Verification:
   - Review logic, run necessary checks; consider edge cases stated in the request.
   - Validate environment constraints (output limits, network, sandbox).
5) Double/Triple Check:
   - Recheck the change scope; avoid unintended side effects.
6) Summary: outline changes, rationale, and verification results.

## Constraints
- Sequential-only tool calls.
- Evidence first; avoid assumptions.
- Do not end early while uncertainty remains (persistence).

## Deliverables
- Minimal, standard-format patch.
- Verification summary (including critical edge cases) and results.