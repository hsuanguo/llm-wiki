# llm-wiki

<p align="center">
  <img src="assets/logo.svg" alt="llm-wiki" width="480" /><br />
  <sub>OKF 0.2 native knowledge bundle that evolves with you</sub>
</p>

An OKF-native personal knowledge base inspired by [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). The bundle IS the wiki — no separate "export" step.

[Chinese](README.zh-CN.md)

This repo ships two things:

| What | Path | Purpose |
|------|------|---------|
| **Skill** | `skills/llm-wiki/` | Agent skill (Claude Code / Cursor / Copilot) — INIT, INGEST, QUERY, UPDATE, LINT |
| **CLI** | `lwiki/` | Python CLI — init OKF bundles, track `raw/` drift, validate, migrate |

## Quick Start

```bash
# 1. Requirements
uv --version || curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install the CLI
uv tool install https://github.com/hsuanguo/llm-wiki.git

# 3. Bootstrap a new bundle
lwiki init ~/wikis/greek-history --domain "Greek history" --sources "articles, papers"

# 4. Browse / edit in the browser
lwiki serve --root ~/wikis
# open http://127.0.0.1:8765

# 5. Validate OKF 0.2 conformance
cd ~/wikis/greek-history && lwiki validate
```

## The Bundle Layout

`lwiki init` scaffolds an OKF 0.2 bundle — the bundle IS the wiki:

```
my-wiki/
├── index.md          # declares okf_version: "0.2"
├── log.md            # append-only operation log
├── overview.md       # top-level concept (OKF frontmatter)
├── AGENTS.md         # local conventions
├── CLAUDE.md         # thin stub: @AGENTS.md for Claude Code
├── README.md         # pointer doc
├── summaries/        # source summaries
├── concepts/         # concept pages
├── entities/         # entity pages (people, tools, orgs, products)
├── insights/         # syntheses and cross-page analyses
└── raw/              # immutable sources, tracked by raw/files.log
```

There is no `wiki/` wrapper. The bundle is the wiki.

## OKF 0.2 Frontmatter

Only `|type` is strictly required. The rest is recommended.

| Tier | Fields |
|------|--------|
| **Required** | `type` (`summary`, `concept`, `entity`, `insight`, `overview`, `attested-computation`) |
| **Recommended** | `title`, `description`, `tags`, `generated: { by, at }`, `status` |
| **Optional** | `resource` (canonical URI), `sources` (list of credibility-shaped entries), `verified` (audit trail), `usage_window` |

OKF provenance replaces the legacy wiki-internal `updated:`, `sources: [paths]`, and `cited:` fields.

## The Daily Workflow

| You do | AI does |
|--------|---------|
| Drop source files in `raw/` | Ingest, summarise, cross-reference |
| Ask questions | Answer from the bundle; cite with markdown links; optionally save an insight |
| Say "lint" | Conformance check + heuristic health report |
| Browse in the browser | `lwiki serve` |
| Convert an old Obsidian-shaped wiki | `lwiki migrate <old> --out <new>` |

## Migrating from the Legacy Wiki (0.1.x → 2.0)

If you have an existing wiki with a `wiki/` wrapper and `[[wikilinks]]`:

```bash
lwiki migrate ~/old-wiki --out ~/new-bundle
# the source wiki is untouched; the bundle is emitted alongside
# all frontmatter is migrated to OKF 0.2; [[wikilinks]] are rewritten to markdown links
```

After migration, `lwiki validate ~/new-bundle` confirms OKF 0.2 conformance.

## CLI Reference

| Command | Purpose |
|---------|---------|
| `lwiki init <dir> --domain "..."` | Scaffold an OKF bundle |
| `lwiki structure` | Print the canonical bundle layout |
| `lwiki validate <dir>` | Check OKF 0.2 conformance |
| `lwiki serve --root <parent>` | Web UI over all bundles under `<parent>` |
| `lwiki raw sync` / `lwiki raw status` | Track `raw/files.log` |
| `lwiki migrate <old> --out <new>` | Convert a legacy wiki to an OKF bundle |
| `lwiki export okf <bundle>` | Verify conformance (alias for `lwiki validate`) |

## License

[MIT](LICENSE)