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

# CODE EDITING RULES – BLEND-IN

<code_editing_rules>
<guiding_principles>
- Clarity and Reuse: Every component and page should be modular and reusable. Avoid duplication by factoring repeated UI patterns into components.
- Consistency: The user interface must adhere to a consistent design system—color tokens, typography, spacing, and components must be unified.
- Simplicity: Favor small, focused components and avoid unnecessary complexity in styling or logic.
- Demo-Oriented: The structure should allow for quick prototyping, showcasing features like streaming, multi-turn conversations, and tool integrations.
- Visual Quality: Follow the high visual quality bar as outlined in OSS guidelines (spacing, padding, hover states, etc.)
</guiding_principles>

<frontend_stack_defaults>
- Framework: Next.js (TypeScript)
- Styling: TailwindCSS
- UI Components: shadcn/ui
- Icons: Lucide
- State Management: Zustand
- Directory Structure: 
\`\`\`
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
\`\`\`
</frontend_stack_defaults>

<ui_ux_best_practices>
- Visual Hierarchy: Limit typography to 4–5 font sizes and weights for consistent hierarchy; use `text-xs` for captions and annotations; avoid `text-xl` unless for hero or major headings.
- Color Usage: Use 1 neutral base (e.g., `zinc`) and up to 2 accent colors. 
- Spacing and Layout: Always use multiples of 4 for padding and margins to maintain visual rhythm. Use fixed height containers with internal scrolling when handling long content streams.
- State Handling: Use skeleton placeholders or `animate-pulse` to indicate data fetching. Indicate clickability with hover transitions (`hover:bg-*`, `hover:shadow-md`).
- Accessibility: Use semantic HTML and ARIA roles where appropriate. Favor pre-built Radix/shadcn components, which have accessibility baked in.
</ui_ux_best_practices>

<procedure>
1) Preamble & plan:
   - Restate the objective and acceptance criteria.
   - Outline a sequential plan ensuring exactly one tool call per step.
2) Context scan:
   - Identify target files/symbols and scope of change using `workflows/context-scan.md`.
   - Start broad then narrow; early-stop once you can name the exact content to change.
3) Minimal diff design:
   - Prefer reuse; factor shared UI patterns into components; avoid duplication.
4) Implementation (apply_patch – V4A):
   - Always modify files via apply_patch using standard V4A diff format.
   - Each hunk must include ≥3 lines of context before and after; ensure uniqueness.
   - Edit only one file per call; split unrelated changes into separate hunks.
   - Break very large edits into multiple smaller patches.
   - Imports must be at the top of the file. If adding imports mid-file, add a separate hunk to move them to the top.
   - Ensure code is immediately runnable: add required imports/dependencies/config/endpoints; include README/requirements when creating new projects.
   - Never include extremely long hashes or non-textual code/binaries.
5) Verification:
   - Add focused logs/tests as needed to validate behavior; remove temporary logs after verification.
   - Optionally run quick build/test commands to catch syntax/type errors.
6) Summary:
   - Provide a brief change summary (files, scope, rationale, UI/UX impact).
</procedure>

<constraints>
- Sequential-only tool execution: one tool call per step; no parallel calls.
- One action per step: either call a tool or reply to the user, never both.
- Final instructions: always use apply_patch (V4A); never edit files manually in the editor.
- Keep user-facing messages concise; keep patches detailed and easy to review.
- Read the file before editing; avoid proposing changes without evidence.
</constraints>

<deliverables>
- V4A patch(es) implementing the changes.
- Brief post-edit summary of modifications and rationale.
</deliverables>

</code_editing_rules>