"""Typer CLI for lwiki."""

from __future__ import annotations

from pathlib import Path

import typer

from lwiki import __version__
from lwiki.init_scaffold import DEFAULT_SOURCE_TYPES, init_wiki_tree
from lwiki.okf_export import export_okf
from lwiki.raw_tracker import run_raw_status, run_raw_sync
from lwiki.structure import render_structure_text

app = typer.Typer(
    name="lwiki",
    help="LLM Wiki: init wiki trees and track raw/ against files.log",
    no_args_is_help=True,
)
raw_app = typer.Typer(help="Compare or sync raw/ with files.log")
app.add_typer(raw_app, name="raw")
export_app = typer.Typer(help="Export a wiki to external formats")
app.add_typer(export_app, name="export")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit(0)


@app.callback()
def main(
    version: bool | None = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True
    ),
) -> None:
    """lwiki — LLM Wiki CLI"""


@app.command("structure")
def structure_cmd() -> None:
    """Print the canonical wiki directory layout (what `lwiki init` creates)."""
    typer.echo(render_structure_text().rstrip())


@raw_app.command("status")
def raw_status(
    raw: Path = typer.Argument(
        Path("raw"),
        help="Path to raw/ directory (often relative to wiki root)",
        exists=False,
    ),
) -> None:
    """Report new/modified/deleted files vs files.log (no write). Exit 1 if drift."""
    raw = raw.resolve()
    code, msg = run_raw_status(raw)
    typer.echo(msg)
    raise typer.Exit(code)


@raw_app.command("sync")
def raw_sync(
    raw: Path = typer.Argument(
        Path("raw"),
        help="Path to raw/ directory",
        exists=False,
    ),
) -> None:
    """Rewrite files.log to match raw/."""
    raw = raw.resolve()
    code, msg = run_raw_sync(raw)
    typer.echo(msg)
    raise typer.Exit(code)


@app.command("checkout")
def checkout_alias(
    raw: Path = typer.Argument(
        Path("raw"),
        help="Path to raw/ directory",
        exists=False,
    ),
) -> None:
    """Alias for `lwiki raw sync` (updates files.log)."""
    raw = raw.resolve()
    code, msg = run_raw_sync(raw)
    typer.echo(msg)
    raise typer.Exit(code)


@app.command("init")
def init_cmd(
    path: Path = typer.Argument(
        Path("."),
        help="Wiki root directory to create",
        exists=False,
    ),
    domain: str = typer.Option(
        "My Wiki",
        "--domain",
        "-d",
        help="One-line domain / purpose for AGENTS.md and overview",
    ),
    source_types: str = typer.Option(
        DEFAULT_SOURCE_TYPES,
        "--sources",
        "-s",
        help=f'Source types line for AGENTS.md (optional; default: "{DEFAULT_SOURCE_TYPES}")',
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite if wiki markers already exist (dangerous)",
    ),
) -> None:
    """Create a new wiki directory structure (INIT)."""
    root = path.resolve()
    try:
        init_wiki_tree(root, domain=domain, source_types=source_types, force=force)
    except FileExistsError as e:
        typer.secho(str(e), err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from e

    raw_dir = root / "raw"
    code, msg = run_raw_sync(raw_dir)
    typer.secho(f"Initialized wiki at {root}", fg=typer.colors.GREEN)
    typer.echo(msg)
    raise typer.Exit(code)


def main() -> None:
    app()


@export_app.command("okf")
def export_okf_cmd(
    wiki: Path = typer.Argument(
        Path("."),
        help="Wiki root directory (must contain AGENTS.md or wiki/{index,log}.md)",
        exists=False,
    ),
    out: Path = typer.Option(
        ...,
        "--out",
        "-o",
        help="Output bundle directory (created if missing; must be empty unless --force)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite an existing non-empty output directory",
    ),
) -> None:
    """Export the wiki as an OKF (Open Knowledge Format) bundle.

    OKF v0.1 spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

    The wiki is read-only; the bundle is written to ``out``. Cross-links are
    rewritten from Obsidian ``[[slug]]`` to bundle-relative ``/path/to/x.md``,
    and each directory gets an OKF-style ``index.md`` listing. Exits non-zero
    if the wiki is missing, the output is non-empty without ``--force``, or
    any concept file has unparseable frontmatter.
    """
    try:
        result = export_okf(wiki.resolve(), out.resolve(), force=force)
    except (FileNotFoundError, FileExistsError) as e:
        typer.secho(str(e), err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from e

    typer.secho(
        f"Exported {result.concept_count} concept(s) to {result.bundle_dir} "
        f"({result.rewritten_links} link(s) rewritten).",
        fg=typer.colors.GREEN,
    )
    for w in result.ambiguous_warnings:
        typer.secho(f"  ambiguous: {w}", fg=typer.colors.YELLOW)
    for w in result.unresolved_warnings:
        typer.secho(f"  unresolved: {w}", fg=typer.colors.YELLOW)


if __name__ == "__main__":
    main()
