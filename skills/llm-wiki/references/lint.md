# LINT — Bundle Health Check

## When to Run

User says "lint", "check the bundle", "any gaps?", or after a substantive ingest / update.

## Process

### 1. Conformance Check

Run **`lwiki validate`** from the bundle root. The CLI wraps `lwiki.conformance.validate_bundle` and reports:

- Bundle-root `index.md` missing or `okf_version` absent
- Concept files with missing / unparseable frontmatter
- Concept files with empty or unknown `type`
- `generated.{by,at}` shape, `sources` shape, `verified` shape, `status` enum, attested-computation keys
- Reserved filenames (`index.md`, `log.md`) outside the bundle root
- Legacy `wiki/` wrapper with concept subdirs (rejected after migration)

Errors are non-negotiable — fix them before proceeding. Warnings and info items are noted in the report but not blockers.

### 2. Optional: Raw Drift

Run **`lwiki raw status`** to check whether `raw/` files have changed since `raw/files.log` was last synced. If drift is reported, the user can choose to:

- Run **`lwiki raw sync`** to refresh `files.log` (no source re-ingest)
- Run a targeted **INGEST** on the changed files

### 3. Heuristic Issues

These aren't caught by the conformance validator. Walk the bundle and look for:

| Category | Examples |
|----------|----------|
| Contradictions | Two pages disagree on a fact; cross-link them in `## See Also` and add a conflict note |
| Stale claims | `generated.at` is more than ~6 months old and a relevant newer source is missing → propose an INGEST |
| Orphan pages | A concept with no incoming links from any other concept → search the bundle for natural cross-references |
| Missing cross-references | A new concept that should link to existing ones but doesn't → backlink audit |
| Stale insights | Insight pages older than 6 months with outdated "current understanding" → propose a re-run |

Write the lint report to `insights/lint-<date>.md` so the user can scan it later. Use [templates/insight.md](../templates/insight.md) as the shape; tag it with `type: insight` and a topic tag of `lint`.

### 4. Suggest Fixes

Heuristic findings are **reports, not auto-fixes**. After writing the lint page, summarise each finding as a one-line actionable suggestion in your reply, and ask whether the user wants any of them applied via UPDATE.

### 5. Report to User

- Conformance summary: errors / warnings / info counts (from `lwiki validate`)
- Drift summary: new / modified / deleted file counts (from `lwiki raw status`)
- Heuristic findings: list of contradictions, staleness, orphans, missing cross-refs
- Lint page path so the user can re-read it
- Proposed next actions (none applied)