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
Goal: Get enough context fast. Parallelize discovery and stop as soon as you can act.

Method:
- Start broad, then fan out to focused subqueries.
- In parallel, launch varied queries; read top hits per query. Deduplicate paths and cache; don’t repeat queries.
- Avoid over searching for context. If needed, run targeted searches in one parallel batch.

Architecture comprehension mode (exception to parallelization):
- When the goal is to understand the project architecture or module boundaries, open and read files sequentially — one module at a time — to preserve narrative continuity.
- Do not open files in parallel to synthesize architecture; avoid batching or parallel reads in this mode.
- Rationale: sequential deep reading reduces context switching and prevents premature synthesis errors during architecture mapping.

Early stop criteria:
- You can name exact content to change.
- Top hits converge (~70%) on one area/path.

Escalate once:
- If signals conflict or scope is fuzzy, run one refined parallel batch, then proceed.

Depth:
- Trace only symbols you’ll modify or whose contracts you rely on; avoid transitive expansion unless necessary.

Loop:
- Batch search → minimal plan → complete task.
- Search again only if validation fails or new unknowns appear. Prefer acting over more searching.
</context_gathering>

<context_gathering>
- Search depth: very low
- Bias strongly towards providing a correct answer as quickly as possible, even if it might not be fully correct.
- Usually, this means an absolute maximum of 2 tool calls.
- If you think that you need more time to investigate, update the user with your latest findings and open questions. You can proceed if the user confirms.
</context_gathering>