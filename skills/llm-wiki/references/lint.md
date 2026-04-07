# LINT — Wiki Health Check

## When to Run

User says "lint", "health check", "find gaps", "check the wiki", or similar. Recommended after every 5-10 ingests.

## Pre-condition

Wiki must be initialized. Read wiki/index.md and scan all page directories.

## Process

### 1. Build Page Inventory

Read index.md, overview.md, and all files in summaries/, concepts/, entities/, insights/. Build a map of:
- All existing slugs (filenames without .md)
- All `[[slug]]` references found in any page
- All `sources` listed in frontmatter
- Inbound link count per page

### 2. Deterministic Checks (Auto-Fix)

Fix these automatically without asking:

**Broken links**
- `[[slug]]` references where no corresponding file exists
- Search wiki/ for a file with the same name elsewhere
  - Exactly one match → fix the path
  - Zero or multiple matches → report to user

**Missing frontmatter**
- Pages without required fields: title, type, tags, sources, updated
- Add missing fields with placeholder values

**Index inconsistencies**
- File exists in wiki/ but missing from index.md → add entry with "(no summary)" placeholder
- Index entry points to nonexistent file → mark as `[MISSING]`

**Broken raw references**
- Links in `sources` frontmatter pointing to nonexistent raw/ files
- Search raw/ for file with same name → fix if exactly one match, report otherwise

**Raw vs files.log drift (optional)**
- From wiki root: **`lwiki raw status`** (compares `raw/` to `files.log`, no write)
- If there is drift, reconcile (ingest or **`lwiki raw sync`** after confirming `raw/` is correct)

### 3. Heuristic Checks (Report Only)

Report these findings without auto-fixing. Let the user decide:

**Contradictions**
- Two pages making conflicting claims about the same thing
- Include exact quotes from both pages

**Stale claims**
- Pages not updated within 90 days that contain temporal language: "current", "latest", "recent", "state-of-the-art", or year literals two or more years old

**Orphan pages**
- Pages with zero inbound `[[slug]]` links (excluding index.md and overview.md)
- Suggest which pages should link to them

**Missing concept pages**
- Terms referenced 3+ times across the wiki but lacking a dedicated page

**Missing cross-references**
- Two pages that discuss the same entity/concept but don't link to each other

**Coverage gaps**
- Open questions listed in overview.md that could be answered
- Topics partially covered that need more sources

**Stale insights**
- Insight pages whose cited source pages (in frontmatter `sources`) have been substantially updated since the insight was created
- Compare the insight's `updated` date against the `updated` dates of its cited pages
- If any cited page was updated after the insight, flag it as potentially outdated

### 4. Write Lint Report

Always write `insights/lint-<today>.md` using [templates/insight.md](../templates/insight.md) as base, with:
- `tags: [insight, lint, maintenance]`
- Body structured as: Summary (counts) → Auto-Fixed (list) → Needs Attention (categorized findings)

Add the lint report to index.md under Insights (table format per [templates/index.md](../templates/index.md)).

### 5. Offer Fixes for Heuristic Issues

For each actionable heuristic finding, offer a concrete fix:
- Show exact diff before writing
- Apply only after user confirmation

### 6. Log

Append to `wiki/log.md`:
```
## [YYYY-MM-DD] lint | <N> deterministic fixed, <N> heuristic reported
Report: [[lint-<today>]]
```
