"""Tests for the wikilink rewrite utility."""

from __future__ import annotations

from pathlib import Path


from lwiki.okf_export import parse_frontmatter
from lwiki.wikilink_rewrite import (
    _relative_path,
    rewrite_bundle,
    rewrite_text,
)


# --- helpers ---


def _make_bundle(
    root: Path,
    *,
    files: dict[str, str],
    link_in: tuple[str, str],
) -> None:
    """Build a tiny bundle from ``files`` (rel-path -> body).

    ``link_in`` is a (rel_path, wikilink_target_slug) pair to wire into a
    minimal slug map for unit-level calls.
    """
    (root / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n# root\n", encoding="utf-8"
    )
    (root / "log.md").write_text("# log\n", encoding="utf-8")
    for rel, body in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    _ = link_in  # silence unused-arg lint


def _slug_map_for(root: Path) -> dict[str, list[str]]:
    """Build the slug map the rewrite util would build for ``root``."""
    out: dict[str, list[str]] = {}
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root).as_posix()
        if rel in {"index.md", "log.md"}:
            continue
        out.setdefault(p.stem, []).append(rel)
    return out


# --- pure helpers ---


def test_relative_path_root_to_subdir() -> None:
    assert _relative_path(Path("overview.md"), Path("concepts/rag.md")) == "concepts/rag.md"


def test_relative_path_sibling_dir() -> None:
    assert (
        _relative_path(Path("concepts/democracy.md"), Path("entities/athens.md"))
        == "../entities/athens.md"
    )


def test_relative_path_same_file() -> None:
    assert _relative_path(Path("a.md"), Path("a.md")) == "a.md"


# --- rewrite_text ---


def test_rewrite_text_simple_relative() -> None:
    body = "See [[rag]] for details."
    slug_map = {"rag": ["concepts/rag.md"]}
    new_body, n, _, _ = rewrite_text(body, slug_map, "summaries/intro.md")
    assert n == 1
    assert "[rag](../concepts/rag.md)" in new_body


def test_rewrite_text_with_display_text() -> None:
    body = "See [[rag|Retrieval-Augmented Generation]] for details."
    slug_map = {"rag": ["concepts/rag.md"]}
    new_body, n, _, _ = rewrite_text(body, slug_map, "summaries/intro.md")
    assert "[Retrieval-Augmented Generation](../concepts/rag.md)" in new_body
    assert n == 1


def test_rewrite_text_with_anchor_strips_anchor() -> None:
    body = "See [[rag#Mechanism]] for details."
    slug_map = {"rag": ["concepts/rag.md"]}
    new_body, n, _, _ = rewrite_text(body, slug_map, "summaries/intro.md")
    assert "[rag](../concepts/rag.md)" in new_body


def test_rewrite_text_unresolved_keeps_original() -> None:
    body = "See [[missing-page]] for details."
    slug_map = {"rag": ["concepts/rag.md"]}
    new_body, n, _, unres = rewrite_text(body, slug_map, "concepts/democracy.md")
    assert n == 0
    assert "[[missing-page]]" in new_body
    assert len(unres) == 1


def test_rewrite_text_ambiguous_reports_warning() -> None:
    body = "See [[rag]] for details."
    slug_map = {
        "rag": ["concepts/rag.md", "entities/rag.md"],
    }
    new_body, n, amb, _ = rewrite_text(body, slug_map, "summaries/intro.md")
    assert n == 0
    assert "[[rag]]" in new_body
    assert len(amb) == 1


def test_rewrite_text_prefers_same_directory() -> None:
    body = "See [[rag]] for details."
    slug_map = {"rag": ["concepts/rag.md", "entities/rag.md"]}
    new_body, n, _, _ = rewrite_text(body, slug_map, "concepts/democracy.md")
    assert n == 1
    assert "[rag](rag.md)" in new_body  # same dir -> bare filename


def test_rewrite_text_absolute_mode() -> None:
    body = "See [[rag]] for details."
    slug_map = {"rag": ["concepts/rag.md"]}
    new_body, n, _, _ = rewrite_text(
        body, slug_map, "concepts/democracy.md", absolute_links=True
    )
    assert "[rag](/concepts/rag.md)" in new_body
    assert n == 1


