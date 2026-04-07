"""Canonical wiki directory layout (INIT). Kept in sync with the wiki skill SKILL.md."""

# Authoritative tree — update here and in skills/llm-wiki/SKILL.md if layout changes.
CANONICAL_WIKI_TREE = """<wiki-root>/
├── AGENTS.md              # Domain schema (editable; shared with non-Claude agents)
├── CLAUDE.md              # Imports @AGENTS.md for Claude Code (keep thin; fixed stub from lwiki init)
├── assets/                # Attachments (images, PDFs) — self-contained
├── raw/                   # Immutable source documents (LLM reads, never modifies)
│   ├── files.log          # Auto-generated file tracking (name + sha256)
│   └── ...
└── wiki/
    ├── index.md           # Content catalog — every page with link + one-line summary
    ├── log.md             # Append-only chronological operation log
    ├── overview.md        # High-level evolving synthesis across all sources
    ├── summaries/         # Source summaries (can merge multiple raw files on same topic)
    ├── concepts/          # Concept pages
    ├── entities/          # Entity pages (people, tools, orgs, products)
    └── insights/          # Valuable query results and cross-page analyses
"""


def render_structure_text() -> str:
    """Full text for `lwiki structure` (tree + required commands)."""
    return f"""{CANONICAL_WIKI_TREE}
Commands (install the `lwiki` CLI if missing):
  lwiki init <wiki-root> --domain \"...\" --sources \"...\"   create this layout + initial raw/files.log
  lwiki raw sync                                            from wiki root: refresh raw/files.log
  lwiki raw status                                          from wiki root: report drift (no write)
"""


def render_structure_compact() -> str:
    """Tree only (for tests or embedding)."""
    return CANONICAL_WIKI_TREE.strip()
