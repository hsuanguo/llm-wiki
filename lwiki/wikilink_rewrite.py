"""Rewrite Obsidian-style ``[[wikilinks]]`` to standard markdown links.

New OKF-native bundles don't carry ``[[…]]``; new content is written
with `[label](path)` markdown links directly. This utility is the bridge
for legacy wikis being migrated and for one-off cleanup of older content:

- Reads every concept file in a bundle (and any other ``.md`` that
  carries a body).
- Resolves each ``[[slug]]`` / ``[[slug|label]]`` to the same target
  the OKF exporter would resolve to (same slug map, same same-dir
  preference, same ambiguity handling).
- Writes back with markdown links — file-relative by default, or
  absolute (`/path/to/x.md`) when ``absolute_links=True`` is passed.

Reports ambiguous / unresolved warnings on stdout so callers can route
them through the same channel as the OKF exporter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .okf_export import WIKILINK_RE, parse_frontmatter


@dataclass
class RewriteResult:
    bundle_dir: Path
    files_scanned: int
    files_rewritten: int
    links_rewritten: int
    ambiguous: list[str]
    unresolved: list[str]


@dataclass
class _SlugEntry:
    """One wikilink slug -> all candidate bundle-relative paths."""

    candidates: list[str]


def _build_slug_map(bundle_dir: Path) -> dict[str, list[str]]:
    """Walk ``bundle_dir`` for ``.md`` concept files and index by stem."""
    slug_map: dict[str, list[str]] = {}
    for path in sorted(bundle_dir.rglob("*.md")):
        rel = path.relative_to(bundle_dir).as_posix()
        # Index everything except reserved filenames — overview.md is a
        # target just like any concept.
        if rel in {"index.md", "log.md"}:
            continue
        slug_map.setdefault(path.stem, []).append(rel)
    return slug_map


def _relative_path(src: Path, tgt: Path) -> str:
    """Compute a markdown-style relative path from ``src`` to ``tgt``."""
    src_parts = list(src.parts)
    tgt_parts = list(tgt.parts)
    common = 0
    while common < min(len(src_parts), len(tgt_parts)) and src_parts[common] == tgt_parts[common]:
        common += 1
    ups = [".."] * (len(src_parts) - 1 - common)
    downs = tgt_parts[common:]
    if not ups and not downs:
        return src.name
    rel_parts = ups + downs
    rel = "/".join(rel_parts)
    return rel if rel else "."


def rewrite_text(
    body: str,
    slug_map: dict[str, list[str]],
    source_path: str,
    *,
    absolute_links: bool = False,
) -> tuple[str, int, list[str], list[str]]:
    """Rewrite ``[[…]]`` references in ``body``.

    Returns (new_body, rewrite_count, ambiguous_warnings, unresolved_warnings).
    Same resolution rules as the OKF exporter:
    - same-directory candidate wins
    - else unambiguous single candidate
    - else ambiguous warning + original kept
    - else unresolved warning + original kept
    """
    rewrites = 0
    ambiguous: list[str] = []
    unresolved: list[str] = []
    source_dir = source_path.split("/", 1)[0]

    def _render(target: str, link_text: str) -> str:
        if absolute_links:
            return f"[{link_text}](/{target})"
        return f"[{link_text}]({_relative_path(Path(source_path), Path(target))})"

    def sub(match: re.Match) -> str:  # noqa: F821 — re.Match imported below
        nonlocal rewrites
        slug = match.group(1).strip()
        display = match.group(2)
        if not slug:
            return match.group(0)
        candidates = slug_map.get(slug, [])
        same_dir = [c for c in candidates if c.split("/", 1)[0] == source_dir]
        if same_dir:
            target = same_dir[0]
        elif len(candidates) == 1:
            target = candidates[0]
        elif len(candidates) > 1:
            ambiguous.append(f"[[{slug}]] resolves to multiple paths: {candidates}")
            return match.group(0)
        else:
            unresolved.append(f"[[{slug}]] not found in any concept file")
            return match.group(0)
        if display and display.strip():
            link_text = display.strip()
        else:
            link_text = target.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        rewrites += 1
        return _render(target, link_text)

    import re  # local — keeps module import light for tests

    new_body = WIKILINK_RE.sub(sub, body)
    return new_body, rewrites, ambiguous, unresolved


def rewrite_bundle(
    bundle_dir: Path,
    *,
    absolute_links: bool = False,
    write: bool = True,
) -> RewriteResult:
    """Rewrite ``[[…]]`` references in every concept file of ``bundle_dir``.

    Set ``write=False`` for a dry run (counts and warnings only).
    """
    bundle_dir = bundle_dir.resolve()
    slug_map = _build_slug_map(bundle_dir)

    scanned = 0
    rewritten_files = 0
    total_rewrites = 0
    ambiguous: list[str] = []
    unresolved: list[str] = []

    for path in sorted(bundle_dir.rglob("*.md")):
        rel = path.relative_to(bundle_dir).as_posix()
        if rel in {"index.md", "log.md", "AGENTS.md", "CLAUDE.md", "README.md"}:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        if not body:
            continue
        new_body, n, amb, unres = rewrite_text(
            body, slug_map, rel, absolute_links=absolute_links
        )
        ambiguous.extend(amb)
        unresolved.extend(unres)
        if n == 0:
            continue
        total_rewrites += n
        rewritten_files += 1
        if write:
            from .okf_export import emit_frontmatter  # local — heavy dep

            rendered = emit_frontmatter(fm) + new_body.lstrip("\n")
            path.write_text(rendered, encoding="utf-8")

    return RewriteResult(
        bundle_dir=bundle_dir,
        files_scanned=scanned,
        files_rewritten=rewritten_files,
        links_rewritten=total_rewrites,
        ambiguous=ambiguous,
        unresolved=unresolved,
    )


def iter_warnings(result: RewriteResult) -> Iterable[str]:
    """Yield all warnings produced by a rewrite run, for CLI reporting."""
    for w in result.ambiguous:
        yield f"  ambiguous: {w}"
    for w in result.unresolved:
        yield f"  unresolved: {w}"