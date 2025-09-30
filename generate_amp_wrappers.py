#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tạo wrapper cho .windsurf/rules/** để Amp (AGENTS.md) có thể 'See @...' theo globs.

- Dò mọi *.md trong .windsurf/rules/** (bao gồm workflows/).
- Suy diễn globs theo tên file -> ghi vào YAML front matter.
- Mirror cấu trúc sang docs/windsurf-compat/**.
- (Tuỳ chọn) chèn block 'Windsurf compatibility wrappers' vào AGENTS.md.

Chạy:
  python3 scripts/generate_amp_wrappers.py \
      --rules-dir ".windsurf/rules" \
      --out-dir "docs/windsurf-compat" \
      --update-agents
"""

import argparse
import os
from pathlib import Path
import re
import sys
from typing import List, Tuple

# --------- cấu hình mặc định (có thể chỉnh) ---------

# Globs chung cho "file code"
GLB_CODE = [
    "**/*.ts", "**/*.tsx", "**/*.js",  "**/*.jsx",
    "**/*.py", "**/*.go",  "**/*.rs",  "**/*.java", "**/*.kt",
    "**/*.cpp","**/*.cc",  "**/*.c",   "**/*.h",    "**/*.hpp",
    "**/*.cu", "**/*.cuh",
    "**/*.sh", "**/*.bash","**/*.zsh", "**/*.ps1",
    "**/*.sql", "**/*.proto",
    "**/*.toml", "**/*.json"
]

# Globs cho tài liệu / Markdown
GLB_DOCS = ["**/*.md", "**/*.mdx", "**/*.mdc", "**/*.rst", "**/*.txt"]

# Globs cho CI/Infra
GLB_CI_INFRA = [
    "infra/**",
    ".github/workflows/**",
    "**/*.tf",
    "**/*.yaml", "**/*.yml",
    "**/Dockerfile", "docker/**", ".devcontainer/**"
]

# Một số thư mục benchmark thường gặp (nếu có)
GLB_BENCH = ["bench/**", "benchmark/**", "benchmarks/**"]

# Tên file (không phần mở rộng) -> loại suy diễn
ALWAYS_ON_NAMES = {
    "global-rules",
    "working-principles",
    "rule-precedence",
    "environment-profile",
    "rule-precedence-escalation",  # workflows/...
    "persistence",
}

CODE_HEAVY_NAMES = {
    "code-editing-rule",
    "cursor-coding-style",
    "language-rules",
    "tool-calling-override",
    "tool-preambles",
    "swe-bench",
    "terminal-bench",
    "swe-bench-mode",  # workflows/...
    "code-editing-playbook",  # workflows/...
    "tool-choreography",      # workflows/...
}

DOCS_HEAVY_NAMES = {
    "markdown-formatting",
    "communication-language-style",  # workflows/...
}

MIXED_KNOWLEDGE_NAMES = {
    # thường áp cho cả code & docs
    "context-gathering",
    "context-understanding",
    "context-scan",          # workflows/...
    "debug-verification",    # workflows/...
    "deep-reasoning",        # workflows/...
    "reasoning-effort",
    "memory_tool_usage_guide",
    "memory-discipline",     # workflows/...
    "reproducibility-runbook" # workflows/...
}

DOMAIN_NAMES_PREFIX = ("domain-",)  # domain-careflow, domain-retail-taubench, ...

# -----------------------------------------------------

def infer_globs(fname: str, rel_parts: List[str]) -> Tuple[List[str], str]:
    """
    Suy diễn globs cho wrapper dựa trên tên file (không .md) và đường dẫn con.
    Trả về: (globs, mode) — mode chỉ để in log (ALWAYS/CODE/DOCS/MIXED/CI)
    """
    base = Path(fname).stem  # e.g., 'code-editing-rule'
    lower = base.lower()
    subpath = "/".join(rel_parts)  # e.g., 'workflows/deep-reasoning.md' (không dùng .md ở đây)

    # 1) Always-on (không có globs -> luôn nạp khi AGENTS.md 'See' file wrapper)
    if lower in ALWAYS_ON_NAMES or lower.startswith(DOMAIN_NAMES_PREFIX):
        return ([], "ALWAYS")

    # 2) Rất định hướng code
    if lower in CODE_HEAVY_NAMES:
        glb = GLB_CODE + GLB_BENCH
        return (glb, "CODE")

    # 3) Định hướng tài liệu
    if lower in DOCS_HEAVY_NAMES:
        return (GLB_DOCS, "DOCS")

    # 4) Hỗn hợp (áp cho cả code & docs), +CI nếu bắt gặp từ khoá
    if (lower in MIXED_KNOWLEDGE_NAMES) or ("context" in lower) or ("reason" in lower):
        glb = GLB_CODE + GLB_DOCS
        if "reproduc" in lower or "runbook" in lower:
            glb = glb + GLB_CI_INFRA
        return (glb, "MIXED")

    # 5) CI/Infra nếu nằm dưới workflows và có từ khoá
    if ("workflows" in rel_parts and any(k in lower for k in ["reproduc", "runbook", "ci", "workflow"])):
        return (GLB_CI_INFRA + GLB_CODE, "CI")

    # 6) Mặc định: áp cho code + docs (an toàn)
    return (GLB_CODE + GLB_DOCS, "DEFAULT")


