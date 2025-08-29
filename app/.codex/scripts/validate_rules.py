#!/usr/bin/env python3
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / 'AGENTS.md'
OUT_DIR = ROOT / 'out'
OUT_INDEX = OUT_DIR / 'rules.index.json'
OUT_DEV = OUT_DIR / 'developer_instructions.md'
TERMINAL_BENCH = ROOT / 'rules' / 'terminal-bench.md'
AGENTIC_TOOLS = ROOT / 'rules' / 'agentic-tools.md'
GLOBAL_RULES = ROOT / 'rules' / 'Global-Rules.md'
CTX_GATHERING = ROOT / 'rules' / 'context-gathering.md'
ENV_PROFILE = ROOT / 'rules' / 'environment-profile.md'
LANG_RULES = ROOT / 'rules' / 'language-rules.md'

def run_compile():
    subprocess.check_call(['bash', str(ROOT / 'scripts' / 'compile_rules.sh')])

def assert_contains(path: Path, patterns: list[str], name: str):
    text = path.read_text(encoding='utf-8')
    for pat in patterns:
        if not re.search(pat, text, flags=re.IGNORECASE):
            raise AssertionError(f"Missing pattern in {name}: {pat}")

def assert_not_contains(path: Path, patterns: list[str], name: str):
    text = path.read_text(encoding='utf-8')
    for pat in patterns:
        if re.search(pat, text, flags=re.IGNORECASE):
            raise AssertionError(f"Forbidden pattern in {name}: {pat}")

def main():
    run_compile()

    # 1) JSON index present and valid
    data = json.loads(OUT_INDEX.read_text(encoding='utf-8'))
    assert isinstance(data, list) and len(data) > 0, 'rules.index.json must be a non-empty list'

    # 2) developer_instructions present and covers core sections
    assert OUT_DEV.exists(), 'developer_instructions.md was not generated'
    assert_contains(OUT_DEV, [
        r'AGENTIC CODING – TOOL DEFINITIONS',
        r'ENVIRONMENT PROFILE',
        r'RULE PRECEDENCE',
        r'TOOL PREAMBLES',
        r'LANGUAGE RULES',
    ], 'developer_instructions.md')

    # 3) AGENTS.md includes canonical apply_patch and no heredoc variants
    assert_contains(AGENTS, [r'apply_patch\",\n\s*\"\*\*\* Begin Patch'], 'AGENTS.md')
    assert_not_contains(AGENTS, [r"apply_patch\s*<<\s*'PATCH'", r"<<'EOF'", r'\"cmd\"\s*:\s*\[\s*\"apply_patch\"'], 'AGENTS.md')

    # 4) terminal-bench canonical call and Quick-Ops
    assert_contains(TERMINAL_BENCH, [r'Quick-Ops Checklist', r'apply_patch\` CLI', r'rg --files'], 'terminal-bench.md')
    assert_not_contains(TERMINAL_BENCH, [r"apply_patch\s*<<\s*'PATCH'", r"<<'EOF'"], 'terminal-bench.md')

    # 5) agentic-tools has functions.shell and elevated permissions fields
    assert_contains(AGENTIC_TOOLS, [r'functions\.shell', r'with_escalated_permissions', r'justification'], 'agentic-tools.md')

    # 6) Global-Rules recommends (not mandates) file:line citations
    assert_not_contains(GLOBAL_RULES, [r'100 % of code-related answers include `file:line`'], 'Global-Rules.md')

    # 7) context-gathering contains tool budget line
    assert_contains(CTX_GATHERING, [r'Tool budget.*2.*gọi tool'], 'context-gathering.md')

    # 8) environment-profile has runtime settings
    assert_contains(ENV_PROFILE, [r'workspace-write', r'on-request', r'restricted', r'250 dòng', r'rg --files'], 'environment-profile.md')

    # 9) language-rules is profile/manual (not always_on)
    assert_contains(LANG_RULES, [r'LANGUAGE RULES – Profiles', r'activation: manual'], 'language-rules.md')

    print('VALIDATION: OK')

if __name__ == '__main__':
    main()

