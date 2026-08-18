"""Tests for the OKF exporter."""

from __future__ import annotations

from pathlib import Path

import pytest

from lwiki.okf_export import (
    build_slug_map,
    collect_concepts,
    emit_frontmatter,
    export_okf,
    parse_frontmatter,
    rewrite_wikilinks,
    write_index_md,
    WIKILINK_RE,
)


# --- parse_frontmatter / emit_frontmatter ---


def test_parse_frontmatter_basic() -> None:
    text = "---\ntitle: Foo\ntype: concept\n---\n\nBody text\n"
    fm, body = parse_frontmatter(text)
    assert fm["title"] == "Foo"
    assert fm["type"] == "concept"
    assert body.startswith("Body text")


def test_parse_frontmatter_empty() -> None:
    fm, body = parse_frontmatter("Just body, no frontmatter\n")
    assert fm == {}
    assert body == "Just body, no frontmatter\n"


def test_parse_frontmatter_invalid_yaml() -> None:
    text = "---\n: invalid: yaml: here\n---\n\nBody\n"
    fm, body = parse_frontmatter(text)
    # Invalid YAML should fall back to empty frontmatter, body preserved.
    assert fm == {}
    assert "Body" in body


def test_emit_frontmatter_roundtrip() -> None:
    fm = {"type": "concept", "title": "RAG", "tags": ["ai", "rag"]}
    text = emit_frontmatter(fm) + "Body\n"
    parsed, body = parse_frontmatter(text)
    assert parsed["type"] == "concept"
    assert parsed["title"] == "RAG"
    assert parsed["tags"] == ["ai", "rag"]
    assert "Body" in body


# --- wikilink rewriter ---


def test_wikilink_simple_rewrite() -> None:
    body = "See [[rag]] for details."
    slug_map = {"rag": ["concepts/rag.md"]}
    new_body, n, ambig, unres = rewrite_wikilinks(body, slug_map, "concepts")
    assert n == 1
    assert "[rag](/concepts/rag.md)" in new_body
    assert ambig == []
    assert unres == []


def test_wikilink_with_display() -> None:
    body = "See [[rag|Retrieval-Augmented Generation]] for details."
    slug_map = {"rag": ["concepts/rag.md"]}
    new_body, n, _, _ = rewrite_wikilinks(body, slug_map, "concepts")
    assert "[Retrieval-Augmented Generation](/concepts/rag.md)" in new_body
    assert n == 1


def test_wikilink_with_anchor_stripped() -> None:
    body = "See [[rag#section]] for details."
    slug_map = {"rag": ["concepts/rag.md"]}
    new_body, n, _, _ = rewrite_wikilinks(body, slug_map, "concepts")
    assert "[rag](/concepts/rag.md)" in new_body


def test_wikilink_unresolved_keeps_original() -> None:
    body = "See [[missing-page]] for details."
    slug_map = {"rag": ["concepts/rag.md"]}
    new_body, n, ambig, unres = rewrite_wikilinks(body, slug_map, "concepts")
    assert n == 0
    assert "[[missing-page]]" in new_body
    assert len(unres) == 1


def test_wikilink_ambiguous_reports_warning() -> None:
    body = "See [[rag]] for details."
    slug_map = {"rag": ["concepts/rag.md", "entities/rag.md"]}
    # Source dir is "summaries" — neither candidate matches, and there are 2
    new_body, n, ambig, unres = rewrite_wikilinks(body, slug_map, "summaries")
    assert n == 0
    assert "[[rag]]" in new_body
    assert len(ambig) == 1


def test_wikilink_prefers_same_directory() -> None:
    body = "See [[rag]] for details."
    slug_map = {"rag": ["concepts/rag.md", "entities/rag.md"]}
    # Source is in concepts/ — should prefer concepts/rag.md
    new_body, n, ambig, _ = rewrite_wikilinks(body, slug_map, "concepts")
    assert n == 1
    assert "[rag](/concepts/rag.md)" in new_body
    assert ambig == []


def test_wikilink_multiple_in_one_body() -> None:
    body = "[[foo]] and [[bar]] and [[baz]]"
    slug_map = {
        "foo": ["concepts/foo.md"],
        "bar": ["concepts/bar.md"],
    }
    new_body, n, _, unres = rewrite_wikilinks(body, slug_map, "concepts")
    assert n == 2
    assert "[foo](/concepts/foo.md)" in new_body
    assert "[bar](/concepts/bar.md)" in new_body
    assert "[[baz]]" in new_body
    assert len(unres) == 1


# --- index.md writer ---


def test_write_index_md_bullet_format(tmp_path: Path) -> None:
    out = tmp_path / "index.md"
    write_index_md(
        out,
        "Concepts",
        [("concepts/rag.md", "Retrieval-Augmented Generation overview.")],
    )
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Concepts\n")
    assert "* [rag](/concepts/rag.md) - Retrieval-Augmented Generation overview." in text


