"""Canonical OKF 0.2 bundle layout (INIT). Kept in sync with the wiki skill SKILL.md."""

from .okf_export import OKF_VERSION

# Authoritative tree — update here and in skills/llm-wiki/SKILL.md if layout changes.
CANONICAL_BUNDLE_TREE = f"""<bundle-root>/
├── index.md              # OKF {OKF_VERSION} — declares okf_version in frontmatter
├── log.md                # Append-only operation log
├── overview.md           # High-level synthesis (top-level concept)
├── AGENTS.md             # Domain schema (editable; shared with non-Claude agents)
├── README.md             # Pointer doc (optional)
├── summaries/            # Source summaries
├── concepts/             # Concept pages
├── entities/             # Entity pages (people, tools, orgs, products)
├── insights/             # Syntheses and cross-page analyses
└── raw/                  # Immutable source documents (LLM reads, never modifies)
    ├── files.log         # Auto-generated file tracking (name + sha256)
    └── ...
"""


def render_structure_text() -> str:
    """Full text for `lwiki structure` (tree + required commands)."""
    return f"""{CANONICAL_BUNDLE_TREE}
Commands (install the `lwiki` CLI if missing):
  lwiki init <bundle-root> --domain "..." --sources "..."     create this layout + initial raw/files.log
  lwiki raw sync                                                from bundle root: refresh raw/files.log
  lwiki raw status                                              from bundle root: report drift (no write)
  lwiki validate <bundle-root>                                  check OKF {OKF_VERSION} conformance
  lwiki serve --root <parent-of-bundles>                        browse all bundles in a parent directory
  lwiki migrate <old-wiki> --out <new-bundle>                   convert a legacy Obsidian-shaped wiki
"""


def render_structure_compact() -> str:
    """Tree only (for tests or embedding)."""
    return CANONICAL_BUNDLE_TREE.strip()