"""Scaffold a new OKF 0.2 bundle (``lwiki init``).

The on-disk shape is a single OKF bundle — no ``wiki/`` wrapper.
Conventions are documented in ``AGENTS.md`` at the bundle root, and
``raw/files.log`` is created so drift tracking works on day one.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .okf_export import OKF_VERSION
from .raw_tracker import run_raw_sync

# Default for AGENTS.md "Source Types" when `lwiki init` is run without `--sources`.
DEFAULT_SOURCE_TYPES = "articles, URLs, papers"

# Generator identifier for OKF 0.2 ``generated.by`` on scaffolded pages.
GENERATED_BY = f"lwiki/{OKF_VERSION}"

# Thin CLAUDE.md for Claude Code: imports AGENTS.md so Claude Code loads the
# same OKF-native conventions (per https://code.claude.com/docs/en/memory#agents-md).
CLAUDE_MD_STUB = """@AGENTS.md

## llm-wiki (Claude Code)

This bundle is OKF native. Domain schema, conventions, and the OKF
frontmatter contract live in **AGENTS.md** (co-edited with the bundle).
This file is fixed: edit `AGENTS.md` to change rules; keep the
`@AGENTS.md` import so Claude Code loads the same content as other agents.
"""


def bundle_markers_exist(bundle_root: Path) -> bool:
    """An OKF bundle is initialised when the root index.md declares okf_version."""
    index = bundle_root / "index.md"
    if not index.is_file():
        return False
    text = index.read_text(encoding="utf-8")
    return f"okf_version: {OKF_VERSION!r}" in text or f'okf_version: "{OKF_VERSION}"' in text


def render_agents_md(domain: str, source_types: str) -> str:
    """Wiki domain schema — primary file for humans and agent-agnostic tooling."""
    return f"""# {domain} Wiki Schema

This bundle is OKF native. Every concept file is a self-describing
markdown document with YAML frontmatter; cross-references are standard
markdown links (no `[[wikilinks]]`).

## Domain
{domain}

## Source Types
{source_types}

## Frontmatter contract (OKF 0.2)

Only `type` is strictly required by the OKF spec; the rest is recommended
for a richer authoring experience and round-trips cleanly through the
conformance validator.

| Tier | Fields |
|------|--------|
| **Required** | `type` (one of `summary`, `concept`, `entity`, `insight`, `overview`, `attested-computation`) |
| **Recommended** | `title`, `description`, `tags`, `generated: {{ by, at }}` |
| **Optional** | `resource` (canonical URI), `sources` (list of credibility-shaped entries), `verified` (audit trail), `status` (`draft`/`stable`/`deprecated`), `usage_window` |

OKF provenance (the `sources` list, `verified` audit, `generated` mapping)
replaces the legacy wiki-internal `sources: [paths]`, `cited: [slugs]`,
and `updated:` fields.

## Other rules

- Cross-references use markdown links: `[display](path)` (file-relative or `/`-prefixed). No `[[…]]`.
- `raw/` is immutable — never modify source documents
- `log.md` is append-only
- The OKF-conformant shape means the bundle is the wiki; there is no separate export step
- Forward references are tolerated — the cascade update will resolve them
- This schema co-evolves with use — suggest changes when conventions need updating
"""


def render_root_index_md(domain: str) -> str:
    """Bundle-root index.md — only place frontmatter is permitted in an index."""
    return f"""---
okf_version: '{OKF_VERSION}'
---

# {domain} — Bundle Index

Use the per-directory indexes (`summaries/index.md`, `concepts/index.md`,
`entities/index.md`, `insights/index.md`) to navigate. They are kept in
sync as pages are added or updated.
"""


def render_log_md(today: str, domain: str) -> str:
    return f"""# Bundle Log

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
generated:
  by: {GENERATED_BY}
  at: {today}
status: draft
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


def render_readme(domain: str) -> str:
    return f"""# {domain}

This directory is an [OKF 0.2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
knowledge bundle. Edit it directly — there is no separate "export" step.
The bundle is the wiki.

- `index.md` — bundle root, declares `okf_version`.
- `log.md` — append-only operation log.
- `overview.md` — high-level synthesis.
- `AGENTS.md` — local conventions for humans and agents.
- `summaries/`, `concepts/`, `entities/`, `insights/` — concept pages.
- `raw/` — immutable source files (tracked by `raw/files.log`).

Use `lwiki serve` to browse this bundle in the browser, `lwiki validate`
to check conformance, and `lwiki migrate` to convert an older
Obsidian-shaped wiki into this shape.
"""


def init_wiki_tree(
    bundle_root: Path,
    *,
    domain: str,
    source_types: str,
    force: bool,
) -> None:
    """Create an OKF 0.2 bundle at ``bundle_root``.

    Hard cut from the legacy ``wiki/`` wrapper: concepts live at the bundle
    root, `AGENTS.md` stays at the root, `raw/files.log` is created for
    drift tracking, and the result passes `lwiki.conformance.validate_bundle`.
    """
    bundle_root = bundle_root.resolve()
    if bundle_markers_exist(bundle_root) and not force:
        raise FileExistsError(
            f"Bundle already exists at {bundle_root} (found okf_version in index.md). "
            "Use --force to overwrite."
        )

    bundle_root.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    # Top-level files
    (bundle_root / "index.md").write_text(render_root_index_md(domain), encoding="utf-8")
    (bundle_root / "log.md").write_text(render_log_md(today, domain), encoding="utf-8")
    (bundle_root / "overview.md").write_text(render_overview_md(domain, today), encoding="utf-8")
    (bundle_root / "AGENTS.md").write_text(render_agents_md(domain, source_types), encoding="utf-8")
    (bundle_root / "CLAUDE.md").write_text(CLAUDE_MD_STUB, encoding="utf-8")
    (bundle_root / "README.md").write_text(render_readme(domain), encoding="utf-8")

    # Concept subdirs
    for sub in ("summaries", "concepts", "entities", "insights"):
        (bundle_root / sub).mkdir(parents=True, exist_ok=True)

    # raw/ + files.log
    raw_dir = bundle_root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    run_raw_sync(raw_dir)