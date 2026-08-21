# llm-wiki

<p align="center">
  <img src="assets/logo.svg" alt="llm-wiki" width="480" /><br />
  <sub>Personal knowledge base that evolves with you</sub>
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

## Usage

Day to day you talk to an AI agent, not to the CLI. Copy the skill into your agent's skill directory once:

```bash
cp -r skills/llm-wiki /path/to/project/.claude/skills/
```

`.claude/skills/` is supported by most AI agents (Claude Code, OpenCode, Cursor, etc.). If your agent expects another location, move it there.

<p align="center">
  <img src="assets/flow.svg" alt="wiki-flow" width="600" /><br />
</p>

### 1. Create a New Wiki (INIT)

Tell the agent:

```
Init a wiki at ~/wikis/greek-history for Greek history
```

The agent will:
- Run `lwiki init` to scaffold the OKF bundle (see [The Bundle Layout](#the-bundle-layout))
- Generate `AGENTS.md` (your domain schema), `CLAUDE.md`, `README.md`, and the starter `index.md` / `log.md` / `overview.md`
- Create the empty `raw/`, `summaries/`, `concepts/`, `entities/`, and `insights/` directories, and an initial `raw/files.log`

### 2. Add Sources (INGEST)

#### Option A: Files

Move source files (PDF, Markdown, etc.) into `~/wikis/greek-history/raw/`, then tell the agent:

```
Ingest all new sources in raw/
```

#### Option B: Paste content directly

```
Add this to the wiki:
<paste article text or URL>
```

#### What happens during ingest

The agent will:
1. Read each source in full
2. Create or update pages in `summaries/`, `concepts/`, `entities/`
3. Run a backlink audit — add markdown links across existing pages
4. Scan the whole bundle for pages affected by the new information (cascade update)
5. Update `index.md`, `overview.md`, and `log.md`
6. Sync `raw/files.log` via `lwiki raw sync`

**Note:** the agent proceeds autonomously. It only asks you when something is genuinely unclear (ambiguous facts, conflicting sources it can't resolve).

### 3. Ask Questions (QUERY)

```
What do we know about the Peloponnesian War?
```

```
Compare Athenian and Spartan military strategies across all sources
```

```
What are the unresolved questions about the fall of Mycenaean civilization?
```

The agent answers strictly from bundle content, citing pages with markdown links. After answering, it may:
- **Offer to save** the analysis as an insight page (if the answer has standalone value)
- **Report issues** found in existing pages (outdated info, contradictions) and ask if you want to fix them

### 4. Update Pages (UPDATE)

#### User-triggered (you ask for changes)

```
Update concepts/democracy.md — the latest source says X
```

```
Fix the contradiction between concepts/oligarchy.md and concepts/democracy.md
```

The agent shows a diff for each page and waits for your confirmation before writing.

#### Agent-triggered (during ingest)

When new sources affect existing pages, the agent updates them automatically if the change is straightforward. It asks you only for uncertain or meaning-altering changes.

### 5. Health Check (LINT)

```
Lint the wiki
```

The agent runs `lwiki validate` for OKF 0.2 conformance and then checks:

| Category | Auto-fixed? | Examples |
|----------|-------------|---------|
| **Deterministic** | Yes | Conformance errors, leftover `[[wikilinks]]`, dead `sources:` paths, index inconsistencies |
| **Heuristic** | No — reports only | Contradictions, stale claims, orphan pages, missing cross-references, stale insights |

It writes a lint report to `insights/lint-<date>.md` and offers fixes for the heuristic issues.

### 6. Check for New Sources (Drift Detection)

```
Any new files in raw/?
```

Or run directly:

```bash
lwiki raw status    # report only
lwiki raw sync      # update files.log
```

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