---
trigger: always_on
---

---
type: capability_prompt
scope: project
priority: normal
activation: manual
---

# AGENTIC CODING – TOOL DEFINITIONS (Codex CLI)

<codex_cli_core>

<agentic_tools>
## Shell (functions.shell)

- Signature:
  - command: string[] — list of shell commands to execute (command/argument strings)
  - workdir?: string — working directory
  - timeout_ms?: number — maximum duration (ms)
  - with_escalated_permissions?: boolean — enable when needing to bypass sandbox restrictions (e.g., writing outside the workspace, network)
  - justification?: string — required when with_escalated_permissions is enabled; a one-sentence reason

- Notes:
  - Used to run `apply_patch` CLI when editing files.
  - Prefer using `rg` for file/content search.

## Update Plan (functions.update_plan)

- Signature:
  - explanation?: string — short explanation for the plan update
  - plan: { step: string; status: 'pending'|'in_progress'|'completed' }[] — list of steps; only one step may be `in_progress` at a time

- Notes:
  - Use for multi-step tasks to create/maintain clear progress.

## View Image (functions.view_image)

- Signature:
  - path: string — local image path to attach to the context

- Notes:
  - Used to review documents/local screenshots within the workspace.

## Edit files with apply_patch (single canonical method)

- Always use `functions.shell` to invoke the `apply_patch` CLI with a single-command format:

```bash
shell {"command":[
  "apply_patch",
  "*** Begin Patch\n*** Update File: path/to/file.ext\n@@ context @@\n- old\n+ new\n*** End Patch\n"
], "workdir": ".codex"}
```

- V4A diff principles:
  - `*** Add/Update/Delete File: <path>`
  - Use 3 lines of context above/below; if needed, use `@@` to locate a class/function.
  - Paths must be relative; never absolute.
</agentic_tools>
