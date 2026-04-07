# QUERY — Answer Questions from the Wiki

## When to Run

User asks a domain question, requests analysis, comparison, or synthesis from wiki content.

## Pre-condition

Wiki must be initialized. If not, tell user to run INIT first.

## Core Rule

**Never answer from general knowledge.** The wiki is the source of truth. Even if you think you know the answer, read the wiki pages first. The wiki may contain information that contradicts your training data — that contradiction is valuable signal.

## Process

### 1. Read Index First

Scan `wiki/index.md` to identify relevant pages by topic, tags, and summaries.

### 2. Read Relevant Pages

Read identified pages in full. Follow one level of `[[wikilinks]]` if they point to pages relevant to the question.

### 3. Synthesize Answer

- Ground every claim in wiki pages with `[[slug]]` citations
- Note agreements and disagreements between pages
- Flag gaps: "The wiki has no page on X" or "[[page]] doesn't cover Y yet"
- Note confidence levels: well-supported (multiple sources) vs. single-source claims
- Match format to question type:
  - Factual → prose with citations
  - Comparison → table
  - How-it-works → numbered steps
  - What-do-we-know → structured summary with open questions
- Suggest follow-up sources to ingest or questions to investigate

### 4. Report Issues Found in Existing Pages

Query does NOT modify existing pages. But if during reading you discover errors, outdated information, or inconsistencies in existing wiki pages, report them at the end of your answer:

> "While answering, I noticed the following issues in existing pages:
> - [[rag]]: description of X appears outdated — newer source says Y
> - [[langchain]] and [[llamaindex]] contradict each other on Z
>
> Want me to run UPDATE to fix these?"

Only proceed with UPDATE if the user confirms.

### 5. Offer to Save as Insight (after answering and reporting issues)

After answering, ask:

> "Worth saving as `insights/<suggested-slug>.md`?"

Guidelines for when to save:
- New synthesis across multiple pages → save
- Simple lookup from one page → don't save
- New connection or pattern discovered → save
- Comparison or analysis that took effort → save

### 6. If Saving: Create Insight and Update Related Pages

Write `insights/<slug>.md` using [templates/insight.md](../templates/insight.md).

**Insights are point-in-time snapshots.** They capture analysis as of their creation date and are NOT updated by subsequent ingests or cascade updates. If the underlying source pages change, lint will flag the insight as potentially stale.

Then update related pages — Obsidian backlinks are NOT visible to LLM:
1. Add reverse links to cited concepts/entities pages in their See Also section
2. Update overview.md if the insight reveals new understanding
3. Add entry to index.md under Insights (table format per [templates/index.md](../templates/index.md))
4. Append to log.md

### 7. If Not Saving: No Log

Do not write to log.md or index.md. Only log when wiki/ files are actually created or changed.