def test_write_index_md_handles_missing_description(tmp_path: Path) -> None:
    out = tmp_path / "index.md"
    write_index_md(out, "Concepts", [("concepts/x.md", "")])
    text = out.read_text(encoding="utf-8")
    assert "(no description)" in text


# --- end-to-end export ---


def _make_sample_wiki(root: Path) -> None:
    """Build a tiny wiki at root/ with two concepts cross-linking."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "AGENTS.md").write_text("# Sample Wiki\n", encoding="utf-8")
    wiki = root / "wiki"
    (wiki / "summaries").mkdir(parents=True)
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "entities").mkdir(parents=True)
    (wiki / "insights").mkdir(parents=True)

    (wiki / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    (wiki / "log.md").write_text("# Wiki Log\n", encoding="utf-8")
    (wiki / "overview.md").write_text(
        "---\ntitle: Overview\ntype: overview\ndescription: Big picture.\n"
        "tags: [overview]\nupdated: 2026-07-01\n---\n\n# Overview\n\n"
        "See [[rag]].\n",
        encoding="utf-8",
    )

    (wiki / "concepts" / "rag.md").write_text(
        "---\ntitle: RAG\ntype: concept\ndescription: Retrieval-Augmented Generation.\n"
        "tags: [ai]\nresource: https://example.com/rag\nupdated: 2026-07-02\n---\n\n"
        "# RAG\n\nSee also [[transformer]] and [[rag|this same page]].\n",
        encoding="utf-8",
    )

    (wiki / "summaries" / "intro.md").write_text(
        "---\ntitle: Intro\ntype: summary\ndescription: A summary.\ntags: [meta]\n"
        "sources: [raw/intro.md]\nupdated: 2026-07-03\n---\n\n# Intro\n\nRefers to [[rag]].\n",
        encoding="utf-8",
    )

    # raw/ with a small file
    raw = root / "raw"
    raw.mkdir()
    (raw / "intro.md").write_text("# Raw intro\n", encoding="utf-8")


def test_export_creates_bundle_with_required_files(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    bundle = tmp_path / "bundle"
    _make_sample_wiki(wiki)
    result = export_okf(wiki, bundle)
    assert result.concept_count == 3  # overview + rag + intro
    assert (bundle / "index.md").is_file()
    assert (bundle / "log.md").is_file()
    assert (bundle / "overview.md").is_file()
    assert (bundle / "concepts" / "rag.md").is_file()
    assert (bundle / "summaries" / "intro.md").is_file()


def test_export_root_index_has_okf_version(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    bundle = tmp_path / "bundle"
    _make_sample_wiki(wiki)
    export_okf(wiki, bundle)
    text = (bundle / "index.md").read_text(encoding="utf-8")
    # okf_version declared as the only place frontmatter is allowed in index.md.
    # OKF 0.2 bumped from "0.1" — see SPEC.md breaking changes.
    assert text.startswith("---\n")
    assert "okf_version: '0.2'" in text or 'okf_version: "0.2"' in text


def test_export_concept_uses_okf02_generated_mapping(tmp_path: Path) -> None:
    """OKF 0.2: last-change moves from ``timestamp`` to ``generated: {by, at}``."""
    wiki = tmp_path / "wiki"
    bundle = tmp_path / "bundle"
    _make_sample_wiki(wiki)
    export_okf(wiki, bundle)
    rag = (bundle / "concepts" / "rag.md").read_text(encoding="utf-8")
    fm = parse_frontmatter(rag)[0]
    # New mapping is present and shaped per OKF 0.2.
    assert "timestamp" not in fm
    assert isinstance(fm.get("generated"), dict)
    assert fm["generated"]["by"] == "llm-wiki/0.2"
    assert fm["generated"]["at"] == "2026-07-02"


def test_export_concept_frontmatter_omits_wiki_only_fields(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    bundle = tmp_path / "bundle"
    _make_sample_wiki(wiki)
    export_okf(wiki, bundle)
    intro = (bundle / "summaries" / "intro.md").read_text(encoding="utf-8")
    # `sources` is wiki-internal lineage; not surfaced in OKF frontmatter.
    assert "sources:" not in intro.split("---", 2)[1]
    # but `description` and `type` are present.
    fm = parse_frontmatter(intro)[0]
    assert fm["type"] == "summary"
    assert fm["description"] == "A summary."


def test_export_rewrites_cross_links(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    bundle = tmp_path / "bundle"
    _make_sample_wiki(wiki)
    result = export_okf(wiki, bundle)

    # overview.md: bare `[[rag]]` rewrites to a path-style link.
    overview = (bundle / "overview.md").read_text(encoding="utf-8")
    assert "[rag](/concepts/rag.md)" in overview

    # concepts/rag.md: `[[rag|this same page]]` rewrites with display text.
    rag = (bundle / "concepts" / "rag.md").read_text(encoding="utf-8")
    assert "[this same page](/concepts/rag.md)" in rag
    assert "[[transformer]]" in rag  # unresolved, kept as-is

    # summaries/intro.md: `[[rag]]` rewrites to a path-style link.
    intro = (bundle / "summaries" / "intro.md").read_text(encoding="utf-8")
    assert "[rag](/concepts/rag.md)" in intro

    # Result reports the unresolved warning and a healthy rewrite count.
    assert any("transformer" in w for w in result.unresolved_warnings)
    assert result.rewritten_links >= 3  # overview→rag, intro→rag, rag→rag


def test_export_passes_raw_via_symlink(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    bundle = tmp_path / "bundle"
    _make_sample_wiki(wiki)
    export_okf(wiki, bundle)
    raw_intro = bundle / "raw" / "intro.md"
    assert raw_intro.exists()
    # symlink on linux, fallback to copy on Windows
    assert raw_intro.is_symlink() or raw_intro.is_file()


def test_export_refuses_non_empty_output_without_force(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    bundle = tmp_path / "bundle"
    _make_sample_wiki(wiki)
    export_okf(wiki, bundle)
    # Second export without --force should raise
    with pytest.raises(FileExistsError):
        export_okf(wiki, bundle, force=False)


def test_export_force_overwrites(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    bundle = tmp_path / "bundle"
    _make_sample_wiki(wiki)
    export_okf(wiki, bundle)
    # Force should succeed and rewrite
    result = export_okf(wiki, bundle, force=True)
    assert result.concept_count == 3


def test_export_missing_wiki_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        export_okf(tmp_path / "nope", tmp_path / "bundle")


def test_export_subdirectory_index_lists_concepts(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    bundle = tmp_path / "bundle"
    _make_sample_wiki(wiki)
    export_okf(wiki, bundle)
    concepts_idx = (bundle / "concepts" / "index.md").read_text(encoding="utf-8")
    assert "* [rag](/concepts/rag.md)" in concepts_idx
    assert "Retrieval-Augmented Generation" in concepts_idx


def test_export_root_index_lists_subdirs(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    bundle = tmp_path / "bundle"
    _make_sample_wiki(wiki)
    export_okf(wiki, bundle)
    root_idx = (bundle / "index.md").read_text(encoding="utf-8")
    # Subdir entries appear as OKF bullet list with descriptions
    assert "[concepts](/concepts/)" in root_idx
    assert "[summaries](/summaries/)" in root_idx


def test_export_drops_wiki_only_frontmatter_fields(tmp_path: Path) -> None:
    """`sources` (raw-file lineage) and `cited` (insight citations) are wiki
    internals. OKF consumers don't need them in the bundle frontmatter."""
    wiki = tmp_path / "wiki"
    bundle = tmp_path / "bundle"
    _make_sample_wiki(wiki)
    # Add an insight with cited/sources
    (wiki / "wiki" / "insights" / "synthesis.md").write_text(
        "---\ntitle: Synthesis\ntype: insight\ndescription: An insight.\n"
        "cited: [rag]\nsources: [raw/intro.md]\nupdated: 2026-07-04\n---\n\n"
        "Insight body.\n",
        encoding="utf-8",
    )
    export_okf(wiki, bundle)
    insight = (bundle / "insights" / "synthesis.md").read_text(encoding="utf-8")
    fm = parse_frontmatter(insight)[0]
    assert "cited" not in fm
    assert "sources" not in fm
    assert fm["type"] == "insight"


