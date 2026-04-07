# UPDATE — Revise Existing Wiki Pages

## Two Modes

This operation runs in two modes with different confirmation levels:

### User-triggered mode
When the user explicitly asks to correct, revise, or update pages.
- **Always show diffs before writing**
- **Always cite the source of new information**
- **Always check downstream effects**
- **Per-page confirmation required — never batch-apply**

### LLM-triggered mode (during INGEST cascade)
When the LLM determines existing pages are affected by newly ingested content.
- **Certain updates** (clear factual additions, new source references, non-controversial supplements) → apply directly, no confirmation needed
- **Uncertain updates** (ambiguous claims, conflicting information, meaning-altering changes) → list them and ask the user
- Always cite the source and log changes regardless of mode

## Pre-condition

Wiki must be initialized. Read wiki/index.md to understand current state.

## Process

### 1. Identify What to Update

The user may provide:
- **Specific page names** → read those pages
- **New information** → read index.md to find affected pages
- **A lint report** → work through its recommendations

### 2. Show Diff for Each Page

Read current content in full. Propose the change:

> **Current:** `<quote the existing text>`
> **Proposed:** `<replacement text>`
> **Reason:** `<why this change is warranted>`
> **Source:** `<URL, file path, or description of where this information comes from>`

**Always include Source.** An edit without a source citation creates untraceability — future sessions won't know why the change was made.

### 3. Per-Page Confirmation

Ask before writing each page. Do not batch-apply changes without per-page confirmation. The user may accept some changes and reject others.

### 4. Check Downstream Effects

After identifying primary pages to update, scan all wiki pages for `[[slug]]` references to updated pages. For each linking page:
- Does the update change what that page asserts?
- If yes → flag it: "[[other-page]] may also need updating based on this change"
- Offer to update with the same confirm-before-write flow

### 5. Contradiction Sweep

If the new information contradicts existing claims: search ALL pages for the contradicted claim. It may appear in more than one place. Update all occurrences, not just the most obvious one.

### 6. Update Index and Overview

- Update one-line summaries in index.md if they changed
- Update the page's frontmatter `updated` date
- Propose overview.md edits if the updates shift the overall synthesis (same confirm-before-write flow)

### 7. Log

Always append to `wiki/log.md`:
```
## [YYYY-MM-DD] update | <list of updated page slugs>
Reason: <brief description of what changed and why>
Source: <URL or description>
```

## Common Mistakes

- **Updating without citing the source** — always include where the new information came from
- **Skipping the downstream check** — silent inconsistency is worse than a visible contradiction
- **Batch-writing without confirmation** — show each diff individually
- **Skipping the log** — every change must be logged
