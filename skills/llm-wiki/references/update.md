# UPDATE — Revise Bundle Pages

## When to Run

User asks for edits, corrections, or merges on existing pages; or the cascade step of INGEST surfaces updates that are certain enough to apply directly.

## Process

### 1. Identify the Target Pages

- If the user names a path (`concepts/democracy.md`, `entities/athens.md`, …) — open it directly.
- If the user names only a topic — locate the page via `index.md` and the See Also chain.
- For multiple edits, group by whether they share a `## See Also` reach (so a single pass over each page covers them).

### 2. Read Current State + History

- Read the current page in full, including frontmatter.
- If a recent ingest or query logged a `verified: [...]` audit entry related to this page, note which actor / timestamp the change should be attributed to (`generated.by` for the new edit; new `verified` entry if the change is a verification pass).

### 3. Propose the Diff

For each page, compose the proposed diff in plain text:

- **Frontmatter changes** explicitly called out (don't bury them)
- **Body changes** shown as removed-then-added, or "no body change" if only frontmatter changed
- **See Also** updates if you added or removed cross-references
- **`generated.at`** refresh is automatic (every edit updates it); surface the new value

Show the diff to the user and **wait for confirmation** before writing.

### 4. Write the Update

On confirmation:

1. Update the page file with the new frontmatter + body. Use the same write semantics as INGEST (markdown links, OKF-shaped frontmatter).
2. Refresh `generated.at`. Add a `verified: [{ by, at }]` entry if the change is a verification (correction of a factual error), not just a re-phrasing.
3. If you added new concepts that other pages should link to, run the **backlink audit** across the bundle.
4. Append to `log.md`:
   ```
   ## [YYYY-MM-DD] update | <topic>
   Pages updated: <list>
   ```

### 5. Cascade

If the change is likely to affect other pages (e.g. a corrected date, a new tag, a renamed entity):

1. Re-read the related pages
2. Apply the same diff pattern; show each to the user
3. Wait for confirmation before writing each

If the cascade is large (>5 pages), propose the changeset as a single batch and ask for one confirmation covering all of them.

### 6. Status Updates

If the change is more than a typo fix:

- `status: draft` → `status: stable` once a second source agrees or the user signs off
- `status: stable` → `status: deprecated` if the page is superseded by a newer one; add a `## Superseded by: [new-page](path.md)` note at the top of the body

Never silently flip status; always call it out in the diff and ask.