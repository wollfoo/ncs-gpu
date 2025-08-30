---
description: Context Scan – quick, sequential context scan with early stop (Early Stop)
auto_execution_mode: 3
---

# Context Scan

Goal: Gather just enough context to act quickly, avoid over-searching, and follow the sequential-only principle.

References:
- `rules/context-gathering.md`
- `rules/tool-calling-override.md`
- `rules/tool-preambles.md`

## When to use
- At the start of a new task to understand context/module boundaries.
- When ambiguity is high and you need to identify the minimal impact area.

## Procedure
1) Rephrase the goal per `tool-preambles.md`.
2) Draft a minimal plan with key questions and expected files/paths to inspect.
3) Global overview:
   - List high-level structure (docs/manifests, entrypoints, main directories).
   - Read sequentially: one file or one search command at a time.
4) Lightweight dependency mapping:
   - Record import/config relations.
   - Prefer reading providers before consumers.
5) Module pass:
   - Read only public APIs, responsibilities, external I/O; avoid deep dives.
6) Selective deep dive:
   - Dive into central/high-risk functions/classes only.
7) Verification loop:
   - If new relations are discovered, update the map and revisit impacted areas.

## Important constraints
- Sequential-only: one tool call per step. Do not batch multiple files/queries.
- Early stop: stop once you can precisely name the content to change.
- Low budget: at most 2 tool calls if possible, unless necessary.

## Stop criteria
- You can identify the exact file/function/class to modify.
- Search results converge (~70%) on one area.

## Deliverables
- Architecture summary and key touchpoints.
- List of target files/symbols and the expected change scope.