---
description: Memory Discipline – disciplined search, storage, and usage of contextual memory
auto_execution_mode: 3
---

# Memory Discipline

Goal: Ensure you always look up context when needed, store only correct, sufficient, and new information, and use consistent naming for effective reuse.

References:
- `rules/memory_tool_usage_guide.md`

## When to use
- When the request may involve prior context, external integrations, or consecutive task chains.

## Procedure
1) Context Assessment:
   - Identify trigger phrases that indicate memory lookup per the guide.
2) Search:
   - Use key/topic-based search; analyze results by similarity and recency.
3) Integrate:
   - Use retrieved information to improve responses; do not expose memory sources.
4) Store:
   - Store only when information is NEW/important; avoid duplicates; store summaries, not full conversations.
5) Naming:
   - Follow the schema: project_name/session_name/sequence + metadata (when appropriate).

## Stop criteria
- You have performed a lookup when context might be missing.
- You store only when there is new value; standard naming; no duplication.

## Deliverables
- Short internal summary of what was stored and a note when nothing was stored due to no new value.