"""Create a new wiki directory tree (LLM Wiki INIT)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

# Default for AGENTS.md "Source Types" when `lwiki init` is run without `--sources`.
DEFAULT_SOURCE_TYPES = "articles, URLs, papers"

# Thin CLAUDE.md for Claude Code: imports AGENTS.md (see https://code.claude.com/docs/en/memory#agents-md).
CLAUDE_MD_STUB = """@AGENTS.md

## LLM Wiki (Claude Code)

Domain schema and conventions live in **AGENTS.md** (co-edited with the wiki). This file is fixed: edit `AGENTS.md` to change rules; keep the `@AGENTS.md` import so Claude Code loads the same content as other agents.
"""


def wiki_markers_exist(wiki_root: Path) -> bool:
    return (wiki_root / "wiki" / "index.md").is_file() and (wiki_root / "wiki" / "log.md").is_file()


def render_agents_md(domain: str, source_types: str) -> str:
    """Wiki domain schema — primary file for humans and agent-agnostic tooling."""
    return f"""# {domain} Wiki Schema

## Domain
{domain}

## Source Types
{source_types}

## Conventions

### Frontmatter contract

Wiki pages use YAML frontmatter. Fields are tiered; only the required tier
must be present on every page, the rest is soft guidance (similar to the
OKF permissive conformance model).

| Tier | Fields |
|------|--------|
| **Required** | `title`, `type`, `description`, `updated` |
| **Recommended** | `tags`, `sources` |
| **Optional** | `resource` (canonical URI for the underlying asset), `cited` (insight pages only — list of wiki page slugs cited) |

`type` is the only field consumers use for routing. Pick descriptive,
self-explanatory values (the standard set is `summary`, `concept`, `entity`,
`insight`, `overview`); consumers MUST tolerate unknown values gracefully.

### Other rules

- Cross-references use [[wikilinks]] with plain filenames (no paths)
- raw/ is immutable — never modify source documents
- log.md is append-only
- Forward references (`[[not-yet-written]]`) are tolerated — the backlink
  audit and cascade update will resolve them
- This schema co-evolves with use — suggest changes when conventions need updating
"""


def render_index_md(domain: str) -> str:
    return f"""# Wiki Index — {domain}

## Summaries

| Page | Summary | Updated |
|------|---------|---------|

## Concepts

| Page | Summary | Updated |
|------|---------|---------|

## Entities

| Page | Summary | Updated |
|------|---------|---------|

## Insights

| Page | Summary | Updated |
|------|---------|---------|
"""


def render_log_md(today: str, domain: str) -> str:
    return f"""# Wiki Log

Append-only. Format: `## [YYYY-MM-DD] <operation> | <title>`
Quick view: `grep "^## \\[" log.md | tail -10`

---

## [{today}] init | {domain}
"""


def render_overview_md(domain: str, today: str) -> str:
    return f"""---
title: Overview
type: overview
description: High-level synthesis across all sources — what we know about {domain} right now.
tags: [overview, synthesis]
sources: []
updated: {today}
---

# {domain} — Overview

> Evolving synthesis across all sources. Updated on each ingest.

## Current Understanding

*No sources ingested yet.*

## Open Questions

*Add questions here as they arise.*

## Key Entities / Concepts

*Populated as pages as they are created.*
"""


def init_wiki_tree(
    wiki_root: Path,
    *,
    domain: str,
    source_types: str,
    force: bool,
) -> None:
    """
    Create wiki layout under wiki_root. Aligns with skills/llm-wiki INIT references.
    Raises FileExistsError if wiki exists and force is False.
    """
    wiki_root = wiki_root.resolve()
    if wiki_markers_exist(wiki_root) and not force:
        raise FileExistsError(
            f"Wiki already exists at {wiki_root} (found wiki/index.md and wiki/log.md). "
            "Use --force to overwrite."
        )

    today = date.today().isoformat()

    (wiki_root / "assets").mkdir(parents=True, exist_ok=True)
    (wiki_root / "raw").mkdir(parents=True, exist_ok=True)
    for sub in ("summaries", "concepts", "entities", "insights"):
        (wiki_root / "wiki" / sub).mkdir(parents=True, exist_ok=True)

    (wiki_root / "AGENTS.md").write_text(render_agents_md(domain, source_types), encoding="utf-8")
    (wiki_root / "CLAUDE.md").write_text(CLAUDE_MD_STUB, encoding="utf-8")
    (wiki_root / "wiki" / "index.md").write_text(render_index_md(domain), encoding="utf-8")
    (wiki_root / "wiki" / "log.md").write_text(render_log_md(today, domain), encoding="utf-8")
    (wiki_root / "wiki" / "overview.md").write_text(
        render_overview_md(domain, today), encoding="utf-8"
    )
