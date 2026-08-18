"""Tests for ``lwiki.conformance`` — the OKF 0.2 bundle validator."""

from __future__ import annotations

from pathlib import Path

import pytest

from lwiki.conformance import (
    ALLOWED_STATUS,
    CONCEPT_SUBDIRS,
    OKF_VERSION,
    RESERVED_FILES,
    Violation,
    validate_bundle,
)

# ---------------------------------------------------------------------------
# Helpers — build minimal bundles in tmp_path.
# ---------------------------------------------------------------------------


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _fm_block(parts: dict[str, object]) -> str:
    """Render a YAML frontmatter block from a dict (no body)."""
    import yaml

    if not parts:
        return ""
    rendered = yaml.safe_dump(parts, sort_keys=False, allow_unicode=True).rstrip()
    return f"---\n{rendered}\n---\n\n"


def _ok_concept_fm() -> dict[str, object]:
    """A concept frontmatter that satisfies every rule."""
    return {
        "type": "concept",
        "title": "RAG",
        "description": "Retrieval-Augmented Generation overview.",
        "tags": ["ai"],
    }


def _make_ok_bundle(root: Path) -> None:
    """Build a minimal bundle that should pass every rule."""
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "index.md", _fm_block({"okf_version": OKF_VERSION}) + "# Index\n")
    _write(root / "log.md", "# Log\n")
    _write(root / "overview.md", _fm_block(_ok_concept_fm() | {"type": "overview"}) + "Body\n")
    _write(
        root / "concepts" / "rag.md",
        _fm_block(_ok_concept_fm()) + "Body\n",
    )
    _write(
        root / "summaries" / "intro.md",
        _fm_block(_ok_concept_fm() | {"type": "summary"}) + "Body\n",
    )


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_module_exposes_okf_version_constant() -> None:
    assert OKF_VERSION == "0.2"


def test_module_exposes_reserved_files_constant() -> None:
    assert RESERVED_FILES == frozenset({"index.md", "log.md"})


def test_module_exposes_concept_subdirs_constant() -> None:
    assert CONCEPT_SUBDIRS == frozenset(
        {"summaries", "concepts", "entities", "insights"}
    )


def test_module_exposes_allowed_status_constant() -> None:
    assert ALLOWED_STATUS == frozenset({"draft", "stable", "deprecated"})


