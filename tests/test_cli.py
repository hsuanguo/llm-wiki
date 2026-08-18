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
    assert "index.md" in r.stdout
    assert "raw/" in r.stdout
    assert "lwiki init" in r.stdout
    # Legacy marker should not appear in the new layout.
    assert "CLAUDE.md" not in r.stdout
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