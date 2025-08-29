---
alwaysApply: false
---

---
type: capability_prompt
scope: project
priority: normal
activation: manual
---

# SWE-BENCH – VERIFIED DEVELOPER INSTRUCTIONS

<swe_bench>
In this environment, use a single canonical call via `shell` + `apply_patch` to edit files:

```bash
shell {"command":[
  "apply_patch",
  "*** Begin Patch\n[YOUR_PATCH]*** End Patch\n"
], "workdir": "."}
```

Where [YOUR_PATCH] is the actual content of your patch in V4A diff format.

Always verify your changes extremely thoroughly. You can make as many tool calls as you like - the user is very patient and prioritizes correctness above all else. Make sure you are 100% certain of the correctness of your solution before ending.
IMPORTANT: not all tests are visible to you in the repository, so even on problems you think are relatively straightforward, you must double and triple check your solutions to ensure they pass any edge cases that are covered in the hidden tests, not just the visible ones.
</swe_bench>
