# Consuming AGENTS.md in Codex CLI

Mục tiêu: đảm bảo Codex CLI có thể hiểu sâu tài liệu `AGENTS.md` theo cấu trúc máy đọc được để áp dụng quy tắc, checklist và định nghĩa công cụ một cách nhất quán.

## Artefacts

- `AGENTS.md`: tài liệu đã hợp nhất và chuẩn hoá.
- `AGENTS_INDEX.json`: chỉ mục JSON có cấu trúc, sinh bởi `tools/agents_md_parser.py`.

Sinh nhanh:
- Local preview: `make agents-all-local` → tạo `app/AGENTS.md` và `app/AGENTS_INDEX.json`.
- Root: `make agents-all` → tạo `../AGENTS.md` và `app/AGENTS_INDEX.json` (đọc từ root).

## JSON Schema (rút gọn)

```jsonc
{
  "title": "AGENTS",
  "stats": { "sections": 76, "with_anchor": 58, "bullets": 323, ... },
  "anchors": { "anchor-id": "Path > To > Section", ... },
  "sections": [
    {
      "level": 2,
      "title": "LANGUAGE RULES",
      "anchor": "golden-rules-language-rules",
      "path": ["AGENTS", "LANGUAGE RULES"],
      "content": "...",
      "bullets": ["..."],
      "code_blocks": [{"lang": "python", "content": "..."}],
      "children": [ ... ]
    }
  ],
  "extracted": {
    "checklists": [ {"path": "...", "anchor": "...", "bullets": ["..."]} ],
    "rules": [ {"path": "...", "anchor": "...", "bullets": ["..."]} ],
    "tools": [ {"path": "...", "anchor": "...", "bullets": ["..."], "code_blocks": [ ... ]} ]
  }
}
```

## Cách tích hợp trong mã Python

- Import trực tiếp và phân tích khi runtime:

```python
from pathlib import Path
from tools.agents_md_parser import parse_agents_md, build_index

roots, anchors = parse_agents_md(Path("./AGENTS.md"))
index = build_index(roots)
# Truy cập các phần quan trọng
rules = index["extracted"]["rules"]
checklists = index["extracted"]["checklists"]
tools = index["extracted"]["tools"]
```

- Hoặc đọc JSON đã sinh sẵn:

```python
import json
index = json.loads(Path("./AGENTS_INDEX.json").read_text(encoding="utf-8"))
# Tìm một mục theo anchor
anchor_map = index["anchors"]
```

## Gợi ý áp dụng trong Codex CLI

- Preambles & Plan: dùng `extracted.rules` và `extracted.checklists` để hiển thị checklist phù hợp theo ngữ cảnh (ví dụ: Tool Preambles, Reasoning Effort).
- Ràng buộc ngôn ngữ: đọc section "LANGUAGE RULES" → enforce phản hồi tiếng Việt + giải thích thuật ngữ Anh.
- Công cụ: đọc section "AGENTIC CODING – TOOL DEFINITIONS" để suy ra hàm/khả năng được phép; hiển thị trợ giúp nhanh khi chọn tool.
- Anchor: khi trích dẫn quy tắc, tham chiếu `#<anchor-id>` để nhảy đến đúng đoạn trong `AGENTS.md`.
- Tìm kiếm: dùng trường `anchors` hoặc xây inverted index riêng nếu cần độ chính xác cao hơn; bản parser đã cung cấp tìm kiếm đơn giản theo tiêu đề/bullets qua lệnh `query`.

## Lệnh CLI hữu ích

- Sinh chỉ mục: `python3 tools/agents_md_parser.py index --source ./AGENTS.md --dest ./AGENTS_INDEX.json`
- Tìm kiếm: `python3 tools/agents_md_parser.py query --source ./AGENTS.md --search "checklist"`
- Xem section: `python3 tools/agents_md_parser.py query --source ./AGENTS.md --path "GOLDEN RULES > LANGUAGE RULES"`

## Bảo trì & Mở rộng

- Parser không phụ thuộc lib ngoài, dễ chỉnh sửa.
- Heuristic nhận diện `tools`, `rules`, `checklists` dựa trên tiêu đề; có thể thêm nhãn (front‑matter hoặc cú pháp) nếu cần chính xác hơn.
- Khi thay đổi cấu trúc `AGENTS.md`, chạy lại `make agents-all(-local)` để cập nhật chỉ mục.

