"""Tests for the OKF conformance validator."""

from __future__ import annotations

from pathlib import Path


from lwiki.conformance import (
    KNOWN_STATUS,
    KNOWN_TYPES,
    Level,
    Violation,
    is_conformant,
    validate_bundle,
)


def _make_bundle(root: Path) -> None:
    """Build a minimal OKF bundle: root index + overview + a concept."""
    (root / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n\n# Bundle Index\n",
        encoding="utf-8",
    )
    (root / "log.md").write_text("# Log\n", encoding="utf-8")
    (root / "concepts").mkdir()
    (root / "concepts" / "rag.md").write_text(
        "---\ntype: concept\ntitle: RAG\ndescription: Retrieval-Augmented Generation.\n"
        "tags: [ai]\n"
        "generated: { by: 'lwiki/0.2', at: '2026-08-01' }\n---\n\n# RAG\n",
        encoding="utf-8",
    )


def _codes(violations: list[Violation]) -> set[str]:
    return {v.code for v in violations}


def _errors(violations: list[Violation]) -> list[Violation]:
    return [v for v in violations if v.level == Level.ERROR]


# --- happy path ---


def test_minimal_conformant_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    _make_bundle(bundle)
    violations = validate_bundle(bundle)
    assert violations == [], violations
    assert is_conformant(violations) is True