# --- rewrite_bundle ---


def test_rewrite_bundle_writes_files(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    _make_bundle(
        bundle,
        files={
            "concepts/democracy.md": (
                "---\ntype: concept\ntitle: Democracy\n"
                "description: Athenian democracy.\n---\n\n"
                "See [[athens]].\n"
            ),
            "entities/athens.md": (
                "---\ntype: entity\ntitle: Athens\ndescription: City.\n---\n\n"
                "Body.\n"
            ),
        },
        link_in=("concepts/democracy.md", "athens"),
    )
    result = rewrite_bundle(bundle)
    assert result.links_rewritten == 1
    assert result.files_rewritten == 1

    body = (bundle / "concepts" / "democracy.md").read_text(encoding="utf-8")
    assert "[athens](../entities/athens.md)" in body
    fm, _ = parse_frontmatter(body)
    # Frontmatter preserved
    assert fm["type"] == "concept"
    assert fm["title"] == "Democracy"


def test_rewrite_bundle_dry_run_does_not_write(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    _make_bundle(
        bundle,
        files={
            "concepts/x.md": (
                "---\ntype: concept\ntitle: X\ndescription: x\n---\n\n"
                "See [[y]].\n"
            ),
            "concepts/y.md": "---\ntype: concept\ntitle: Y\ndescription: y\n---\n\n",
        },
        link_in=("concepts/x.md", "y"),
    )
    original = (bundle / "concepts" / "x.md").read_text(encoding="utf-8")
    result = rewrite_bundle(bundle, write=False)
    assert result.links_rewritten == 1
    assert (bundle / "concepts" / "x.md").read_text(encoding="utf-8") == original


def test_rewrite_bundle_skips_reserved_files(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n\n[[concepts]]\n",
        encoding="utf-8",
    )
    (bundle / "log.md").write_text("# log\n", encoding="utf-8")
    (bundle / "AGENTS.md").write_text("See [[concepts]]\n", encoding="utf-8")
    (bundle / "CLAUDE.md").write_text("See [[concepts]]\n", encoding="utf-8")
    (bundle / "README.md").write_text("See [[concepts]]\n", encoding="utf-8")
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntype: concept\ntitle: X\ndescription: x\n---\n\nSee [[y]].\n",
        encoding="utf-8",
    )
    (bundle / "concepts" / "y.md").write_text(
        "---\ntype: concept\ntitle: Y\ndescription: y\n---\n\n",
        encoding="utf-8",
    )
    result = rewrite_bundle(bundle)
    # Only the one concept file is rewritten; reserved files untouched.
    assert result.files_rewritten == 1
    assert result.files_scanned == 2  # both concept files are scanned
    # Reserved files still have the wikilink syntax (untouched)
    assert "[[concepts]]" in (bundle / "index.md").read_text(encoding="utf-8")
    assert "[[concepts]]" in (bundle / "AGENTS.md").read_text(encoding="utf-8")
    assert "[[concepts]]" in (bundle / "CLAUDE.md").read_text(encoding="utf-8")
    assert "[[concepts]]" in (bundle / "README.md").read_text(encoding="utf-8")


def test_rewrite_bundle_collects_warnings(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n\n", encoding="utf-8"
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntype: concept\ntitle: X\ndescription: x\n---\n\n"
        "See [[missing]] and [[another-missing]].\n",
        encoding="utf-8",
    )
    result = rewrite_bundle(bundle)
    assert result.links_rewritten == 0
    assert len(result.unresolved) == 2


def test_rewrite_bundle_absolute_flag(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    _make_bundle(
        bundle,
        files={
            "concepts/x.md": (
                "---\ntype: concept\ntitle: X\ndescription: x\n---\n\n"
                "See [[y]].\n"
            ),
            "concepts/y.md": "---\ntype: concept\ntitle: Y\ndescription: y\n---\n\n",
        },
        link_in=("concepts/x.md", "y"),
    )
    rewrite_bundle(bundle, absolute_links=True)
    body = (bundle / "concepts" / "x.md").read_text(encoding="utf-8")
    assert "[y](/concepts/y.md)" in body