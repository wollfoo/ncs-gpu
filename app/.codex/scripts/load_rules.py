#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = ROOT / 'rules'
OUT_DIR = ROOT / 'out'
OUT_INDEX = OUT_DIR / 'rules.index.json'
COMPILE = ROOT / 'scripts' / 'compile_rules.sh'

FM_PATTERN = re.compile(r'^(?:---[\r\n]+[\s\S]*?---[\r\n]+)+', re.MULTILINE)

def ensure_compiled():
    if not OUT_INDEX.exists():
        try:
            subprocess.check_call(['bash', str(COMPILE)])
        except Exception:
            # If compile is unavailable in runtime, continue and expect OUT_INDEX to exist
            pass

def strip_front_matter(text: str) -> str:
    return FM_PATTERN.sub('', text, count=1)

def build_markdown(rules):
    parts = ["# Developer Instructions – Selected Rules", ""]
    for r in rules:
        title = r.get('title') or r.get('file')
        parts.append(f"## {title}")
        try:
            content = Path(ROOT, r['file']).read_text(encoding='utf-8')
            content = strip_front_matter(content).rstrip()
        except Exception as e:
            content = f"[Error reading {r['file']}: {e}]"
        parts.append("")
        parts.append(content)
        parts.append("")
        parts.append("---")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"

def parse_args():
    ap = argparse.ArgumentParser(description='Load rules and output developer instructions (selected)')
    ap.add_argument('--core-only', action='store_true', help='Chỉ lấy rules core (activation=always_on hoặc tag codex_cli_core)')
    ap.add_argument('--format', choices=['markdown', 'md', 'json'], default='markdown', help='Định dạng đầu ra')
    ap.add_argument('--output', '-o', help='Đường dẫn file đầu ra (mặc định: stdout)')
    return ap.parse_args()

def main():
    args = parse_args()
    ensure_compiled()
    data = json.loads(OUT_INDEX.read_text(encoding='utf-8'))

    if args.core_only:
        sel = [x for x in data if (x.get('activation') == 'always_on') or ('codex_cli_core' in (x.get('tags') or []))]
    else:
        sel = data

    if args.format in ('markdown', 'md'):
        out = build_markdown(sel)
    else:
        out = json.dumps(sel, ensure_ascii=False, indent=2) + "\n"

    if args.output:
        Path(args.output).write_text(out, encoding='utf-8')
    else:
        sys.stdout.write(out)

if __name__ == '__main__':
    main()