def test_empty_bundle_with_root_index_passes(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n\n# empty\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    assert _errors(violations) == []


def test_missing_bundle_directory_errors(tmp_path: Path) -> None:
    violations = validate_bundle(tmp_path / "nope")
    assert any(v.code == "bundle.missing" for v in violations)
    assert is_conformant(violations) is False


# --- root index ---


def test_root_index_missing_errors(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    violations = validate_bundle(bundle)
    assert "root.index_missing" in _codes(violations)


def test_root_index_missing_okf_version_errors(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text("# no frontmatter\n", encoding="utf-8")
    violations = validate_bundle(bundle)
    assert "root.okf_version_missing" in _codes(violations)


def test_root_index_wrong_okf_version_warns(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.1'\n---\n\n# old\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    assert "root.okf_version_wrong" in _codes(violations)
    # still parseable; no ERROR
    assert is_conformant(violations) is True


# --- legacy wiki/ wrapper ---


def test_legacy_wiki_wrapper_errors(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n\n# x\n",
        encoding="utf-8",
    )
    # legacy wiki/ with concept subdirs still inside
    (bundle / "wiki" / "concepts").mkdir(parents=True)
    (bundle / "wiki" / "concepts" / "rag.md").write_text(
        "---\ntype: concept\n---\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    assert "legacy.wiki_wrapper" in _codes(violations)


def test_inert_wiki_dir_does_not_error(tmp_path: Path) -> None:
    """``wiki/`` with no concept subdirs is treated as inert (user-owned)."""
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n\n# x\n",
        encoding="utf-8",
    )
    (bundle / "wiki").mkdir()
    (bundle / "wiki" / "notes.md").write_text("# personal notes\n", encoding="utf-8")
    violations = validate_bundle(bundle)
    assert "legacy.wiki_wrapper" not in _codes(violations)


# --- concept file shape ---


def test_concept_missing_frontmatter_errors(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text("no frontmatter here\n", encoding="utf-8")
    violations = validate_bundle(bundle)
    assert "concept.frontmatter_missing" in _codes(violations)


def test_concept_missing_type_errors(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntitle: X\n---\n\nbody\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    assert "concept.type_missing" in _codes(violations)


def test_concept_unknown_type_is_info(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntype: future-thing\n---\n\nbody\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    info = [v for v in violations if v.level == Level.INFO]
    assert any(v.code == "concept.type_unknown" for v in info)
    assert is_conformant(violations) is True


def test_concept_with_all_known_types_is_clean(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    for sub, slug in [
        ("summaries", "summary.md"),
        ("concepts", "concept.md"),
        ("entities", "entity.md"),
        ("insights", "insight.md"),
        ("", "overview.md"),
    ]:
        if sub:
            (bundle / sub).mkdir(exist_ok=True)
        target = (bundle / sub / slug) if sub else (bundle / slug)
        target.write_text(
            f"---\ntype: {slug.removesuffix('.md')}\n---\n",
            encoding="utf-8",
        )
    violations = validate_bundle(bundle)
    assert _errors(violations) == []


# --- reserved filenames ---


def test_reserved_filename_in_subdir_errors(tmp_path: Path) -> None:
    """Reserved filenames are not allowed as concept files in subdirs.

    `index.md` in a concept subdir is treated as a per-directory index and
    is allowed (see ``test_directory_index_in_subdir_passes`` below); only
    `log.md` outside the bundle root still triggers the rule.
    """
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "log.md").write_text(
        "---\ntype: concept\n---\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    assert "concept.reserved_filename" in _codes(violations)


def test_directory_index_in_subdir_passes(tmp_path: Path) -> None:
    """`<subdir>/index.md` is OKF's per-directory listing convention.

    A bullet-list directory index without frontmatter is allowed and is
    exempt from concept frontmatter checks.
    """
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "index.md").write_text(
        "# Concepts\n\n* [rag](rag.md) - retrieval-augmented generation\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    assert "concept.reserved_filename" not in _codes(violations)
    assert _errors(violations) == []


# --- generated / sources / verified / status ---


def test_generated_malformed_errors(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntype: concept\ngenerated: '2026-08-01'\n---\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    assert "generated.malformed" in _codes(violations)


def test_generated_missing_at_warns(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntype: concept\ngenerated: { by: 'lwiki/0.2' }\n---\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    assert "generated.at_missing" in _codes(violations)


def test_sources_string_entries_allowed(tmp_path: Path) -> None:
    """Bare strings in ``sources`` (legacy wiki shape) are tolerated."""
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntype: concept\nsources:\n  - raw/foo.md\n  - { resource: 'raw/bar.md' }\n---\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    assert "sources.entry_malformed" not in _codes(violations)
    assert _errors(violations) == []


def test_sources_malformed_errors(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntype: concept\nsources: 'not a list'\n---\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    assert "sources.malformed" in _codes(violations)


def test_verified_malformed_errors(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntype: concept\nverified: 'string'\n---\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    assert "verified.malformed" in _codes(violations)


def test_verified_entry_without_at_warns(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntype: concept\nverified:\n  - { by: 'human:x' }\n---\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    assert "verified.entry_incomplete" in _codes(violations)


def test_status_must_be_known_value(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    for status, should_pass in [("draft", True), ("stable", True), ("deprecated", True), ("wip", False)]:
        (bundle / "concepts" / "x.md").write_text(
            f"---\ntype: concept\nstatus: {status}\n---\n",
            encoding="utf-8",
        )
        violations = validate_bundle(bundle)
        has_error = any(v.code == "status.malformed" for v in _errors(violations))
        assert has_error is not should_pass, f"status={status!r}"


def test_status_known_values_constant() -> None:
    assert KNOWN_STATUS == {"draft", "stable", "deprecated"}


def test_known_types_constant() -> None:
    assert {"summary", "concept", "entity", "insight", "overview"} <= KNOWN_TYPES


# --- attested-computation ---


def test_attested_computation_requires_keys(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "compute.md").write_text(
        "---\ntype: attested-computation\n---\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    expected_codes = {
        "attested.runtime_missing",
        "attested.parameters_missing",
        "attested.computation_missing",
        "attested.executor_missing",
        "attested.attester_missing",
    }
    assert expected_codes <= _codes(violations)


def test_attested_computation_full_is_clean(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n",
        encoding="utf-8",
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "compute.md").write_text(
        "---\ntype: attested-computation\n"
        "runtime: python3\n"
        "parameters:\n  x: int\n"
        "computation: scripts/compute.py\n"
        "executor: { resource: 'scripts/run.sh', receipt: 'out/receipt.json' }\n"
        "attester: { resource: 'scripts/verify.py' }\n---\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    assert _errors(violations) == []


# --- shape of violations ---


def test_violation_paths_are_bundle_relative() -> None:
    v = Violation(Level.ERROR, "x", "msg", path="concepts/rag.md")
    assert v.path == "concepts/rag.md"


def test_is_conformant_ignores_warnings(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.1'\n---\n",
        encoding="utf-8",
    )
    violations = validate_bundle(bundle)
    # only a WARN, not an ERROR
    assert is_conformant(violations) is True
    assert any(v.level == Level.WARN for v in violations)