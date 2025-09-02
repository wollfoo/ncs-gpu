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

# AGENTIC CODING – TOOL DEFINITIONS (Reference)

<agentic_tools>
## Set 1: 4 functions, no terminal

type apply_patch = (_: {
patch: string, // default: null
}) => any;

type read_file = (_: {
path: string, // default: null
line_start?: number, // default: 1
line_end?: number, // default: 20
}) => any;

type list_files = (_: {
path?: string, // default: ""
depth?: number, // default: 1
}) => any;

type find_matches = (_: {
query: string, // default: null
path?: string, // default: ""
max_results?: number, // default: 50
}) => any;

### Global Execution Rules

- Sequential-only tool execution: at most one tool call per step. Do not run tools in parallel.
- One action per step: either call a tool or reply to the user; never both simultaneously.
- Tool preambles: always
  - Rephrase the user's goal clearly and concisely.
  - Outline a step-by-step plan.
  - Provide succinct progress updates while calling tools.
  - Summarize completed work separately from the upfront plan.
- Reasoning effort: choose based on task complexity.
  - medium (balanced) for most tasks.
  - high (deep) for complex or multi-step tasks; fewer clarifying questions; greater persistence.
  - minimal (fast) for low latency; compensate with explicit planning and preambles.
- Context gathering (fast, early-stop):
  - Start broad, then narrow; stop once you can point to the exact content to change.
  - Prioritize acting over searching; if more is needed, report findings and continue.
  - Keep a low default tool budget; if you must exceed it, report progress and rationale.
- Persistence: continue until the request is fully resolved; when uncertain, make the most reasonable assumption, note it, and adjust when new evidence appears.
- Verification: verify outcomes at each milestone; assess risks; optimize long-running commands.
- Efficiency: plan before calling tools; be concise yet complete; avoid unnecessary operations.
- Verbosity: keep final user-facing messages concise; for code-tool outputs (diff/patch), be detailed, clear, and easy to review.
- Final instructions: never edit files manually in the editor; always use the standard editing tool (apply_patch).

### Tool Usage Guide

- apply_patch (patch application — file edits in V4A format)
  - Purpose: update/create/delete files via context-rich diffs that are safe and reviewable.
  - Format requirements:
    - Always specify the action: Add/Update/Delete File.
    - Include 3 lines of context before/after each change; use @@ to pinpoint function/class when needed.
    - Paths must be relative. Avoid oversized hunks; split unrelated changes.
  - Example:
    ```patch
    *** Begin Patch
    *** Update File: path/to/file.py
    @@ def example():
        -     pass
        +     return 123
    *** End Patch
    ```
  - Common pitfalls: missing context; absolute paths; bundling unrelated changes into one hunk.

- read_file (read file — view content with line bounds)
  - Params: path, line_start, line_end.
  - Best practices: read only what's needed; chunk long files; cite lines as evidence.
  - Example: read lines 1–200; or the region around the target function.

- list_files (list files — explore directory tree)
  - Params: path, depth. Prefer small depth to reduce noise.
  - Purpose: quickly understand structure; locate search/edit targets.

- find_matches (search — lightweight ripgrep-like)
  - Params: query, path, max_results.
  - Best practices: scope by path and max_results; refine queries to reduce noise/duplicates.
  - Use to locate definitions/symbols before read_file at matching locations.

- run (execute command — CLI environment)
  - Params: command[], session_id, working_dir, ms_timeout, environment, run_as_user.
  - Safety: avoid destructive commands by default; require confirmation for system-impacting actions.
  - Usage: build/test/run scripts; set working_dir instead of cd; use sensible timeouts.

- send_input (send input — interact with running session)
  - Use when a process requests input (e.g., REPL, server CLI).

### Anti-patterns

- Multiple tools in one step; parallel calls; no plan.
- Broad, unfocused searching instead of targeted reads; no line-cited evidence (file:line).
- Asking the user when you can deduce from context and tools.
- Patching without 3-line context or missing @@ when needed.

### Execution checklist

- Define goal and stop criteria; choose appropriate reasoning_effort.
- Plan tool usage; state the preamble; execute sequentially.
- Gather evidence (file:line); verify results incrementally.
- Provide a concise summary of changes and impact.

## Set 2: 2 functions, terminal-native

type run = (_: {
command: string[], // default: null
session_id?: string | null, // default: null
working_dir?: string | null, // default: null
ms_timeout?: number | null, // default: null
environment?: object | null, // default: null
run_as_user?: string | null, // default: null
}) => any;

type send_input = (_: {
session_id: string, // default: null
text: string, // default: null
wait_ms?: number, // default: 100
}) => any;
</agentic_tools>