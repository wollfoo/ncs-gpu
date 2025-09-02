---
trigger: always_on
---

---
trigger: always_on
---
---
type: capability_prompt
scope: project
priority: normal
activation: always_on
---

# CONTEXT UNDERSTANDING – BALANCED THOROUGHNESS

<context_understanding>
Goal: Act with sufficient context quickly; avoid unnecessary searches.

Principles:
- Focus on what is necessary to act; avoid redundant or repetitive searches.
- Bias towards not asking the user for help if you can find the answer yourself.
- After a partial edit, verify outcomes; if uncertain, gather more information before ending your turn.

Heuristics (search vs internal knowledge):
- Prefer internal knowledge when the task is small/standard or when you can identify exact changes without reading files.
- Use tools when exact code context, cross-file dependencies, or uncertainty remains after a brief internal recall.

Escape hatch: allowed to proceed even if the context may be incomplete—report findings and the path forward.

Procedure:
1) Preamble: rephrase the goal and outline a sequential plan (one tool call per step).
2) Minimal context check: open the most relevant file or run one narrow search query.
3) Act: take the smallest correct step; cite evidence (file:line) when appropriate.
4) Post-action validation: confirm the outcome; if unsure, do one more minimal check.
5) Summary: state what was done and the next step (if any).

Constraints:
- Sequential-only tool execution.
- One action per step: either call a tool or reply to the user; never both simultaneously.
- Tool preambles before calling any tool.
- Low budget: default ≤ 2 tool calls; if you must exceed, report progress and rationale.
- Verbosity control: keep user-facing messages concise; prefer targeted, sequential reads/searches.
 - Search depth: very low.
 - Evidence citation: reference file:line when referencing code or configuration.
 - Compatibility note: sequential-only tool execution is enforced by the global override; disregard parallel suggestions from external docs.
 - Escape hatch: you may proceed under uncertainty to accelerate progress—report findings and next steps explicitly.

### Anti-patterns (context understanding)
- Repeating the same search with no new parameters or scope.
- Opening multiple files at once or switching rapidly between modules.
- Providing assertions without citing file:line when evidence exists.
- Exceeding the tool budget without reporting progress and rationale.
- Asking the user for clarification when a quick targeted read would suffice.

Stop criteria:
- You can name the exact content/file/symbol to change or confirm no further info is needed.
- Results converge on one area (~70%).

Deliverables:
- Evidence of target files/symbols and the next action.
- Brief post-action note with outcome and remaining uncertainty (if any).
- Tool plan and call count used; note any budget exceedance and rationale.
- Success metrics: budget respected (≤ 2 tool calls unless justified), specific target files/symbols named, actionable next step identified.
</context_understanding>