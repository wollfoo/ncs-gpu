#!/usr/bin/env python3
"""
AGENTS.md Parser & Indexer

Goal:
- Phân tích tệp AGENTS.md và sinh chỉ mục JSON có cấu trúc, nhằm giúp Codex CLI
  hiểu sâu nội dung: cấu trúc, chức năng, quy tắc, checklist, công cụ.
- Cung cấp CLI truy vấn nhanh: tìm kiếm, lấy section theo path/anchor.

Không phụ thuộc thư viện ngoài. Python 3.8+.

Ví dụ:
  # Sinh chỉ mục JSON tại app/AGENTS_INDEX.json từ app/AGENTS.md
  python3 tools/agents_md_parser.py index --source ./AGENTS.md --dest ./AGENTS_INDEX.json

  # Truy vấn theo từ khoá
  python3 tools/agents_md_parser.py query --source ./AGENTS.md --search "checklist"

  # Xem một section theo đường dẫn tiêu đề
  python3 tools/agents_md_parser.py query --source ./AGENTS.md --path "GOLDEN RULES > LANGUAGE RULES"
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


HEADING_RE = re.compile(r'^(?P<hashes>#{1,6})\s+(?P<title>[^#].*?)\s*$')
ANCHOR_RE = re.compile(r'^<a id="(?P<id>[^"]+)"></a>\s*$')
FENCE_OPEN_RE = re.compile(r'^\s*```(?P<lang>\w+)?\s*$')
FENCE_CLOSE_RE = re.compile(r'^\s*```\s*$')
BULLET_RE = re.compile(r'^\s*[-*+]\s+(?P<text>.+)$')
NUM_BULLET_RE = re.compile(r'^\s*\d+[.)]\s+(?P<text>.+)$')


@dataclass
class CodeBlock:
    lang: Optional[str]
    content: str


@dataclass
class Section:
    level: int
    title: str
    anchor: Optional[str] = None
    content: List[str] = field(default_factory=list)
    bullets: List[str] = field(default_factory=list)
    code_blocks: List[CodeBlock] = field(default_factory=list)
    children: List['Section'] = field(default_factory=list)
    path: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "level": self.level,
            "title": self.title,
            "anchor": self.anchor,
            "path": self.path,
            "content": "\n".join(self.content).strip(),
            "bullets": self.bullets,
            "code_blocks": [dataclasses.asdict(cb) for cb in self.code_blocks],
            "children": [c.to_dict() for c in self.children],
        }


def normalize(text: str) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return [ln.rstrip() for ln in text.splitlines()]


def parse_agents_md(path: Path) -> Tuple[List[Section], Dict[str, Section]]:
    """Parse AGENTS.md into a hierarchical section tree.

    Returns: (top_level_sections, anchor_map)
    """
    lines = normalize(path.read_text(encoding="utf-8"))
    # Skip initial HTML comment header and metadata until first heading
    idx = 0
    while idx < len(lines) and not HEADING_RE.match(lines[idx]):
        idx += 1

    stack: List[Section] = []
    roots: List[Section] = []
    anchor_map: Dict[str, Section] = {}

    in_fence = False
    fence_lang: Optional[str] = None
    fence_lines: List[str] = []
    current: Optional[Section] = None

    def push_section(sec: Section) -> None:
        nonlocal stack, roots, current
        # Assign path
        sec.path = [*(stack[-1].path if stack else []), sec.title]
        # Attach into tree
        if not stack:
            roots.append(sec)
        else:
            stack[-1].children.append(sec)
        stack.append(sec)
        current = sec

    def close_to_level(level: int) -> None:
        nonlocal stack, current
        while stack and stack[-1].level >= level:
            stack.pop()
        current = stack[-1] if stack else None

    # Main parse loop
    i = idx
    while i < len(lines):
        line = lines[i]

        # code fence open/close
        if not in_fence:
            m_open = FENCE_OPEN_RE.match(line)
            if m_open:
                in_fence = True
                fence_lang = m_open.group('lang')
                fence_lines = []
                i += 1
                continue
        else:
            if FENCE_CLOSE_RE.match(line):
                # close fence
                if current is not None:
                    current.code_blocks.append(CodeBlock(lang=fence_lang, content="\n".join(fence_lines)))
                in_fence = False
                fence_lang = None
                fence_lines = []
                i += 1
                continue
            fence_lines.append(line)
            i += 1
            continue

        # heading
        m_h = HEADING_RE.match(line)
        if m_h:
            level = len(m_h.group('hashes'))
            title = m_h.group('title').strip()
            # Close to parent of lower level
            close_to_level(level)
            sec = Section(level=level, title=title)
            push_section(sec)

            # Try capture anchor on next line if present
            if i + 1 < len(lines):
                m_a = ANCHOR_RE.match(lines[i + 1])
                if m_a:
                    sec.anchor = m_a.group('id')
                    anchor_map[sec.anchor] = sec
                    i += 1  # consume anchor line
            i += 1
            continue

        # anchor line standing alone (rare)
        m_a = ANCHOR_RE.match(line)
        if m_a and current is not None and current.anchor is None:
            current.anchor = m_a.group('id')
            anchor_map[current.anchor] = current
            i += 1
            continue

        # bullets
        m_b = BULLET_RE.match(line) or NUM_BULLET_RE.match(line)
        if m_b and current is not None:
            current.bullets.append(m_b.group('text').strip())
            i += 1
            continue

        # default: content
        if current is not None:
            current.content.append(line)
        i += 1

    return roots, anchor_map


def flatten_sections(secs: List[Section]) -> List[Section]:
    out: List[Section] = []
    def rec(s: Section):
        out.append(s)
        for c in s.children:
            rec(c)
    for s in secs:
        rec(s)
    return out


def tokenize(text: str) -> List[str]:
    toks = re.split(r"[^a-zA-Z0-9]+", text.lower())
    return [t for t in toks if len(t) >= 3]


def build_index(roots: List[Section]) -> Dict:
    flat = flatten_sections(roots)
    # Anchors map
    anchors: Dict[str, str] = {}
    for s in flat:
        if s.anchor:
            anchors[s.anchor] = " > ".join(s.path)

    # Keyword inverted index (simple)
    inverted: Dict[str, List[str]] = {}
    def add_term(term: str, anchor: Optional[str]):
        if not anchor:
            return
        inverted.setdefault(term, [])
        if anchor not in inverted[term]:
            inverted[term].append(anchor)

    for s in flat:
        anchor = s.anchor
        for chunk in [s.title] + s.bullets + ["\n".join(s.content)]:
            for t in tokenize(chunk):
                add_term(t, anchor)

    # Heuristic extraction
    def is_tool_section(title: str) -> bool:
        t = title.lower()
        return 'tool' in t or 'agentic' in t

    def is_checklist(title: str) -> bool:
        t = title.lower()
        return 'checklist' in t or 'quick checklist' in t

    def is_rules(title: str) -> bool:
        t = title.lower()
        return 'rule' in t or 'guideline' in t or 'principle' in t

    extracted = {
        "checklists": [],
        "rules": [],
        "tools": [],
    }

    for s in flat:
        if is_checklist(s.title):
            extracted["checklists"].append({
                "path": " > ".join(s.path),
                "anchor": s.anchor,
                "bullets": s.bullets,
            })
        if is_rules(s.title):
            if s.bullets:
                extracted["rules"].append({
                    "path": " > ".join(s.path),
                    "anchor": s.anchor,
                    "bullets": s.bullets,
                })
        if is_tool_section(s.title):
            if s.bullets or s.code_blocks:
                extracted["tools"].append({
                    "path": " > ".join(s.path),
                    "anchor": s.anchor,
                    "bullets": s.bullets,
                    "code_blocks": [dataclasses.asdict(cb) for cb in s.code_blocks],
                })

    stats = {
        "sections": len(flat),
        "with_anchor": sum(1 for s in flat if s.anchor),
        "bullets": sum(len(s.bullets) for s in flat),
        "code_blocks": sum(len(s.code_blocks) for s in flat),
        "depth_max": max((len(s.path) for s in flat), default=0),
    }

    return {
        "title": "AGENTS",
        "stats": stats,
        "anchors": anchors,
        "sections": [s.to_dict() for s in roots],
        "extracted": extracted,
    }


def print_section(sec: Section) -> None:
    print(f"# Level {sec.level} | {' > '.join(sec.path)}")
    if sec.anchor:
        print(f"Anchor: #{sec.anchor}")
    if sec.bullets:
        print("- Bullets:")
        for b in sec.bullets:
            print(f"  - {b}")
    if sec.code_blocks:
        print(f"- Code blocks: {len(sec.code_blocks)}")
    text = "\n".join(sec.content).strip()
    if text:
        print(f"\n{text[:400]}{'...' if len(text) > 400 else ''}")


def cmd_index(ns: argparse.Namespace) -> int:
    src = ns.source
    if not src.exists():
        print(f"Source not found: {src}")
        return 2
    roots, _ = parse_agents_md(src)
    index = build_index(roots)
    out = json.dumps(index, ensure_ascii=False, indent=2)
    Path(ns.dest).write_text(out, encoding="utf-8")
    print(f"Indexed {src} → {ns.dest}")
    print(f"Sections: {index['stats']['sections']}, Bullets: {index['stats']['bullets']}")
    return 0


def find_by_path(roots: List[Section], path: str) -> Optional[Section]:
    parts = [p.strip() for p in path.split('>')]
    cur = roots
    node: Optional[Section] = None
    for part in parts:
        found = None
        for s in cur:
            if s.title.strip().lower() == part.strip().lower():
                found = s
                break
        if not found:
            return None
        node = found
        cur = node.children
    return node


def cmd_query(ns: argparse.Namespace) -> int:
    src = ns.source
    if not src.exists():
        print(f"Source not found: {src}")
        return 2
    roots, anchors = parse_agents_md(src)

    if ns.path:
        sec = find_by_path(roots, ns.path)
        if not sec:
            print(f"Section not found by path: {ns.path}")
            return 3
        print_section(sec)
        return 0

    if ns.anchor:
        sec = anchors.get(ns.anchor)
        if not sec:
            print(f"Section not found by anchor: {ns.anchor}")
            return 3
        print_section(sec)
        return 0

    if ns.search:
        # Simple substring & token match on titles and bullets
        q = ns.search.lower()
        candidates: List[Tuple[int, Section]] = []
        flat = flatten_sections(roots)
        for s in flat:
            score = 0
            if q in s.title.lower():
                score += 5
            score += sum(1 for b in s.bullets if q in b.lower())
            if score > 0:
                candidates.append((score, s))
        candidates.sort(key=lambda t: (-t[0], len(t[1].path)))
        for score, s in candidates[: ns.limit or 10]:
            print(f"[{score}] {' > '.join(s.path)}  #{s.anchor or ''}")
        if not candidates:
            print("No matches.")
        return 0

    # Default: print top-level sections
    for s in roots:
        print(f"- {' > '.join(s.path)}  #{s.anchor or ''}")
    return 0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Parse and index AGENTS.md for Codex CLI consumption")
    sub = p.add_subparsers(dest='cmd', required=True)

    # common
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--source', type=Path, default=Path('../AGENTS.md'), help='Path to AGENTS.md')

    i = sub.add_parser('index', parents=[common], help='Build structured JSON index from AGENTS.md')
    i.add_argument('--dest', type=Path, default=Path('./AGENTS_INDEX.json'), help='Destination JSON path')

    q = sub.add_parser('query', parents=[common], help='Query sections by path/anchor/search')
    q.add_argument('--path', type=str, help='Section path, e.g., "GOLDEN RULES > LANGUAGE RULES"')
    q.add_argument('--anchor', type=str, help='Section anchor id')
    q.add_argument('--search', type=str, help='Keyword search over titles and bullets')
    q.add_argument('--limit', type=int, default=10)

    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ns = parse_args(argv)
    if ns.cmd == 'index':
        return cmd_index(ns)
    if ns.cmd == 'query':
        return cmd_query(ns)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
