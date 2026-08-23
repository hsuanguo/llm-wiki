# INIT — Bootstrap a New Bundle

## When to Run

User says "init wiki", "create a knowledge base", or similar. Also runs automatically if INGEST is triggered but no bundle structure exists.

## Process

### 1. Gather Configuration

Ask one question at a time (or infer from context):

1. **Where should the bundle live?** (path, e.g., `wiki/greek-history`)
2. **What is the domain/purpose?** (one sentence — maps to `lwiki init --domain`)
3. *(Optional)* **What types of sources will you add?** If the user does not care, skip this: the CLI defaults to **articles, URLs, papers** in **`AGENTS.md`** (`--sources`).

### 2. Create the Directory Structure

**Required:** the tree must match **`lwiki structure`** exactly. Run that command and follow it; do not improvise folders or mirror an outdated ASCII diagram from this file.

Bootstrap with **`lwiki init`**. If the **`lwiki`** command is not available, ask the user to install it, then retry. Minimal invocation:

`lwiki init <bundle-root> --domain "<one-sentence purpose>"`

Add **`--sources "..."`** only when the user specified source types in step 3; otherwise omit it and the defaults apply.

That command creates the directories, **`index.md`** (declares `okf_version: "0.2"`), **`log.md`** (first `init` entry), **`overview.md`** (top-level concept), **`AGENTS.md`** (local conventions), **`CLAUDE.md`** (thin `@AGENTS.md` import for Claude Code), **`README.md`** (pointer doc), `summaries/`, `concepts/`, `entities/`, `insights/`, runs an initial **`lwiki raw sync`** to create `raw/files.log`. There is no `wiki/` wrapper.

### 3. Starter Files (AGENTS.md, CLAUDE.md, README, index, log, overview)

**Implemented by `lwiki init`** — same content shapes as this skill and [templates/root-index.md](../templates/root-index.md):

- **`AGENTS.md`** — `# <Domain> Wiki Schema` with **Domain**,** **Source Types** (from `--sources` or default), and **Conventions** (frontmatter contract — required/recommended/optional tiers, OKF fields, no `[[wikilinks]]`, immutable `raw/`, append-only `log.md`, forward-reference tolerance, co-evolving schema). This is the file to edit for schema changes (also consumed by other agents).
- **`CLAUDE.md`** — Fixed stub: `@AGENTS.md` plus a short note so Claude Code loads the same OKF-native conventions.
- **`README.md`** — Short pointer doc that names the bundle as OKF and points to `lwiki serve` / `lwiki validate` / `lwiki migrate`.
- **`index.md`** — frontmatter `okf_version: "0.2"`; the OKF spec reserves frontmatter here and only here.
- **`log.md`** — header + first `## [date] init | <domain>` entry.
- **`overview.md`** — frontmatter (`type: overview`, `generated: { by, at }`, `status: draft`) + empty "Current Understanding" / "Open Questions" sections.

Edit **`AGENTS.md`** (and only adjust **`CLAUDE.md`** for Claude-specific add-ons). If `lwiki` could not be run (rare), follow the same file shapes by hand.

### 4. Initialize raw/files.log

**Required:** with **bundle root as cwd**, run:

`lwiki raw sync`

That creates or refreshes `raw/files.log`. If `raw/` already has files before sync, report them and ask whether to ingest.

`lwiki init` already performs an initial `raw sync` after creating the tree.

### 5. Multi-Bundle Setup

If the user has multiple bundles under a parent directory (e.g., `wiki/`):

- Suggest a shared **`AGENTS.md`** (or shared snippets imported into each bundle) for common conventions
- Each bundle gets its own **`AGENTS.md`** for domain-specific schema and a **`CLAUDE.md`** stub that imports it
- `lwiki serve --root <parent>` browses all bundles in a directory at once