def write_wrapper(out_file: Path, rel_rule_path: str, globs: List[str]) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    title = out_file.stem
    with out_file.open("w", encoding="utf-8") as f:
        f.write(f"# {title} (Windsurf compatibility wrapper)\n")
        if globs:
            f.write("---\n")
            f.write("globs:\n")
            for g in globs:
                f.write(f"  - '{g}'\n")
            f.write("---\n")
        f.write(f"See @.windsurf/rules/{rel_rule_path}\n")


def collect_rule_files(rules_dir: Path) -> List[Path]:
    return sorted(rules_dir.rglob("*.md"))


def ensure_agents_block(repo_root: Path, out_dir: Path) -> None:
    agents = repo_root / "AGENTS.md"
    line = "See @"+str(out_dir).replace(str(repo_root)+"/", "")
    block_header = "## Windsurf compatibility wrappers"
    block = f"\n{block_header}\n{line}/**/*.md\n"
    if agents.exists():
        txt = agents.read_text(encoding="utf-8")
        if block_header in txt:
            # idempotent: update dòng See @ nếu khác
            new_txt = re.sub(rf"{re.escape(block_header)}[\s\S]*?(?=\n## |\Z)",
                             block+"\n", txt, count=1)
            if new_txt != txt:
                agents.write_text(new_txt, encoding="utf-8")
        else:
            with agents.open("a", encoding="utf-8") as f:
                f.write(block)
    else:
        with agents.open("w", encoding="utf-8") as f:
            f.write("# AGENTS.md\n\n")
            f.write(block)


def main():
    ap = argparse.ArgumentParser(description="Generate Amp wrappers for Windsurf rules")
    ap.add_argument("--repo-root", default=".", help="Đường dẫn root của repo (mặc định: .)")
    ap.add_argument("--rules-dir", default=".windsurf/rules",
                    help="Thư mục rules nguồn (mặc định: .windsurf/rules)")
    ap.add_argument("--out-dir", default="docs/windsurf-compat",
                    help="Thư mục đích cho wrapper (mặc định: docs/windsurf-compat)")
    ap.add_argument("--update-agents", action="store_true",
                    help="Chèn block 'Windsurf compatibility wrappers' vào AGENTS.md")

    args = ap.parse_args()
    repo_root = Path(args.repo_root).resolve()
    rules_dir = (repo_root / args.rules_dir).resolve()
    out_dir = (repo_root / args.out_dir).resolve()

    if not rules_dir.exists():
        print(f"[ERR] Không tìm thấy thư mục rules: {rules_dir}", file=sys.stderr)
        sys.exit(1)

    rule_files = collect_rule_files(rules_dir)
    if not rule_files:
        print(f"[WARN] Không thấy *.md trong {rules_dir}", file=sys.stderr)

    created = 0
    for rf in rule_files:
        rel = rf.relative_to(rules_dir)               # e.g. workflows/deep-reasoning.md
        rel_parts = list(rel.parts[:-1])              # e.g. ['workflows']
        globs, mode = infer_globs(rf.name, rel_parts) # suy diễn globs
        out_file = out_dir / rel                      # mirror cấu trúc
        write_wrapper(out_file, str(rel).replace("\\", "/"), globs)
        created += 1
        print(f"[OK] {mode:<7} -> {out_file.relative_to(repo_root)}  (See @.windsurf/rules/{rel})")

    if args.update_agents:
        ensure_agents_block(repo_root, out_dir)
        print(f"[OK] Đã cập nhật/khởi tạo AGENTS.md với block 'Windsurf compatibility wrappers'")

    print(f"\n[SUMMARY] Tạo {created} wrapper vào {out_dir.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
