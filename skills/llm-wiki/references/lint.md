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

### 2. Auto-Fix the Recoverable

Two classes of issue are auto-fixable without user input — both can survive a partial migration, so address them immediately:

- **Broken `[[wikilinks]]`** — leftover from a partial `lwiki migrate`. Run `lwiki wikilink-rewrite <bundle>` (file-relative by default; `--absolute` for the OKF spec-recommended form). Re-run `lwiki validate` to confirm zero ambiguous / unresolved warnings.
- **Broken `sources: [raw/...]` paths** — paths that no longer resolve in `raw/`. Scan the bundle for `sources` entries whose `resource` starts with `raw/` and whose file doesn't exist; remove or update them. (`lwiki raw status` will show raw drift separately; only the OKF `sources` entries pointing at `raw/` are in scope here.)

Report each auto-fix in your reply ("rewrote 4 wikilinks, dropped 2 dead source references").

### 3. Optional: Raw Drift

Run **`lwiki raw status`** to check whether `raw/` files have changed since `raw/files.log` was last synced. If drift is reported, the user can choose to:

- Run **`lwiki raw sync`** to refresh `files.log` (no source re-ingest)
- Run a targeted **INGEST** on the changed files

### 4. Heuristic Issues

These aren't caught by the conformance validator. Walk the bundle and look for:

| Category | How to detect |
|----------|---------------|
| **Contradictions** | Two pages disagree on a fact; cross-link them in `## See Also` and add a conflict note |
| **Stale claims (temporal)** | Pages older than 90 days with `generated.at` < cutoff, or pages using temporal keywords like "current", "latest", "recent", "state-of-the-art", or a year literal that no longer matches the present — propose an INGEST |
| **Orphan pages** | A concept with no incoming links from any other concept → search the bundle for natural cross-references |
| **Missing concept pages** | A slug referenced 3+ times across the bundle but with no dedicated page → propose a new concept or a redirect note |
| **Coverage gaps from `overview.md`** | Each entry under `## Open Questions` is a candidate for a query → propose a QUERY |
| **Missing cross-references** | A new concept that should link to existing ones but doesn't → backlink audit |
| **Stale insights** | An insight whose latest `verified[*].at` is older than the `generated.at` of any bundle-internal page it cites (i.e. the cited page was re-ingested after the insight was last verified) — OR an insight whose `verified[*].at` is older than the `last_modified` of any entry in its frontmatter `sources:` list — OR an insight older than 6 months that still uses "current understanding" / "current state" framing. Each match proposes a re-run of the underlying query. |

Write the lint report to `insights/lint-<date>.md` so the user can scan it later. Use [templates/insight.md](../templates/insight.md) as the shape; tag it with `type: insight` and a topic tag of `lint`.

### 5. Suggest Fixes

Heuristic findings are **reports, not auto-fixes**. After writing the lint page, summarise each finding as a one-line actionable suggestion in your reply, and ask whether the user wants any of them applied via UPDATE.

### 6. Report to User

- Conformance summary: errors / warnings / info counts (from `lwiki validate`)
- Auto-fix summary: wikilinks rewritten, dead source refs dropped
- Drift summary: new / modified / deleted file counts (from `lwiki raw status`)
- Heuristic findings: list of contradictions, staleness, orphans, missing concepts, coverage gaps, missing cross-refs
- Lint page path so the user can re-read it
- Proposed next actions (none applied)
