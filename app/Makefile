# Simple make targets for building AGENTS.md

PY ?= python3

# Default paths (can be overridden):
SOURCE_DIR ?= ../.codex/rules
ORDER_FILE ?= $(SOURCE_DIR)/AGENTS_ORDER
DEST_FILE  ?= ../AGENTS.md
TOC_DEPTH  ?= 3
MIN_LEVEL  ?= 2

.PHONY: help agents agents-local agents-check

help:
	@echo "make agents         Build AGENTS.md from $(SOURCE_DIR) -> $(DEST_FILE)"
	@echo "make agents-local   Build app/AGENTS.md from .windsurf/rules (preview)"
	@echo "make agents-check   Lint markdown in $(SOURCE_DIR)"
	@echo "make agents-index   Build JSON index from ../AGENTS.md"
	@echo "make agents-index-local Build JSON index from ./AGENTS.md"
	@echo "make agents-all     Build AGENTS.md and its JSON index (root)"
	@echo "make agents-all-local Build AGENTS.md and its JSON index (local preview)"

agents:
	PYTHONPATH=. $(PY) tools/agents_md_builder.py build \
	  --source $(SOURCE_DIR) \
	  --dest $(DEST_FILE) \
	  --order-file $(ORDER_FILE) \
	  --toc-depth $(TOC_DEPTH) \
	  --min-level $(MIN_LEVEL)

agents-local:
	PYTHONPATH=. $(PY) tools/agents_md_builder.py build \
	  --source ./.windsurf/rules \
	  --dest ./AGENTS.md \
	  --toc-depth 3 \
	  --min-level 2

agents-check:
	$(PY) tools/agents_md_builder.py check --source $(SOURCE_DIR)

.PHONY: agents-index agents-index-local

agents-index:
	$(PY) tools/agents_md_parser.py index --source ../AGENTS.md --dest ./AGENTS_INDEX.json

agents-index-local:
	$(PY) tools/agents_md_parser.py index --source ./AGENTS.md --dest ./AGENTS_INDEX.json

.PHONY: agents-all agents-all-local

agents-all: agents agents-index

agents-all-local: agents-local agents-index-local
