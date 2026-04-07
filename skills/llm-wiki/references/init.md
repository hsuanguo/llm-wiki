# INIT — Bootstrap a New Wiki

## When to Run

User says "init wiki", "create a knowledge base", or similar. Also runs automatically if INGEST is triggered but no wiki structure exists.

## Process

### 1. Gather Configuration

Ask one question at a time (or infer from context):

1. **Where should the wiki live?** (path relative to vault, e.g., `wiki/ai-agents`)
2. **What is the domain/purpose?** (one sentence — maps to `lwiki init --domain`)
3. *(Optional)* **What types of sources will you add?** If the user does not care, skip this: the CLI defaults to **articles, URLs, papers** in **`AGENTS.md`** (`--sources`).

### 2. Create Directory Structure

**Required:** the tree must match **`lwiki structure`** exactly. Run that command and follow it; do not improvise folders or mirror an outdated ASCII diagram from this file.

Bootstrap with **`lwiki init`**. If the **`lwiki`** command is not available, ask the user to install it, then retry. Minimal invocation:

`lwiki init <wiki-root> --domain "<one-sentence purpose>"`

Add **`--sources "..."`** only when the user specified source types in step 3; otherwise omit it and the defaults apply.

That command creates the directories, **`AGENTS.md`** (domain schema), a thin **`CLAUDE.md`** that imports `@AGENTS.md` per [Claude Code AGENTS.md](https://code.claude.com/docs/en/memory#agents-md), **`wiki/index.md`**, **`wiki/log.md`**, **`wiki/overview.md`**, runs an initial **`lwiki raw sync`**, and does not require hand-writing the files below.

### 3. Starter Files (AGENTS.md, CLAUDE.md, index, log, overview)

**Implemented by `lwiki init`** — same content shapes as this skill and [templates/index.md](../templates/index.md):

- **`AGENTS.md`** — `# <Domain> Wiki Schema` with **Domain**, **Source Types** (from `--sources` or default), and **Conventions** (frontmatter, wikilinks, immutable `raw/`, append-only `log.md`, co-evolving schema). This is the file to edit for schema changes (also consumed by other agents).
- **`CLAUDE.md`** — Fixed stub: `@AGENTS.md` plus a short **LLM Wiki (Claude Code)** note so Claude Code loads the same instructions without duplicating them.
- **`wiki/index.md`** — empty tables per category (Summaries, Concepts, Entities, Insights).
- **`wiki/log.md`** — header + first `## [date] init | <domain>` entry.
- **`wiki/overview.md`** — frontmatter + empty “Current Understanding” / “Open Questions” sections.

Edit **AGENTS.md** (and only adjust **CLAUDE.md** for Claude-specific add-ons). If `lwiki` could not be run (rare), follow the same two-file pattern by hand.

### 4. Initialize raw/files.log

**Required:** with **wiki root as cwd**, run:

`lwiki raw sync`

That creates or refreshes `raw/files.log`. If `raw/` already has files before sync, report them and ask whether to ingest.

`lwiki init` already performs an initial `raw sync` after creating the tree.

### 5. Multi-Wiki Setup

If the user has multiple wikis under a parent directory (e.g., `wiki/`):
- Suggest a shared **`AGENTS.md`** (or shared snippets imported into each wiki) for common conventions
- Each wiki gets its own **`AGENTS.md`** for domain-specific schema and a **`CLAUDE.md`** stub that imports it
- [Claude Code](https://code.claude.com/docs/en/memory) walks up the tree loading `CLAUDE.md` / `CLAUDE.local.md`; keep wiki roots consistent so imports resolve
