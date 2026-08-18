"""Export an llm-wiki as an OKF (Open Knowledge Format) bundle.

The exporter is read-only on the source wiki: it walks ``wiki/``, rewrites
``[[wikilinks]]`` to bundle-relative markdown links, normalizes frontmatter
into OKF 0.2's recommended shape, and emits per-directory ``index.md`` files
in the OKF bullet-list format. It is the counterpart to the Obsidian-first
templates in ``skills/llm-wiki/templates/``: llm-wiki stays Obsidian-native,
OKF is the publishable projection.

OKF 0.2 breaking changes vs 0.1 are reflected here:
  * Content's last-change moves from ``timestamp`` to ``generated: {by, at}``
  * Bundle root ``index.md`` declares ``okf_version: "0.2"``
  * Per-source credibility signals live in the frontmatter ``sources`` list
    (the wiki-internal raw-file lineage is dropped from the bundle, the
    same way 0.1 dropped ``sources``/``cited``).

Reference: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# llm-wiki concept subdirectories. The exporter mirrors them at the bundle
# root; OKF does not require any specific hierarchy.
WIKI_SUBDIRS: tuple[str, ...] = ("summaries", "concepts", "entities", "insights")

# OKF 0.2 — declared on the bundle-root index.md frontmatter.
OKF_VERSION = "0.2"

# OKF 0.2 actor convention for `generated.by`. Tools are ``<name>/<version>``.
GENERATED_BY = "llm-wiki/0.2"

# Match [[slug]] or [[slug|display]], with optional #anchor. Group 1 is the
# slug, group 2 (optional) is the display text.
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")

# Reserved OKF filenames that must NOT be used for concept documents.
OKF_RESERVED = frozenset({"index.md", "log.md"})


@dataclass
class ConceptRecord:
    """A wiki page (concept) with its source path and parsed frontmatter."""

    rel_path: str
    title: str
    description: str
    type: str
    tags: list[str]
    resource: str | None
    timestamp: str
    body: str


def build_generated(timestamp: str, by: str = GENERATED_BY) -> dict[str, str]:
    """OKF 0.2 ``generated: { by, at }`` mapping.

    Returns an empty dict when ``timestamp`` is empty so concept pages with
    no date still get a clean frontmatter block.
    """
    if not timestamp:
        return {}
    return {"by": by, "at": timestamp}


@dataclass
class ExportResult:
    """Summary of an export run; used by CLI feedback and tests."""

    bundle_dir: Path
    concept_count: int
    rewritten_links: int
    ambiguous_warnings: list[str] = field(default_factory=list)
    unresolved_warnings: list[str] = field(default_factory=list)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split markdown into (frontmatter dict, body). Returns ({}, text) if
    no parseable YAML frontmatter is present."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm_text = text[4:end]
    body = text[end + 5 :]
    try:
        fm = yaml.safe_load(fm_text) or {}
        if not isinstance(fm, dict):
            fm = {}
    except yaml.YAMLError:
        fm = {}
    # Strip the single leading newline that follows `---\n` so the body
    # starts with the actual content (not a blank line).
    if body.startswith("\n"):
        body = body[1:]
    return fm, body


def emit_frontmatter(fm: dict) -> str:
    """Render a frontmatter dict as a YAML block (without trailing body)."""
    if not fm:
        return ""
    rendered = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip()
    return f"---\n{rendered}\n---\n\n"


def _read_concept(md: Path, rel: str) -> ConceptRecord:
    text = md.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    tags_raw = fm.get("tags") or []
    if isinstance(tags_raw, list):
        tags = [str(t) for t in tags_raw]
    else:
        tags = []
    resource_val = fm.get("resource")
    return ConceptRecord(
        rel_path=rel,
        title=str(fm.get("title", md.stem)),
        description=str(fm.get("description", "")),
        type=str(fm.get("type", "")),
        tags=tags,
        resource=resource_val if isinstance(resource_val, str) else None,
        timestamp=str(fm.get("updated", "")),
        body=body,
    )


def collect_concepts(wiki_root: Path) -> list[ConceptRecord]:
    """Walk ``wiki/{summaries,concepts,entities,insights}/`` and collect all
    concept files. ``wiki/overview.md`` is collected separately."""
    wiki = wiki_root / "wiki"
    concepts: list[ConceptRecord] = []
    for sub in WIKI_SUBDIRS:
        sub_dir = wiki / sub
        if not sub_dir.is_dir():
            continue
        for md in sorted(sub_dir.glob("*.md")):
            concepts.append(_read_concept(md, f"{sub}/{md.name}"))
    overview = wiki / "overview.md"
    if overview.is_file():
        concepts.append(_read_concept(overview, "overview.md"))
    return concepts


def build_slug_map(wiki_root: Path) -> dict[str, list[str]]:
    """Build a slug -> [bundle_rel_path] map for wikilink rewriting.

    Multiple paths per slug happen when two wiki subdirs contain a file with
    the same stem (e.g., ``concepts/rag.md`` and ``entities/rag.md``). The
    rewriter prefers a same-dir candidate before falling back to ambiguity.
    """
    wiki = wiki_root / "wiki"
    slug_map: dict[str, list[str]] = {}
    for sub in WIKI_SUBDIRS:
        sub_dir = wiki / sub
        if not sub_dir.is_dir():
            continue
        for md in sub_dir.glob("*.md"):
            slug_map.setdefault(md.stem, []).append(f"{sub}/{md.name}")
    overview = wiki / "overview.md"
    if overview.is_file():
        slug_map.setdefault("overview", []).append("overview.md")
    return slug_map


def rewrite_wikilinks(
    body: str,
    slug_map: dict[str, list[str]],
    source_dir: str,
    *,
    absolute_links: bool = True,
    source_path: str | None = None,
) -> tuple[str, int, list[str], list[str]]:
    """Rewrite ``[[slug]]`` and ``[[slug|display]]`` to OKF markdown links.

    OKF 0.2 §6.1 allows both absolute (bundle-root, e.g. ``/concepts/rag.md``)
    and file-relative (``../concepts/rag.md``) link forms. Absolute is the
    spec-recommended default and is what ``absolute_links=True`` emits.

    Set ``absolute_links=False`` and pass the source file's bundle-relative
    path (e.g. ``concepts/democracy.md``) as ``source_path`` to get
    file-relative links. File-relative links are what most wiki renderers
    (mkdocs, GitHub Pages, Docusaurus, Obsidian) follow reliably without
    any rewrites, so they're useful when the bundle will be served without
    a consumer that understands the leading-slash form.

    Returns (new_body, rewrite_count, ambiguous_warnings, unresolved_warnings).
    """
    rewrites = 0
    ambiguous: list[str] = []
    unresolved: list[str] = []

    def _render(target: str, link_text: str) -> str:
        if absolute_links:
            return f"[{link_text}](/{target})"
        # File-relative from the source page. The source page is at
        # ``<bundle>/<source_path>``; the target is ``<bundle>/<target>``.
        src = Path(source_path or f"{source_dir}/_")  # "_" placeholder for top-level
        tgt = Path(target)
        rel = _relative_path(src, tgt)
        return f"[{link_text}]({rel})"

    def sub(match: re.Match) -> str:
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
            unresolved.append(f"[[{slug}]] not found in any wiki/ subdir")
            return match.group(0)

        if display and display.strip():
            link_text = display.strip()
        else:
            link_text = target.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        rewrites += 1
        return _render(target, link_text)

    new_body = WIKILINK_RE.sub(sub, body)
    return new_body, rewrites, ambiguous, unresolved


def _relative_path(src: Path, tgt: Path) -> str:
    """Compute a markdown-style relative path from ``src`` to ``tgt``.

    Both arguments are POSIX-style bundle-relative paths (no leading slash).
    Examples (using the bundle root as the anchor):
        src=overview.md, tgt=concepts/rag.md → ``concepts/rag.md``
        src=concepts/rag.md, tgt=entities/foo.md → ``../entities/foo.md``
        src=concepts/sub/page.md, tgt=concepts/other.md → ``../other.md``
    """
    src_parts = list(src.parts)
    tgt_parts = list(tgt.parts)
    # Common ancestor
    common = 0
    while common < min(len(src_parts), len(tgt_parts)) and src_parts[common] == tgt_parts[common]:
        common += 1
    ups = [".."] * (len(src_parts) - 1 - common)  # src's parent segments (drop src filename)
    downs = tgt_parts[common:]
    if not ups and not downs:
        return src.name  # same file
    rel_parts = ups + downs
    rel = "/".join(rel_parts)
    return rel if rel else "."


def _display_title(path: str) -> str:
    """Extract a human-friendly title from a bundle-relative path.

    ``concepts/rag.md`` → ``rag``; ``concepts/`` → ``concepts`` (subdirectory).
    """
    if path.endswith("/"):
        return path.rstrip("/")
    last = path.rsplit("/", 1)[-1]
    return last.rsplit(".", 1)[0] if "." in last else last


def write_index_md(
    out_path: Path,
    section_title: str,
    entries: list[tuple[str, str]],
    *,
    source_rel_path: str | None = None,
    absolute_links: bool = True,
) -> None:
    """Write an OKF-style ``index.md`` (bullet list, one entry per concept).

    ``source_rel_path`` is the bundle-relative path of this index file
    (e.g. ``concepts/index.md``); required only when ``absolute_links``
    is False, so per-entry links can be computed relative to it.
    """
    lines = [f"# {section_title}", ""]
    for path, desc in entries:
        title = _display_title(path)
        d = desc if desc else "(no description)"
        if absolute_links:
            href = f"/{path}"
        else:
            if source_rel_path is None:
                raise ValueError("source_rel_path required when absolute_links=False")
            href = _relative_path(Path(source_rel_path), Path(path))
        lines.append(f"* [{title}]({href}) - {d}")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _singularize(word: str) -> str:
    """Light-touch singularization for the four llm-wiki subdirs."""
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("s"):
        return word[:-1]
    return word


def _wiki_root_is_valid(wiki_root: Path) -> bool:
    """A wiki is initialized if it has AGENTS.md or both wiki/index.md and
    wiki/log.md. Either marker is enough — they all converge on the same
    layout."""
    if (wiki_root / "AGENTS.md").is_file():
        return True
    if (wiki_root / "wiki" / "index.md").is_file() and (wiki_root / "wiki" / "log.md").is_file():
        return True
    return False


def _passthrough_raw(src_raw: Path, dst_raw: Path) -> None:
    """Symlink raw files into the bundle. Falls back to copy if symlinks
    fail (some filesystems / Windows). Preserves ``files.log`` verbatim."""
    dst_raw.mkdir(parents=True, exist_ok=True)
    for f in src_raw.iterdir():
        target = dst_raw / f.name
        if target.exists() or target.is_symlink():
            target.unlink()
        if f.is_dir():
            target.mkdir(exist_ok=True)
            _passthrough_raw(f, target)
            continue
        try:
            target.symlink_to(f.resolve())
        except OSError:
            target.write_bytes(f.read_bytes())


def export_okf(
    wiki_root: Path,
    bundle_dir: Path,
    *,
    force: bool = False,
    relative_links: bool = False,
) -> ExportResult:
    """Export ``wiki_root`` as an OKF bundle at ``bundle_dir``.

    The source wiki is read-only. The bundle layout mirrors the wiki's
    subdirectory structure at the bundle root (no ``wiki/`` wrapper),
    so consumers can treat the bundle as a self-contained OKF Knowledge
    Bundle.

    ``relative_links=False`` (default) emits OKF-spec-recommended
    bundle-root-absolute links (``/concepts/rag.md``). Pass
    ``relative_links=True`` to emit file-relative links
    (``../entities/foo.md`` from ``concepts/rag.md``) instead — useful
    when the bundle is served to a renderer that doesn't follow the
    leading-slash form.
    """
    wiki_root = wiki_root.resolve()
    bundle_dir = bundle_dir.resolve()

    if not _wiki_root_is_valid(wiki_root):
        raise FileNotFoundError(
            f"No wiki found at {wiki_root} (missing AGENTS.md or wiki/index.md + wiki/log.md)"
        )

    if bundle_dir.exists():
        if any(bundle_dir.iterdir()) and not force:
            raise FileExistsError(
                f"Bundle directory {bundle_dir} is not empty (use --force to overwrite)"
            )
    else:
        bundle_dir.mkdir(parents=True)

    concepts = collect_concepts(wiki_root)
    slug_map = build_slug_map(wiki_root)

    by_dir: dict[str, list[ConceptRecord]] = {sd: [] for sd in WIKI_SUBDIRS}
    by_dir["overview"] = []
    for c in concepts:
        top = c.rel_path.split("/", 1)[0]
        by_dir.setdefault(top, []).append(c)

    total_rewrites = 0
    all_ambiguous: list[str] = []
    all_unresolved: list[str] = []

    # Write each concept file: rewritten links, OKF-shaped frontmatter.
    for c in concepts:
        out_path = bundle_dir / c.rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        source_dir = c.rel_path.split("/", 1)[0]
        new_body, rewrites, ambig, unres = rewrite_wikilinks(
            c.body,
            slug_map,
            source_dir,
            absolute_links=not relative_links,
            source_path=c.rel_path,
        )
        total_rewrites += rewrites
        all_ambiguous.extend(ambig)
        all_unresolved.extend(unres)

        okf_fm: dict = {"type": c.type, "title": c.title, "description": c.description}
        if c.tags:
            okf_fm["tags"] = c.tags
        if c.resource:
            okf_fm["resource"] = c.resource
        generated = build_generated(c.timestamp)
        if generated:
            okf_fm["generated"] = generated

        out_text = emit_frontmatter(okf_fm) + new_body.lstrip("\n")
        out_path.write_text(out_text, encoding="utf-8")

    # log.md is OKF-shaped already; pass through verbatim if present.
    src_log = wiki_root / "wiki" / "log.md"
    if src_log.is_file():
        (bundle_dir / "log.md").write_text(src_log.read_text(encoding="utf-8"), encoding="utf-8")

    # Bundle root index.md: okf_version in frontmatter, then directory listing.
    root_entries: list[tuple[str, str]] = []
    for sub in WIKI_SUBDIRS:
        sub_concepts = by_dir.get(sub, [])
        if not sub_concepts:
            continue
        root_entries.append(
            (
                f"{sub}/",
                f"{len(sub_concepts)} concept(s)",
            )
        )
    if by_dir.get("overview"):
        root_entries.append(("overview.md", "high-level synthesis across all sources"))
    write_index_md(
        bundle_dir / "index.md",
        f"{wiki_root.name} — Bundle Index",
        root_entries,
        source_rel_path="index.md",
        absolute_links=not relative_links,
    )
    # Inject okf_version frontmatter — only legal place for frontmatter in index.md.
    root_idx = bundle_dir / "index.md"
    current = root_idx.read_text(encoding="utf-8")
    root_idx.write_text(emit_frontmatter({"okf_version": OKF_VERSION}) + current, encoding="utf-8")

    # Per-subdirectory index.md.
    for sub in WIKI_SUBDIRS:
        sub_concepts = by_dir.get(sub, [])
        if not sub_concepts:
            continue
        entries = [(c.rel_path, c.description) for c in sub_concepts]
        title_word = _singularize(sub).capitalize()
        write_index_md(
            bundle_dir / sub / "index.md",
            title_word,
            entries,
            source_rel_path=f"{sub}/index.md",
            absolute_links=not relative_links,
        )

    # raw/ passthrough (symlinks preferred).
    src_raw = wiki_root / "raw"
    if src_raw.is_dir():
        _passthrough_raw(src_raw, bundle_dir / "raw")

    return ExportResult(
        bundle_dir=bundle_dir,
        concept_count=len(concepts),
        rewritten_links=total_rewrites,
        ambiguous_warnings=all_ambiguous,
        unresolved_warnings=all_unresolved,
    )
