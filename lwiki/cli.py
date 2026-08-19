"""Typer CLI for lwiki."""

from __future__ import annotations

from pathlib import Path

import typer

from lwiki import __version__
from lwiki.init_scaffold import DEFAULT_SOURCE_TYPES, init_wiki_tree
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


@app.command("migrate")
def migrate_cmd(
    old_wiki: Path = typer.Argument(
        ...,
        help="Legacy Obsidian-shaped wiki root (contains AGENTS.md + wiki/)",
        exists=False,
    ),
    out: Path = typer.Option(
        ...,
        "--out",
        "-o",
        help="Output bundle directory (created if missing)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite an existing non-empty output directory",
    ),
) -> None:
    """Convert a legacy Obsidian-shaped wiki into an OKF 0.2 bundle.

    The source wiki is read-only. ``out`` becomes the OKF bundle — concepts
    lifted to the bundle root, frontmatter migrated to OKF 0.2, any
    leftover ``[[wikilinks]]`` rewritten to standard markdown links.
    """
    from .migrate import convert

    try:
        result = convert(old_wiki.resolve(), out.resolve(), force=force)
    except (FileNotFoundError, FileExistsError) as e:
        typer.secho(str(e), err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from e

    typer.secho(
        f"Migrated {result.pages_migrated} page(s) from {result.old_wiki.name} "
        f"to {result.new_bundle} "
        f"({result.files_copied} files, {result.links_rewritten} link(s) rewritten).",
        fg=typer.colors.GREEN,
    )
    for w in result.warnings:
        typer.secho(f"  warning: {w}", fg=typer.colors.YELLOW)


@app.command("validate")
def validate_cmd(
    bundle: Path = typer.Argument(
        Path("."),
        help="OKF bundle root (must contain index.md declaring okf_version)",
        exists=False,
    ),
) -> None:
    """Check OKF 0.2 conformance. Exit 0 if conformant, non-zero otherwise."""
    from .conformance import is_conformant, validate_bundle

    violations = validate_bundle(bundle.resolve())
    for v in violations:
        prefix = f"[{v.level.value.upper()}]"
        where = f" {v.path}" if v.path else ""
        typer.echo(f"{prefix} {v.code}{where} - {v.message}")
    if not is_conformant(violations):
        raise typer.Exit(1)
    typer.echo(f"OK: {bundle} conforms to OKF 0.2.")


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


@app.command("serve")
def serve_cmd(
    root: Path = typer.Option(
        Path("."),
        "--root",
        "-r",
        help="Directory containing wiki folders (each with AGENTS.md).",
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host for the HTTP server."),
    port: int = typer.Option(8765, "--port", "-p", help="Bind port for the HTTP server."),
) -> None:
    """Start the llm-wiki web UI (server-rendered SPA, no extra deps)."""
    from .server import run_server  # local import — keeps CLI startup fast

    try:
        run_server(root.resolve(), host=host, port=port)
    except OSError as e:
        typer.secho(f"failed to bind {host}:{port}: {e}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from e


def run() -> None:
    app()


@export_app.command("okf")
def export_okf_cmd(
    bundle: Path = typer.Argument(
        Path("."),
        help="OKF bundle root (must contain index.md declaring okf_version)",
        exists=False,
    ),
) -> None:
    """Verify OKF 0.2 conformance of the bundle (no transformation).

    This command used to project an Obsidian-shaped wiki into an OKF bundle.
    llm-wiki is now 100% OKF-native — the bundle IS the wiki — so the
    command's new role is to **validate** conformance against the OKF 0.2
    spec. Use ``lwiki migrate`` to convert a legacy Obsidian-shaped wiki.
    """
    from .conformance import is_conformant, validate_bundle

    violations = validate_bundle(bundle.resolve())
    for v in violations:
        prefix = f"[{v.level.value.upper()}]"
        where = f" {v.path}" if v.path else ""
        typer.echo(f"{prefix} {v.code}{where} - {v.message}")
    if not is_conformant(violations):
        raise typer.Exit(1)
    typer.echo(f"OK: {bundle} conforms to OKF 0.2.")


if __name__ == "__main__":
    main()
