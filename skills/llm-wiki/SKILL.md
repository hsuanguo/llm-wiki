---
name: llm-wiki
description: "Use this skill whenever work is wiki- or knowledge-base-shaped — especially if the user says wiki, knowledge base, vault, bundle, OKF, or raw/ in this project. Trigger on words such as `init wiki`, `add to wiki`, `ingest wiki`, or `lint wiki`, updating or revising wiki pages, and on domain-specific questions that should be answered from the wiki (what we know about X, compare A and B, gaps, contradictions) — not off-wiki trivia. Do not use for generic chat, unrelated code or tooling, or file operations with no wiki intent."
metadata:
  author: hsuanguo
  version: "0.2"
---

# LLM Wiki

An OKF native knowledge bundle that evolves with you. The bundle IS the wiki — there is no separate "export" step. Authoring goes straight into the bundle; consumers (this skill, the CLI, the web UI, OKF readers) all see the same files.

Inspired by [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## How to work

Use two phases: **(1) gather context**, **(2) map the request into steps** — each step is one operation with a dedicated reference file. Read that reference *before* executing the step.

### 1. Gather context

Infer **intent** from the user's message (bootstrap, ingest, answer from the bundle, revise pages, lint, etc.) and **state** from the bundle:

- Whether a bundle already exists at the target root (`index.md` declares `okf_version: "0.2"`).
- If it exists: skim `index.md`, tail `log.md`, and inspect `raw/` when ingest, drift, or new sources matter.
- If uncertain about what a bundle looks like, run **`lwiki structure`** to get the information.

### 2. Map intention to one or more steps

Decompose the request into an **ordered list of steps**. Each step = a single primary operation. **Open the matching reference for every step** you will run; do not rely on memory alone.

| Operation | Typical trigger | Reference |
|-----------|-----------------|-----------|
| **INIT** | No bundle yet; user wants a new knowledge base | [references/init.md](references/init.md) |
| **INGEST** | New or changed files in `raw/`, pasted content, or URL to add | [references/ingest.md](references/ingest.md) |
| **QUERY** | Question that should be answered **from bundle pages**, not general knowledge | [references/query.md](references/query.md) |
| **UPDATE** | User wants edits, corrections, or merges on existing pages | [references/update.md](references/update.md) |
| **LINT** | "Lint", health check, gaps, inconsistencies, optional raw vs `raw/files.log` drift | [references/lint.md](references/lint.md) |

One message can imply several steps (e.g. INGEST then LINT). Order them sensibly — often INIT first if missing, then INGEST / UPDATE / QUERY, and LINT when checking health after substantive changes.

### Routing hint

```
bundle root index.md declares okf_version: "0.2"?
├─ No → INIT → references/init.md
├─ Yes →
│   ├─ New/changed raw/, or paste/URL to capture? → INGEST → references/ingest.md
│   ├─ Domain question grounded in the bundle? → QUERY → references/query.md
│   ├─ "lint" / health check / find gaps? → LINT → references/lint.md
│   ├─ Revise or correct existing pages? → UPDATE → references/update.md
│   └─ Paste or URL only? → save under raw/, then INGEST → references/ingest.md
```

## Bundle Structure

**Authoritative layout** is whatever **`lwiki structure`** prints. Run that command and treat the output as the single source of truth for INIT and whenever you need to understand the bundle structure; do not invent alternate directory trees or maintain a parallel diagram in prose.

At a glance: `<bundle>/` has **`index.md`** (declares `okf_version: "0.2"`), **`log.md`** (append-only), **`overview.md`** (top-level concept), **`AGENTS.md`** (local conventions, editable), **`CLAUDE.md`** (thin `@AGENTS.md` import for Claude Code), `raw/` (immutable sources tracked by `raw/files.log`), and concept subdirs `summaries/`, `concepts/`, `entities/`, `insights/`. There is no `wiki/` wrapper.

## Tooling (required)

All structural operations use the **`lwiki`** CLI. Never hand-edit `files.log` or create dirs manually.

| Action | Command (bundle root as cwd unless noted) |
|--------|------------------------------------------|
| Show canonical tree | `lwiki structure` |
| Bootstrap files + dirs | `lwiki init <bundle-root> --domain "..." --sources "..."` |
| Refresh `raw/files.log` | `lwiki raw sync` (or `lwiki checkout`) |
| Report drift (no write) | `lwiki raw status` |
| Check OKF 0.2 conformance | `lwiki validate` |
| Browse / edit in browser | `lwiki serve --root <parent-of-bundles>` |
| Convert a legacy Obsidian-shaped wiki | `lwiki migrate <old-wiki> --out <new-bundle>` |
| Rewrite legacy `[[wikilinks]]` in place | `lwiki.wikilink_rewrite.rewrite_bundle(bundle_dir: Path, *, absolute_links=False, write=True)` (Python API; both kwargs optional) |

## Page Conventions

Page templates are in `templates/` — read the relevant template before creating a new page:
- [templates/summary.md](templates/summary.md) — source summaries
- [templates/concept.md](templates/concept.md) — concept pages
- [templates/entity.md](templates/entity.md) — entity pages
- [templates/insight.md](templates/insight.md) — insights (point-in-time snapshots, NOT cascade-updated)
- [templates/attested-computation.md](templates/attested-computation.md) — OKF 0.2 attested computations (OKF §4.2)
- [templates/root-index.md](templates/root-index.md) — bundle-root `index.md` (frontmatter `okf_version`)
- [templates/directory-index.md](templates/directory-index.md) — per-directory index (`summaries/index.md`, `concepts/index.md`, etc.)

Common rules:
- Every page carries frontmatter with at minimum `type`. The OKF permissive contract: only `type` is required; `title`, `description`, `tags`, `generated: { by, at }`, `status` are recommended; `resource`, `sources` (credibility-shaped), `verified` (audit trail), `usage_window` are optional.
- Cross-references are **standard markdown links** `[label](path)` — file-relative (`../entities/foo.md`) or bundle-root-absolute (`/entities/foo.md`). **No `[[wikilinks]]`** in new content; the legacy form is auto-rewritten on migration.
- `generated.at` records the last change; `generated.by` is the actor (`<name>/<version>` for agents, `human:<id>` for people, `process:<id>` for automated processes).
- `status` is `draft | stable | deprecated`. Default `draft` for new pages; flip to `stable` once the content has been reviewed.
- Start every page with a 1-2 sentence summary in the body (frontmatter `description` is the structured form of the same idea).
- Every page ends with a `## See Also` section for cross-references.
- Insight pages add a `## Citations` section for external sources (URLs, DOIs).
- Slugs: lowercase, hyphen-separated (e.g., `attention-mechanism.md`).
- Raw files: no date prefix in filename; dates tracked via frontmatter.
- Forward references to not-yet-written pages are tolerated — the backlink audit and cascade update will resolve them.

## Key Rules

1. **LLM writes bundle pages; human curates sources and asks questions**
2. **raw/ is immutable** — never modify
3. **Log and index only on bundle file changes** — no-op queries don't write anything
4. **Ask only when uncertain** — proceed autonomously; escalate when facts are ambiguous, sources conflict, or a change would alter meaning
5. **Pages are not bound to raw files** — LLM determines relevance across the entire bundle
6. **Backlink audit on every ingest** — scan all pages for missing links to new content
7. **Insights are snapshots** — not cascade-updated; add reverse links in See Also (markdown links, not Obsidian backlinks)
8. **Schema co-evolves** — suggest `AGENTS.md` changes; user confirms; log records
9. **Use lwiki CLI** for INIT, structure, raw/files.log, validate — see Tooling

## Tips for Users

Surface these to the user when relevant (e.g., during INIT, first ingest, or when they ask for help):

- **Obsidian Web Clipper** browser extension is the best way to capture web articles — bypasses anti-scraping etc.
- **`lwiki serve`** runs a zero-dep web UI over the same bundle — handy when you want to browse or edit without launching a separate tool.
- **`lwiki validate`** checks OKF 0.2 conformance; wire it into CI before publishing a bundle.
- You never write bundle pages yourself — AI handles all the maintenance.
