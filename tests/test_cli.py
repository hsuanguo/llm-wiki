"""CLI smoke tests via Typer runner."""

from pathlib import Path

from typer.testing import CliRunner

from lwiki.cli import app
from lwiki.conformance import is_conformant, validate_bundle

runner = CliRunner()


def test_help() -> None:
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    assert "lwiki" in r.stdout.lower() or "LLM Wiki" in r.stdout


def test_raw_status_help() -> None:
    r = runner.invoke(app, ["raw", "status", "--help"])
    assert r.exit_code == 0


# --- init (OKF-native) ---


def test_init_creates_okf_bundle(tmp_path: Path) -> None:
    target = tmp_path / "mybundle"
    r = runner.invoke(
        app,
        ["init", str(target), "--domain", "Test", "--sources", "urls"],
    )
    assert r.exit_code == 0, r.output
    # No wiki/ wrapper; concepts at the bundle root.
    assert (target / "index.md").is_file()
    assert (target / "log.md").is_file()
    assert (target / "overview.md").is_file()
    assert (target / "AGENTS.md").is_file()
    assert (target / "CLAUDE.md").is_file()
    assert (target / "raw" / "files.log").is_file()
    for sub in ("summaries", "concepts", "entities", "insights"):
        assert (target / sub).is_dir(), f"{sub}/ not created"
    assert not (target / "wiki").is_dir(), "wiki/ wrapper must be gone"


def test_init_bundle_passes_conformance(tmp_path: Path) -> None:
    target = tmp_path / "conformant"
    runner.invoke(app, ["init", str(target), "-d", "Greek History"])
    violations = validate_bundle(target)
    assert is_conformant(violations), violations
    # The only expected findings, if any, would be WARN / INFO — not ERROR.
    assert all(v.level.value != "error" for v in violations)


def test_init_refuses_double_init(tmp_path: Path) -> None:
    target = tmp_path / "b"
    runner.invoke(app, ["init", str(target)])
    r = runner.invoke(app, ["init", str(target)])
    assert r.exit_code == 1


def test_init_default_sources_in_agents(tmp_path: Path) -> None:
    target = tmp_path / "b2"
    r = runner.invoke(app, ["init", str(target), "-d", "Only Domain"])
    assert r.exit_code == 0, r.output
    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "Only Domain" in agents
    assert "articles, URLs, papers" in agents
    assert "## Source Types" in agents


def test_init_claude_md_imports_agents_md(tmp_path: Path) -> None:
    """CLAUDE.md must exist and import AGENTS.md so Claude Code loads the
    OKF-native conventions from the same source as other agents."""
    target = tmp_path / "b_claude"
    runner.invoke(app, ["init", str(target)])
    claude = (target / "CLAUDE.md").read_text(encoding="utf-8")
    assert "@AGENTS.md" in claude
    assert "AGENTS.md" in claude


def test_init_force_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "b3"
    runner.invoke(app, ["init", str(target)])
    r = runner.invoke(app, ["init", str(target), "--force"])
    assert r.exit_code == 0


# --- structure ---


def test_structure_command() -> None:
    r = runner.invoke(app, ["structure"])
    assert r.exit_code == 0
    assert "AGENTS.md" in r.stdout
    assert "CLAUDE.md" in r.stdout
    assert "index.md" in r.stdout
    assert "raw/" in r.stdout
    assert "lwiki init" in r.stdout
    # Legacy marker should not appear in the new layout.
    assert "wiki/" not in r.stdout


# --- index.md shape ---


def test_init_root_index_has_okf_version(tmp_path: Path) -> None:
    target = tmp_path / "b4"
    runner.invoke(app, ["init", str(target)])
    text = (target / "index.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "okf_version:" in text
    assert "'0.2'" in text or '"0.2"' in text


# --- AGENTS.md ---


def test_init_agents_md_documents_okf_contract(tmp_path: Path) -> None:
    """AGENTS.md must declare the OKF 0.2 frontmatter contract so non-LLM
    consumers see the schema up front."""
    target = tmp_path / "b5"
    runner.invoke(app, ["init", str(target), "-d", "Test"])
    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    # Required tier mentions type
    assert "type" in agents
    # Recommended tier mentions generated
    assert "generated" in agents
    # Optional tier mentions resource
    assert "resource" in agents
    # Wikilink rules are explicitly dropped
    assert "[[" not in agents or "no `[[" in agents or "no [[wikilinks]]" in agents


# --- overview.md ---


def test_init_overview_uses_okf_frontmatter(tmp_path: Path) -> None:
    target = tmp_path / "b6"
    runner.invoke(app, ["init", str(target), "-d", "Greek History"])
    overview = (target / "overview.md").read_text(encoding="utf-8")
    assert overview.startswith("---")
    assert "type: overview" in overview
    assert "description:" in overview
    assert "generated:" in overview
    assert "status:" in overview
    assert "Greek History" in overview
    # The legacy ``updated:`` field must not appear.
    assert "updated:" not in overview


# --- validate ---


def test_validate_passes_on_scaffold(tmp_path: Path) -> None:
    target = tmp_path / "b7"
    runner.invoke(app, ["init", str(target), "-d", "x"])
    r = runner.invoke(app, ["validate", str(target)])
    assert r.exit_code == 0, r.output
    assert "OK" in r.output


def test_validate_fails_on_missing_okf_version(tmp_path: Path) -> None:
    target = tmp_path / "b8"
    target.mkdir()
    (target / "index.md").write_text("# no frontmatter\n", encoding="utf-8")
    r = runner.invoke(app, ["validate", str(target)])
    assert r.exit_code != 0


# --- migrate ---


def test_wikilink_rewrite_cli(tmp_path: Path) -> None:
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n", encoding="utf-8"
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntype: concept\ntitle: X\ndescription: x\n---\n\nSee [[y]].\n",
        encoding="utf-8",
    )
    (bundle / "concepts" / "y.md").write_text(
        "---\ntype: concept\ntitle: Y\ndescription: y\n---\n\n", encoding="utf-8"
    )
    r = runner.invoke(app, ["wikilink-rewrite", str(bundle)])
    assert r.exit_code == 0, r.output
    assert "Rewritten" in r.output or "rewritten" in r.output.lower()
    body = (bundle / "concepts" / "x.md").read_text(encoding="utf-8")
    assert "[y](y.md)" in body


def test_migrate_legacy_wiki(tmp_path: Path) -> None:
    old = tmp_path / "old"
    old.mkdir()
    new = tmp_path / "new"
    # Build a small legacy wiki
    (old / "AGENTS.md").write_text("# x\n", encoding="utf-8")
    (old / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (old / "raw").mkdir()
    (old / "raw" / "files.log").write_text("# empty\n", encoding="utf-8")
    (old / "wiki" / "concepts").mkdir(parents=True)
    (old / "wiki" / "index.md").write_text("# idx\n", encoding="utf-8")
    (old / "wiki" / "log.md").write_text("# log\n", encoding="utf-8")
    (old / "wiki" / "overview.md").write_text(
        "---\ntitle: Overview\ntype: overview\ndescription: x\n"
        "updated: 2026-01-01\n---\n\nBody.\n",
        encoding="utf-8",
    )
    (old / "wiki" / "concepts" / "democracy.md").write_text(
        "---\ntitle: Democracy\ntype: concept\ndescription: x\n"
        "updated: 2026-01-02\n---\n\nBody.\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["migrate", str(old), "--out", str(new)])
    assert r.exit_code == 0, r.output
    assert (new / "concepts" / "democracy.md").is_file()
    assert (new / "index.md").is_file()
    assert "Migrated" in r.output