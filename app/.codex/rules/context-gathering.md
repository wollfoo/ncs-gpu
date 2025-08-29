---
trigger: always_on
---
---
type: capability_prompt
scope: project
priority: normal
activation: always_on
---

# CONTEXT GATHERING – EARLY STOP + TOOL BUDGET

<context_gathering>
Goal: Get enough context fast. Sequence discovery step-by-step and stop as soon as you can act.

Method:
- Start broad, then fan out to focused subqueries.
- Sequentially launch varied queries; read top hits per query. Deduplicate paths and cache; don’t repeat queries.
- Avoid over searching for context. If needed, run targeted searches in a short sequential pass.
- Tool budget: tối đa 2 lần gọi tool cho giai đoạn gathering (ưu tiên độ chính xác nhanh).

Architecture comprehension mode (sequential-only):
- When the goal is to understand the project architecture or module boundaries, open and read files sequentially — one module at a time — to preserve narrative continuity.
- Open files one at a time to synthesize architecture; never open more than one file at once in this mode.
- Rationale: sequential deep reading reduces context switching and prevents premature synthesis errors during architecture mapping.

Sequential codebase context analysis (overview-to-detail; sequential-only):
- Activation:
  - Use when the goal is to understand project architecture or module boundaries.
- Constraints:
  - Execute file reads, directory listings, and searches one at a time (sequential-only) to preserve narrative continuity.

- Workflow:
  1) Global overview (high-level):
     - Identify root docs and manifests (e.g., README, CONTRIBUTING, package manager manifests), primary entrypoints (e.g., src/app/, main files), and high-level directory structure (depth 2–3).
     - Note packages/apps/services and major boundaries (domains, layers).
  2) Dependency mapping (module order):
     - Build a lightweight dependency order from providers/dependencies to consumers (analyze dependencies first, then dependents).
     - Use import/require/use edges and config wiring as signals; adjust order if conflicts appear.
  3) Module pass (per module, still high-level):
     - Read public API (exports/types), configs, side-effects, external IO (DB, HTTP, FS), and responsibilities; avoid deep function-level dives.
     - Record invariants, contracts, and cross-module touchpoints.
  4) Function/class deep dive (detailed):
     - After module context is stable, dive into internal functions/classes of each module in the established order (most central/high-risk first).
     - Verify invariants and contracts; add notes for edge cases and error handling.
  5) Verification loop:
     - If new relationships are discovered, update the dependency map and revisit impacted summaries before proceeding.

- Exit criteria:
  - Architecture map + module summaries + key invariants identified; can point to exact files/symbols for critical paths.
    
    - Notes:
    -  - Prefer targeted, sequential reads over narrow, per-query grep passes (one at a time) while in this mode.
    -  - If time-constrained, complete overview + top critical modules (Pareto), then proceed to detailed passes.

- Early stop criteria:
  - You can name exact content to change.
  - Top hits converge (~70%) on one area/path.

- Escalate once:
  - If signals conflict or scope is fuzzy, run one refined sequential pass, then proceed.

- Depth:
  - Trace only symbols you’ll modify or whose contracts you rely on; avoid transitive expansion unless necessary.

- Loop:
  - Sequential search passes → minimal plan → complete task.
  - Search again only if validation fails or new unknowns appear. Prefer acting over more searching.
</context_gathering>

<context_gathering>
- Search depth: very low
- Bias strongly towards providing a correct answer as quickly as possible, even if it might not be fully correct.
- Usually, this means an absolute maximum of 2 tool calls.
- If you think that you need more time to investigate, update the user with your latest findings and open questions. You can proceed if the user confirms.
</context_gathering>
