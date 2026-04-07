"""CLI smoke tests via Typer runner."""

from pathlib import Path

from typer.testing import CliRunner

from lwiki.cli import app

runner = CliRunner()


def test_help() -> None:
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    assert "lwiki" in r.stdout.lower() or "LLM Wiki" in r.stdout


def test_raw_status_help() -> None:
    r = runner.invoke(app, ["raw", "status", "--help"])
    assert r.exit_code == 0


def test_init_creates_wiki(tmp_path: Path) -> None:
    target = tmp_path / "mywiki"
    r = runner.invoke(
        app,
        ["init", str(target), "--domain", "Test", "--sources", "urls"],
    )
    assert r.exit_code == 0, r.output
    assert (target / "wiki" / "index.md").is_file()
    assert (target / "raw" / "files.log").is_file()


def test_init_refuses_double_init(tmp_path: Path) -> None:
    target = tmp_path / "w"
    runner.invoke(app, ["init", str(target)])
    r = runner.invoke(app, ["init", str(target)])
    assert r.exit_code == 1


def test_init_default_sources_in_agents(tmp_path: Path) -> None:
    target = tmp_path / "wiki2"
    r = runner.invoke(app, ["init", str(target), "-d", "Only Domain"])
    assert r.exit_code == 0, r.output
    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "Only Domain" in agents
    assert "articles, URLs, papers" in agents
    assert "## Source Types" in agents
    stub = (target / "CLAUDE.md").read_text(encoding="utf-8")
    assert "@AGENTS.md" in stub


def test_structure_command() -> None:
    r = runner.invoke(app, ["structure"])
    assert r.exit_code == 0
    assert "AGENTS.md" in r.stdout
    assert "CLAUDE.md" in r.stdout
    assert "wiki/" in r.stdout
    assert "lwiki init" in r.stdout


def test_init_creates_all_subdirectories(tmp_path: Path) -> None:
    """lwiki init must create assets/, raw/, and all wiki/ subdirectories."""
    target = tmp_path / "fullwiki"
    r = runner.invoke(app, ["init", str(target), "-d", "Test"])
    assert r.exit_code == 0, r.output
    assert (target / "assets").is_dir()
    assert (target / "raw").is_dir()
    for sub in ("summaries", "concepts", "entities", "insights"):
        assert (target / "wiki" / sub).is_dir(), f"wiki/{sub}/ not created"


def test_init_index_no_empty_table_rows(tmp_path: Path) -> None:
    """index.md tables should have header + separator only, no empty data rows."""
    target = tmp_path / "indexwiki"
    r = runner.invoke(app, ["init", str(target), "-d", "Test"])
    assert r.exit_code == 0, r.output
    index_content = (target / "wiki" / "index.md").read_text(encoding="utf-8")
    # No lines that are just empty table cells like "| | | |"
    for line in index_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            # Table lines should be header, separator, or have actual content
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # Allow header row and separator row, reject all-empty data rows
            if all(c == "" for c in cells):
                raise AssertionError(f"Empty table row found in index.md: {line!r}")