def test_violation_dataclass_is_immutable() -> None:
    v = Violation(path="concepts/rag.md", rule="type_missing", message="hi")
    assert v.path == "concepts/rag.md"
    assert v.rule == "type_missing"
    assert v.message == "hi"
    with pytest.raises(Exception):
        v.rule = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_ok_bundle_returns_no_violations(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    assert validate_bundle(bundle) == []


def test_missing_bundle_directory_returns_violation(tmp_path: Path) -> None:
    out = validate_bundle(tmp_path / "does-not-exist")
    assert len(out) == 1
    assert out[0].rule == "bundle_not_found"
    assert out[0].path == ""


# ---------------------------------------------------------------------------
# okf_version
# ---------------------------------------------------------------------------


def test_root_index_missing_is_violation(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    out = validate_bundle(bundle)
    assert any(v.rule == "okf_version_missing" for v in out)


def test_root_index_missing_okf_version_key(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _write(bundle / "index.md", "---\nfoo: bar\n---\n\nBody\n")
    out = validate_bundle(bundle)
    rule_paths = [(v.rule, v.path) for v in out]
    assert ("okf_version_missing", "index.md") in rule_paths


def test_root_index_with_wrong_okf_version(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _write(bundle / "index.md", _fm_block({"okf_version": "0.1"}) + "Body\n")
    out = validate_bundle(bundle)
    bad = [v for v in out if v.rule == "okf_version_wrong"]
    assert len(bad) == 1
    assert bad[0].path == "index.md"
    assert "0.2" in bad[0].message


# ---------------------------------------------------------------------------
# Frontmatter presence
# ---------------------------------------------------------------------------


def test_concept_file_with_no_frontmatter(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    # Replace one concept file with body-only content.
    _write(bundle / "concepts" / "rag.md", "Body without frontmatter\n")
    out = validate_bundle(bundle)
    bad = [v for v in out if v.rule == "no_frontmatter"]
    assert len(bad) == 1
    assert bad[0].path == "concepts/rag.md"
    assert "missing" in bad[0].message


def test_concept_file_with_unparseable_frontmatter(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    _write(bundle / "concepts" / "rag.md", "---\n: bad: yaml: here\n---\n\nBody\n")
    out = validate_bundle(bundle)
    bad = [v for v in out if v.rule == "no_frontmatter"]
    assert len(bad) == 1
    assert bad[0].path == "concepts/rag.md"
    assert "unparseable" in bad[0].message


def test_concept_file_with_frontmatter_not_a_mapping(tmp_path: Path) -> None:
    """YAML that parses to a list/scalar is treated as unparseable."""
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    _write(bundle / "concepts" / "rag.md", "---\n- not\n- a\n- mapping\n---\n\nBody\n")
    out = validate_bundle(bundle)
    assert any(
        v.rule == "no_frontmatter" and v.path == "concepts/rag.md" for v in out
    )


# ---------------------------------------------------------------------------
# type
# ---------------------------------------------------------------------------


def test_concept_missing_type(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    _write(
        bundle / "concepts" / "rag.md",
        _fm_block({"title": "RAG"}) + "Body\n",
    )
    out = validate_bundle(bundle)
    bad = [v for v in out if v.rule == "type_missing"]
    assert len(bad) == 1
    assert bad[0].path == "concepts/rag.md"


def test_concept_empty_type(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    _write(bundle / "concepts" / "rag.md", _fm_block({"type": ""}) + "Body\n")
    out = validate_bundle(bundle)
    assert any(v.rule == "type_empty" for v in out)


def test_concept_whitespace_only_type(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    _write(bundle / "concepts" / "rag.md", _fm_block({"type": "   "}) + "Body\n")
    out = validate_bundle(bundle)
    assert any(v.rule == "type_empty" for v in out)


def test_concept_non_string_type(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    _write(bundle / "concepts" / "rag.md", _fm_block({"type": 42}) + "Body\n")
    out = validate_bundle(bundle)
    assert any(v.rule == "type_empty" for v in out)


# ---------------------------------------------------------------------------
# generated
# ---------------------------------------------------------------------------


def test_generated_missing_by(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"generated": {"at": "2026-01-01"}}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    out = validate_bundle(bundle)
    assert any(
        v.rule == "generated_malformed" and v.path == "concepts/rag.md"
        for v in out
    )


def test_generated_missing_at(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"generated": {"by": "llm-wiki/0.2"}}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    out = validate_bundle(bundle)
    assert any(v.rule == "generated_malformed" for v in out)


def test_generated_non_string_values(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"generated": {"by": 1, "at": 2}}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    out = validate_bundle(bundle)
    assert any(v.rule == "generated_malformed" for v in out)


def test_generated_not_a_mapping(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"generated": "llm-wiki/0.2 at 2026-01-01"}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    out = validate_bundle(bundle)
    assert any(v.rule == "generated_malformed" for v in out)


def test_generated_well_formed_passes(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"generated": {"by": "llm-wiki/0.2", "at": "2026-01-01"}}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    assert validate_bundle(bundle) == []


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------


def test_sources_must_be_a_list(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"sources": "raw/foo.md"}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    out = validate_bundle(bundle)
    assert any(v.rule == "sources_malformed" for v in out)


def test_sources_string_entries_pass(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"sources": ["raw/foo.md", "raw/bar.md"]}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    assert validate_bundle(bundle) == []


def test_sources_mapping_with_resource_passes(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {
        "sources": [{"resource": "https://example.com/rag"}]
    }
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    assert validate_bundle(bundle) == []


def test_sources_mapping_with_last_modified_passes(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"sources": [{"last_modified": "2026-01-01"}]}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    assert validate_bundle(bundle) == []


def test_sources_mapping_with_neither_resource_nor_last_modified(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"sources": [{"foo": "bar"}]}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    out = validate_bundle(bundle)
    bad = [v for v in out if v.rule == "sources_malformed"]
    assert any("resource" in v.message and "last_modified" in v.message for v in bad)


def test_sources_entry_wrong_type(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"sources": [42]}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    out = validate_bundle(bundle)
    assert any(v.rule == "sources_malformed" for v in out)


# ---------------------------------------------------------------------------
# verified
# ---------------------------------------------------------------------------


def test_verified_must_be_a_list(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"verified": "not-a-list"}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    out = validate_bundle(bundle)
    assert any(v.rule == "verified_malformed" for v in out)


def test_verified_entry_missing_by_or_at(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"verified": [{"by": "alice"}, {"at": "2026-01-01"}]}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    out = validate_bundle(bundle)
    bad = [v for v in out if v.rule == "verified_malformed"]
    assert len(bad) == 2


def test_verified_entry_wrong_type(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"verified": ["not-a-mapping"]}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    out = validate_bundle(bundle)
    assert any(v.rule == "verified_malformed" for v in out)


def test_verified_well_formed_passes(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {
        "verified": [
            {"by": "alice", "at": "2026-01-01"},
            {"by": "bob", "at": "2026-02-02"},
        ]
    }
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    assert validate_bundle(bundle) == []


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_invalid_value(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = _ok_concept_fm() | {"status": "wip"}
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    out = validate_bundle(bundle)
    bad = [v for v in out if v.rule == "status_invalid"]
    assert len(bad) == 1
    assert "draft" in bad[0].message and "stable" in bad[0].message


def test_status_each_allowed_value_passes(tmp_path: Path) -> None:
    for allowed in sorted(ALLOWED_STATUS):
        bundle = tmp_path / "bundle"
        _make_ok_bundle(bundle)
        fm = _ok_concept_fm() | {"status": allowed}
        _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
        assert validate_bundle(bundle) == [], f"status={allowed!r} should pass"


# ---------------------------------------------------------------------------
# Reserved filenames
# ---------------------------------------------------------------------------


def test_reserved_index_md_inside_concept_subdir(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    _write(bundle / "concepts" / "index.md", _fm_block(_ok_concept_fm()) + "Body\n")
    out = validate_bundle(bundle)
    bad = [v for v in out if v.rule == "reserved_filename_in_subdir"]
    assert len(bad) == 1
    assert bad[0].path == "concepts/index.md"
    assert "concepts/" in bad[0].message


def test_reserved_log_md_inside_concept_subdir(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    _write(bundle / "summaries" / "log.md", _fm_block(_ok_concept_fm()) + "Body\n")
    out = validate_bundle(bundle)
    bad = [v for v in out if v.rule == "reserved_filename_in_subdir"]
    assert len(bad) == 1
    assert bad[0].path == "summaries/log.md"


def test_reserved_filename_at_bundle_root_is_ok(tmp_path: Path) -> None:
    """index.md and log.md at the bundle root are legal (root log.md is
    pass-through; root index.md is checked separately for okf_version)."""
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    assert validate_bundle(bundle) == []


# ---------------------------------------------------------------------------
# Layout: no concept files under wiki/
# ---------------------------------------------------------------------------


def test_concept_under_wiki_layout_violation(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    _write(
        bundle / "wiki" / "concepts" / "rag.md",
        _fm_block(_ok_concept_fm()) + "Body\n",
    )
    out = validate_bundle(bundle)
    bad = [v for v in out if v.rule == "wiki_layout_pre_migration"]
    assert len(bad) == 1
    assert bad[0].path == "wiki/concepts/rag.md"
    assert "post-migration" in bad[0].message


def test_concept_under_wiki_root_index_violation(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    _write(bundle / "wiki" / "index.md", _fm_block(_ok_concept_fm()) + "Body\n")
    out = validate_bundle(bundle)
    assert any(
        v.rule == "wiki_layout_pre_migration" and v.path == "wiki/index.md"
        for v in out
    )


# ---------------------------------------------------------------------------
# Aggregations / cross-rule
# ---------------------------------------------------------------------------


def test_violations_are_deterministic_and_sorted(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    # Multiple violations across multiple files.
    _write(bundle / "concepts" / "rag.md", _fm_block({"type": ""}) + "Body\n")
    _write(bundle / "summaries" / "intro.md", "No frontmatter\n")
    _write(bundle / "concepts" / "index.md", _fm_block(_ok_concept_fm()) + "Body\n")
    _write(bundle / "wiki" / "concepts" / "rag.md", _fm_block(_ok_concept_fm()) + "Body\n")
    out = validate_bundle(bundle)
    # Same input twice -> identical output.
    assert out == validate_bundle(bundle)
    # Output is in stable order (sorted by bundle-relative path).
    paths = [v.path for v in out]
    assert paths == sorted(paths)
    # All four problem files surfaced.
    rules = {v.rule for v in out}
    assert {"type_empty", "no_frontmatter", "reserved_filename_in_subdir", "wiki_layout_pre_migration"} <= rules


def test_violations_collect_all_problems_not_just_first(tmp_path: Path) -> None:
    """A file with multiple problems should yield multiple Violations."""
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    fm = {
        "type": "",  # type_empty
        "status": "wip",  # status_invalid
        "generated": "bad",  # generated_malformed
        "sources": [{"foo": "bar"}],  # sources_malformed
        "verified": "nope",  # verified_malformed
    }
    _write(bundle / "concepts" / "rag.md", _fm_block(fm) + "Body\n")
    out = validate_bundle(bundle)
    rag = [v for v in out if v.path == "concepts/rag.md"]
    rules = {v.rule for v in rag}
    assert rules == {
        "type_empty",
        "status_invalid",
        "generated_malformed",
        "sources_malformed",
        "verified_malformed",
    }


def test_subdir_not_a_concept_subdir_allows_index_md(tmp_path: Path) -> None:
    """Per the issue wording, the reserved-name rule applies to *concept*
    subdirs only. A non-concept subdir may host an index.md (e.g. assets/)."""
    bundle = tmp_path / "bundle"
    _make_ok_bundle(bundle)
    _write(bundle / "assets" / "index.md", "# Asset listing\n")
    out = validate_bundle(bundle)
    # No reserved-filename violation; assets/index.md is outside the four
    # concept subdirs.
    assert not any(
        v.rule == "reserved_filename_in_subdir" for v in out
    )