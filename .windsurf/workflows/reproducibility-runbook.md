---
description: Reproducibility Runbook – ensure reproducibility, environment control, and command logging
auto_execution_mode: 3
---

# Reproducibility Runbook

Goal: Ensure all results are reproducible by controlling environment, seeds, versions, and the command trail.

References:
- `rules/global-rules.md` (Reproducibility plan, Required outputs)
- `rules/environment-profile.md` (sandbox limits, network, output, search/read rules)
- `rules/swe-bench.md` (thorough verification, edge-case coverage)
- `rules/tool-preambles.md`, `rules/tool-calling-override.md`

## When to use
- Before executing complex sequences that must be 100% repeatable.
- Before/after applying a patch or a risky change.

## Procedure
1) Preamble: restate the goal and outline a sequential plan.
2) Environment Baseline:
   - Record versions of critical tools (e.g., runtime, package manager).
   - Follow `environment-profile.md`: avoid network unless necessary; restrict IO to the workspace.
3) Seeds & Determinism:
   - Set seeds for libraries/components with randomness (if applicable).
   - Use deterministic flags/options when available.
4) Dependency Pinning:
   - Record versions of all used packages/dependencies.
5) Command Log:
   - Log commands and parameters; ensure the sequence is replayable.
6) Artifact Registry:
   - List produced files/artifacts, locations, and sizes (if relevant).
7) Verification:
   - Re-run the logged procedure and confirm results match.
   - Add edge cases per `rules/swe-bench.md`.

## Constraints
- Sequential-only: one tool call per step; narrate progress.
- Respect environment limits: output truncation, search/read rules, restricted network.

## Deliverables
- Environment summary (key versions), seeds, and dependencies.
- Ordered command log that can be replayed.
- Artifact list and confirmation of successful reproducibility.