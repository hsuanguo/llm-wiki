"""Convert an Obsidian-shaped llm-wiki into an OKF 0.2 bundle.

Legacy shape (pre-2.0):

    <wiki-root>/
    ├── AGENTS.md
    ├── CLAUDE.md
    ├── raw/
    └── wiki/
        ├── index.md
        ├── log.md
        ├── overview.md
        ├── summaries/
        ├── concepts/
        ├── entities/
        └── insights/

OKF-native shape (post-2.0):

    <new-bundle>/
    ├── index.md        # okf_version: '0.2'
    ├── log.md
    ├── overview.md
    ├── AGENTS.md       # lifted from wiki root
    ├── CLAUDE.md       # lifted from wiki root
    ├── README.md       # fresh pointer
    ├── summaries/      # lifted from wiki/
    ├── concepts/
    ├── entities/
    ├── insights/
    └── raw/            # preserved (files.log intact)

The source wiki is **not** mutated — the converter emits the bundle
alongside. Migration is idempotent at the directory level: refuses to
overwrite an existing bundle unless ``force=True``.

Frontmatter migration rules:
- ``updated:`` → ``generated: { by: 'lwiki-migrate/0.1', at: <date> }``
- ``sources: [raw/foo.md]`` → ``sources: [{ resource: 'raw/foo.md', ... }]``
- ``cited: [slug, ...]`` (insight pages) → ``verified: [{ by, at }]``
- Wiki-internal-only fields are dropped (``okf_version`` already
  present, etc.).
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .okf_export import emit_frontmatter, parse_frontmatter
from .wikilink_rewrite import rewrite_bundle

MIGRATE_BY = "lwiki-migrate/0.1"

# Match a plain ISO date (YYYY-MM-DD) or anything string-coercible.
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Reserved filenames that must NOT be used as concept slugs.
RESERVED = {"index.md", "log.md", "AGENTS.md", "CLAUDE.md", "README.md"}


@dataclass
class MigrateResult:
    """Summary of a migrate run."""

    old_wiki: Path
    new_bundle: Path
    files_copied: int
    pages_migrated: int
    links_rewritten: int
    warnings: list[str] = field(default_factory=list)


def _is_iso_date(value: Any) -> str | None:
    """Return ``value`` if it's a date-shaped string; otherwise ``None``."""
    if isinstance(value, (date, datetime)) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str) and _ISO_DATE_RE.match(value.strip()):
        return value.strip()
    return None


def _migrate_frontmatter(fm: dict, today: str) -> dict:
    """Rewrite legacy frontmatter into OKF 0.2 shape."""
    out: dict = {}

    # Preserve OKF-native fields unchanged.
    for k in ("type", "title", "description", "tags", "resource"):
        if k in fm:
            out[k] = fm[k]

    # `generated` from `updated`.
    at_date = _is_iso_date(fm.get("updated")) or today
    out["generated"] = {"by": MIGRATE_BY, "at": at_date}

    # `sources` list — coerce legacy paths into credibility-shaped entries.
    if "sources" in fm:
        out["sources"] = _migrate_sources(fm["sources"])

    # `cited` → `verified` (insight pages only).
    if "cited" in fm:
        cited = fm["cited"]
        entries: list[dict] = []
        if isinstance(cited, list):
            for slug in cited:
                if not isinstance(slug, str) or not slug.strip():
                    continue
                entries.append({"by": slug.strip(), "at": today})
        if entries:
            out["verified"] = entries

    return out


def _migrate_sources(value: Any) -> list[dict]:
    """Coerce legacy ``sources: [raw/foo.md]`` to OKF credibility entries."""
    if not isinstance(value, list):
        return []
    out: list[dict] = []
    for entry in value:
        if isinstance(entry, str):
            out.append({"resource": entry})
        elif isinstance(entry, dict):
            out.append(entry)
    return out


def _is_legacy_wiki(wiki_root: Path) -> bool:
    """A wiki is in the legacy shape when it has both AGENTS.md and wiki/."""
    return (wiki_root / "AGENTS.md").is_file() and (wiki_root / "wiki").is_dir()


