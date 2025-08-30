---
description: Code Editing Playbook – standardized code editing process per Code Editing Rules
auto_execution_mode: 3
---
# Code Editing Playbook

Goal: Edit code clearly, consistently, and maintainably with high UI/UX quality, while adhering to sequential tool calling.

References:
- `rules/code-editing-rule.md`
- `rules/tool-preambles.md`
- `rules/tool-calling-override.md`

## When to use
- Any task that requires creating/editing code, especially front-end using the default stack.

## Procedure
1) Preamble: restate the goal and outline a sequential plan (one tool call per step).
2) Context Scan: if needed, use `context-scan.md` to pinpoint the correct location/scope for changes.
3) Minimal diff design: avoid duplication; prefer reuse.
4) Execute edits in small steps:
   - Follow sequential-only: one tool call per step.
   - Briefly narrate progress after each step.
5) Quick UI/UX checks using the best practices below.
6) Change summary: briefly list items, files, scope, and rationale.

## Front-end defaults (per `frontend_stack_defaults`)
- Framework: Next.js (TypeScript)
- Styling: TailwindCSS
- UI Components: shadcn/ui
- Icons: Lucide
- State Management: Zustand
- Recommended Directory Structure:
```
/src
 /app
   /api/<route>/route.ts         # API endpoints
   /(pages)                      # Page routes
 /components/                    # UI building blocks
 /hooks/                         # Reusable React hooks
 /lib/                           # Utilities (fetchers, helpers)
 /stores/                        # Zustand stores
 /types/                         # Shared TypeScript types
 /styles/                        # Tailwind config
```

## UI/UX Best Practices (from `code-editing-rule.md`)
- Visual Hierarchy: limit to 4–5 font sizes/weights; use `text-xs` for captions; avoid `text-xl` except for major headings.
- Color Usage: one neutral base (e.g., `zinc`) + up to two accents.
- Spacing/Layout: use multiples of 4; prefer fixed-height containers with internal scrolling for long streams.
- State Handling: use skeleton/`animate-pulse` while fetching; clear hover states (`hover:bg-*`, `hover:shadow-md`).
- Accessibility: semantic HTML + ARIA; prefer Radix/shadcn components with built-in a11y.

## Constraints
- Sequential-only tool calling (see `tool-calling-override.md`).
- Clear preamble and progress narration (see `tool-preambles.md`).

## Deliverables
- Minimal, clear patch that follows the default directory structure.
- Brief change summary (files, rationale, UI/UX impact).