# --- slug map + collect ---


def test_collect_concepts_skips_missing_subdirs(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _make_sample_wiki(wiki)
    # Remove one subdir; collect should not blow up.
    (wiki / "wiki" / "entities").rmdir()
    concepts = collect_concepts(wiki)
    paths = {c.rel_path for c in concepts}
    assert "concepts/rag.md" in paths
    assert "summaries/intro.md" in paths


def test_build_slug_map_handles_overview(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _make_sample_wiki(wiki)
    slug_map = build_slug_map(wiki)
    assert slug_map["rag"] == ["concepts/rag.md"]
    assert slug_map["overview"] == ["overview.md"]


# --- regex sanity ---


def test_wikilink_regex_matches() -> None:
    cases = [
        ("[[slug]]", "slug", None),
        ("[[slug|display]]", "slug", "display"),
        ("[[my-thing]]", "my-thing", None),
        ("[[my-thing|My Thing]]", "my-thing", "My Thing"),
    ]
    for text, expected_slug, expected_display in cases:
        m = WIKILINK_RE.fullmatch(text)
        assert m is not None, f"failed to match: {text}"
        assert m.group(1) == expected_slug
        assert m.group(2) == expected_display


# --- CLI integration ---


def test_cli_export_okf_creates_bundle(tmp_path: Path) -> None:
    """End-to-end via Typer runner."""
    from typer.testing import CliRunner

    from lwiki.cli import app

    runner = CliRunner()
    wiki = tmp_path / "wiki"
    bundle = tmp_path / "bundle"
    _make_sample_wiki(wiki)
    r = runner.invoke(app, ["export", "okf", str(wiki), "--out", str(bundle)])
    assert r.exit_code == 0, r.output
    assert (bundle / "index.md").is_file()
    assert "Exported" in r.output