def _copy_root_file(src: Path, dst: Path) -> bool:
    """Copy a top-level file from old wiki to new bundle."""
    if not src.is_file():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def convert(old_wiki: Path, new_bundle: Path, *, force: bool = False) -> MigrateResult:
    """Convert ``old_wiki`` into an OKF-native bundle at ``new_bundle``.

    Raises FileNotFoundError if the source wiki isn't recognisable as a
    legacy wiki. Raises FileExistsError if ``new_bundle`` is non-empty
    and ``force`` is False.
    """
    old_wiki = old_wiki.resolve()
    new_bundle = new_bundle.resolve()

    if not _is_legacy_wiki(old_wiki):
        raise FileNotFoundError(
            f"No legacy wiki at {old_wiki} (missing AGENTS.md + wiki/ directory)"
        )

    if new_bundle.exists():
        if any(new_bundle.iterdir()) and not force:
            raise FileExistsError(
                f"Bundle directory {new_bundle} is not empty (use --force to overwrite)"
            )
    else:
        new_bundle.mkdir(parents=True)

    warnings: list[str] = []
    files_copied = 0
    pages_migrated = 0
    today = date.today().isoformat()

    # Lift root-level files: AGENTS.md, CLAUDE.md.
    for rel in ("AGENTS.md", "CLAUDE.md"):
        if _copy_root_file(old_wiki / rel, new_bundle / rel):
            files_copied += 1

    # Lift `wiki/{index,log,overview}.md` to the bundle root.
    legacy_wiki = old_wiki / "wiki"
    for rel in ("index.md", "log.md", "overview.md"):
        src = legacy_wiki / rel
        if not src.is_file():
            warnings.append(f"missing {rel} in source wiki; bundle will lack it")
            continue
        if rel == "overview.md":
            # Re-render overview.md with the OKF frontmatter shape.
            text = src.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(text)
            fm = _migrate_frontmatter(fm, today)
            new_text = emit_frontmatter(fm) + body.lstrip("\n")
            (new_bundle / rel).write_text(new_text, encoding="utf-8")
            files_copied += 1
            pages_migrated += 1
        elif rel == "index.md":
            # Re-emit with the OKF bundle-root index shape.
            (new_bundle / rel).write_text(
                "---\nokf_version: '0.2'\n---\n\n# Bundle Index\n",
                encoding="utf-8",
            )
            files_copied += 1
        elif rel == "log.md":
            shutil.copy2(src, new_bundle / rel)
            files_copied += 1

    # Lift concept subdirs: `wiki/<sub>/<slug>.md` → `<sub>/<slug>.md`.
    for sub in ("summaries", "concepts", "entities", "insights"):
        src_sub = legacy_wiki / sub
        if not src_sub.is_dir():
            continue
        dst_sub = new_bundle / sub
        dst_sub.mkdir(parents=True, exist_ok=True)
        for md in sorted(src_sub.glob("*.md")):
            if md.stem in RESERVED:
                warnings.append(f"skipping reserved filename {sub}/{md.name}")
                continue
            text = md.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(text)
            fm = _migrate_frontmatter(fm, today)
            new_text = emit_frontmatter(fm) + body.lstrip("\n")
            (dst_sub / md.name).write_text(new_text, encoding="utf-8")
            files_copied += 1
            pages_migrated += 1

    # Write a fresh README pointer.
    (new_bundle / "README.md").write_text(
        f"# Bundle (migrated from {old_wiki.name})\n\n"
        "This bundle is OKF native. It was converted from a legacy\n"
        "Obsidian-shaped llm-wiki. See `AGENTS.md` for local conventions.\n",
        encoding="utf-8",
    )
    files_copied += 1

    # Mirror raw/ + files.log verbatim.
    raw_src = old_wiki / "raw"
    if raw_src.is_dir():
        raw_dst = new_bundle / "raw"
        if raw_dst.exists():
            shutil.rmtree(raw_dst)
        shutil.copytree(raw_src, raw_dst, symlinks=True)
        files_copied += 1

    # Rewrite any leftover `[[wikilinks]]` to markdown links in place.
    rewrite_result = rewrite_bundle(new_bundle)
    warnings.extend(f"{w}" for w in rewrite_result.ambiguous)
    warnings.extend(f"{w}" for w in rewrite_result.unresolved)

    return MigrateResult(
        old_wiki=old_wiki,
        new_bundle=new_bundle,
        files_copied=files_copied,
        pages_migrated=pages_migrated,
        links_rewritten=rewrite_result.links_rewritten,
        warnings=warnings,
    )