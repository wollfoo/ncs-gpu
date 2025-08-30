---
description: Debug + Verification – systematic debugging and result verification
auto_execution_mode: 3
---

# Debug + Verification

Goal: Perform systematic debugging, identify the root cause, and verify end-to-end under the principle "Never Assume, Always Verify".

References:
- `rules/global-rules.md` (Always Double-Check, Three-Layer Thinking)
- `rules/context-understanding.md`
- `rules/persistence.md`
- `rules/environment-profile.md`
- `rules/tool-preambles.md`

## When to use
- When behavior deviates; bugs are reproducible or flaky.
- After code changes when impact must be verified.

## Systematic debug process
1) Rephrase goal + short plan: describe the bug, expected behavior, and suspected scope.
2) Minimal reproduction:
   - Confirm environment constraints per `environment-profile.md` (output limits, network, ...).
3) Root-cause isolation:
   - Narrow scope using signals (stack trace, logs, recent commits).
   - Avoid outer-layer fixes without understanding the core issue.
4) Minimal fix:
   - Produce a small diff; consider side effects and backward compatibility.
5) Logging and measurement:
   - Add temporary logging if needed (remove after verification).

## Verification
- Test end-to-end against the original scenario and edge cases.
- Double-check: repeat the repro; confirm symptoms are gone.
- If tests exist: run them and assess coverage of critical edge cases.

## Constraints
- Sequential-only tool calls; narrate progress after each step.
- Evidence-first actions; avoid assumptions.

## Deliverables
- Short report: root cause, changes made, and verification method.
- List of verified test cases/steps and results.