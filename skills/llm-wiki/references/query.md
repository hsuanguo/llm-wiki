# QUERY — Answer from the Bundle

## When to Run

User asks a question that should be answered **strictly from bundle content**, not general knowledge. The phrase "what do we know about X" is the canonical trigger; a direct "answer this for me" is a signal too.

## Process

### 1. Scope the Question

Re-read the question and identify:

- The **entities / concepts** involved (slug names to look up)
- The **claim shape**: comparison? chronology? gap? contradiction? synthesis?
- Whether the user wants citations / page anchors

### 2. Gather Bundle Context

- Skim `index.md` to find candidate pages
- Read the top relevant pages in full — including `## See Also` chains
- For gap / contradiction queries, also pull the `insights/` folder

If the answer requires pages you haven't yet read, follow the markdown links — they are the bundle's signal that those pages are related.

### 3. Synthesise the Answer

Match the answer shape to the question shape:

| Question shape | Answer shape |
|----------------|--------------|
| Factual ("what is X") | Prose paragraph; cite one or two pages |
| Comparison ("compare A and B") | Side-by-side table or short prose with explicit A-vs-B sentences; cite both |
| How-it-works ("how does X do Y") | Numbered steps; cite the page that documents each step |
| What-do-we-know ("what do we know about X") | Structured summary: facts (cited), open questions (cited to `overview.md`), contradictions (linked both ways) |
| Gap-finding ("what's missing about X") | List of candidate topics, each marked "no page yet" or "page exists, expand to cover X" |

After choosing the shape:

- **Cite every claim** with a markdown link to the source page (`[foo](concepts/foo.md)` from `overview.md`; `[bar](../entities/bar.md)` from a sub-page; `/concepts/bar.md` is also valid)
- **Note uncertainty** explicitly when a claim is sourced from a single page or contradicts another page in the bundle
- **Stay inside the bundle.** If the question requires information that isn't in any page, say so and recommend a targeted ingest.

### 4. Optional: Save as Insight

If the answer has standalone value (synthesis, comparison, gap analysis), propose to save it as an insight page using [templates/insight.md](../templates/insight.md). Insights are point-in-time snapshots, not cascade-updated, so a new ingest won't disturb them.

Wait for user confirmation before writing the insight. If confirmed:

- Set `type: insight` and `status: draft` initially
- Add `verified: [{ by: <your actor>, at: <today> }]` once the user signs off
- Append a `## [YYYY-MM-DD] query | <topic>` entry to `log.md`
- **After saving the insight, run UPDATE** to add a reverse `[insight-slug](../insights/<slug>.md)` entry under `## See Also` on every cited concept/entity page, and to refresh `overview.md` if the synthesis moves the high-level picture. The insight itself is a snapshot and won't be cascade-updated, but its neighbours need to know about it.

### 5. Optional: Report Issues

If your read of the bundle surfaces problems — outdated facts, contradictions, an obvious gap in coverage — flag them in your reply and ask whether the user wants them fixed. **Don't auto-fix.** A query is read-side; fixing belongs to UPDATE or LINT.
