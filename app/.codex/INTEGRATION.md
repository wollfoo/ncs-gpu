# Codex CLI Integration Guide

This guide ensures Codex CLI loads and applies all rules from `.codex/rules/` by default.

## Build artefacts

- Compile unified rules and machine-readable indices:
  - `AGENTS.md` – human-friendly compiled rules
  - `rules/manifest.json` – machine index (with metadata)
  - `out/rules.index.json` – lightweight machine index (stable path)
  - `out/developer_instructions.md` – full developer instructions (to inject)

Run:
```bash
bash .codex/scripts/compile_rules.sh
```

## Inject into Developer Instructions

At session bootstrap, inject the content of `.codex/out/developer_instructions.md` into the model as Developer instructions.

Examples:

- Responses API style (pseudo):
```js
const dev = fs.readFileSync('.codex/out/developer_instructions.md','utf8');
client.responses.create({ model, instructions: dev, input: [...] });
```

- Chat-style (pseudo):
```js
const dev = fs.readFileSync('.codex/out/developer_instructions.md','utf8');
client.chat.completions.create({
  model,
  messages: [ { role: 'developer', content: dev }, ... ]
});
```

## Auto-loader (optional)

Use the loader to rebuild if needed and print developer instructions to stdout:

```bash
# All rules
python3 .codex/scripts/load_rules.py > /tmp/dev_instr.md
```

### Selective loader with flags (core-only)

- Python loader:
```bash
# Core rules only (activation=always_on OR tag=codex_cli_core)
python3 .codex/scripts/load_rules.py --core-only > /tmp/dev_instr_core.md
# All rules
python3 .codex/scripts/load_rules.py > /tmp/dev_instr_all.md
# JSON output
python3 .codex/scripts/load_rules.py --core-only --format json > /tmp/rules_core.json
```

## Validate rules consistency

Run validations to ensure canonical formats and core sections are present:

```bash
python3 .codex/scripts/validate_rules.py
```

This checks:
- Canonical `apply_patch` usage (no heredocs/legacy formats)
- Presence of core sections (tools, environment profile, precedence, preambles, language profiles)
- Runtime-awareness details (sandbox, approvals, network, chunked reads, rg)
- Indices exist and are valid JSON
