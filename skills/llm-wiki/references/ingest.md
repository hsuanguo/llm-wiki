# INGEST — Process New Sources

## When to Run

User adds files to raw/, pastes content, provides a URL, or says "ingest" / "add to wiki".

## Pre-condition

Wiki must be initialized (`wiki/index.md` and `wiki/log.md` exist). If not, run **[INIT](init.md)** first.

## Process

### 1. Accept the Source

- **File path** → read directly; copy to `raw/<filename>` if not already there
- **URL** → fetch content; save to `raw/<slug>.md`
- **Pasted text** → save to `raw/<slug>.md`

Slug format: lowercase, hyphens, no special characters. Example: "Attention Is All You Need" → `attention-is-all-you-need.md`

### 2. Read in Full

Read all content. For long sources, read in sections. Do not skip.

### 3. Assess and Proceed

After reading the source:
- Identify key takeaways, entities, and concepts
- Check whether it contradicts anything already in the wiki (read index.md + relevant pages)
- Proceed to write/update pages based on your assessment

**Only ask the user if something is genuinely unclear** — e.g., ambiguous claims, conflicting information where you can't determine which is correct, or domain-specific terms you don't understand. Do not ask for emphasis/de-emphasis on every ingest.

### 4. Compile into Wiki

For each piece of knowledge in the source, determine where it belongs. Apply this decision logic to summaries, concepts, and entities alike:

**Decision logic (not mutually exclusive — a single source may trigger multiple actions):**

- **Same core topic as existing page** → Merge into that page. Add the new raw file to `sources` frontmatter. Update affected sections.
- **New concept/entity** → Create a new page. Name the file after the concept or entity, not the raw file.
- **Spans multiple pages** → Place primary content in the most relevant page. Add `[[wikilinks]]` and See Also cross-references to related pages.

**Handling contradictions:**
- If the new source contradicts existing content, **annotate the disagreement with source attribution** — do not silently overwrite.
- When merging into an existing page, note the conflict within that page (e.g., "Source A claims X; Source B claims Y").
- When conflicting content lives in separate pages, note it in both and cross-link them.

**Page creation by type:**
- Summaries → `summaries/<slug>.md` using [templates/summary.md](../templates/summary.md)
- Concepts → `concepts/<slug>.md` using [templates/concept.md](../templates/concept.md)
- Entities → `entities/<slug>.md` using [templates/entity.md](../templates/entity.md)

### 5. Backlink Audit — Do Not Skip

Scan ALL existing pages in wiki/ for mentions that should link to newly created or updated pages but don't. Add `[[slug]]` references where appropriate.

This is the most commonly skipped step. A compounding wiki's value comes from bidirectional links.

### 6. Cascade Update

After direct operations, scan the entire wiki for pages that may be affected by the new information:

1. Read through all pages in summaries/, concepts/, entities/, insights/
2. For each page, assess whether the new source changes, contradicts, or supplements its content
3. **Pages are not bound to specific raw files** — a source named "rag.md" may affect pages about fine-tuning, langchain, or any related topic
4. Categorize findings:
   - **Certain updates** → apply directly
   - **Uncertain** → list them and ask the user for guidance

### 7. Update Overview, Index, Log

- **overview.md** → update if the source shifts the big picture, adds key entities/concepts, or raises new open questions
- **index.md** → add entries for new pages, update summaries for modified pages
- **index.md** → use table format per [templates/index.md](../templates/index.md)
- **log.md** → append:
  ```
  ## [YYYY-MM-DD] ingest | <source title>
  Pages created: <list>
  Pages updated: <list>
  - Cascade: <cascade-updated page>
  ```

### 8. Update raw/files.log

**Required:** from **wiki root**:

`lwiki raw sync`

(or `lwiki checkout`). If **`lwiki`** is not available, ask the user to install it before running sync. Writes `files.log` inside `raw/`; no script copy inside the wiki.

### 9. Report to User

- Summary page written/updated
- Concept/entity pages created or updated (list)
- Pages that received backlinks (list)
- Cascade updates applied or flagged
- Total pages touched

A typical 2000-3000 word article touches 5-8 wiki files.
