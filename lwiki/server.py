"""HTTP server for the llm-wiki web UI.

Zero-deps: uses only the Python standard library (``http.server`` +
``json`` + ``urllib``). The server is read/write on the wiki directories
under its configured root — it creates pages, updates them, deletes them,
and serves a knowledge-graph view sourced from frontmatter + ``[[wikilinks]]``.

Endpoints (all under ``/api/``):
    GET    /api/wikis                     list wikis under the wiki root
    POST   /api/wikis                     init a new wiki (body: domain, sources?)
    GET    /api/wikis/<name>              wiki meta (counts, description)
    GET    /api/wikis/<name>/pages        list all concept pages
    GET    /api/wikis/<name>/pages/<rel>  get one page (frontmatter + body)
    PUT    /api/wikis/<name>/pages/<rel>  create or overwrite page
    DELETE /api/wikis/<name>/pages/<rel>  delete page
    GET    /api/wikis/<name>/graph        nodes + edges for the graph view
    GET    /api/wikis/<name>/log          tail of wiki/log.md

The HTML SPA is served from ``/`` (resolved relative to this module).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .okf_export import parse_frontmatter
from .raw_tracker import run_raw_status, run_raw_sync

WIKI_SUBDIRS: tuple[str, ...] = ("summaries", "concepts", "entities", "insights")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")


@dataclass
class ServerConfig:
    """Resolved server configuration."""

    wiki_root: Path
    host: str = "127.0.0.1"
    port: int = 8765
    static_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.static_dir = Path(__file__).resolve().parent / "static"


# ---------------------------------------------------------------------------
# Wiki model helpers — read-side only, independent of HTTP.


def _safe_wiki_name(name: str) -> str:
    """Reject path traversal in wiki names."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise ValueError(f"invalid wiki name: {name!r}")
    return name


def _wiki_path(wiki_root: Path, name: str) -> Path:
    return wiki_root / _safe_wiki_name(name)


def _resolve_wiki(wiki_root: Path, name: str) -> Path:
    path = _wiki_path(wiki_root, name).resolve()
    root = wiki_root.resolve()
    if root not in path.parents and path != root:
        raise ValueError(f"wiki path escapes root: {path}")
    return path


def _is_wiki(path: Path) -> bool:
    return (path / "AGENTS.md").is_file() or (
        (path / "wiki" / "index.md").is_file() and (path / "wiki" / "log.md").is_file()
    )


def list_wikis(wiki_root: Path) -> list[dict[str, Any]]:
    """Enumerate wikis directly under ``wiki_root``."""
    if not wiki_root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for child in sorted(wiki_root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if _is_wiki(child):
            out.append(
                {
                    "name": child.name,
                    "description": _read_description(child),
                    "counts": _count_pages(child),
                }
            )
    return out


def _read_description(wiki_dir: Path) -> str:
    overview = wiki_dir / "wiki" / "overview.md"
    if not overview.is_file():
        return ""
    try:
        fm, _ = parse_frontmatter(overview.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(fm.get("description", ""))


def _count_pages(wiki_dir: Path) -> dict[str, int]:
    counts = {sub: 0 for sub in WIKI_SUBDIRS}
    counts["overview"] = 1 if (wiki_dir / "wiki" / "overview.md").is_file() else 0
    for sub in WIKI_SUBDIRS:
        sub_dir = wiki_dir / "wiki" / sub
        if not sub_dir.is_dir():
            continue
        counts[sub] = sum(1 for _ in sub_dir.glob("*.md"))
    counts["total"] = sum(counts.values())
    return counts


def list_pages(wiki_dir: Path) -> list[dict[str, Any]]:
    """List concept pages in a wiki (overview + each subdir)."""
    pages: list[dict[str, Any]] = []
    overview = wiki_dir / "wiki" / "overview.md"
    if overview.is_file():
        pages.append(_page_meta(overview, "overview", wiki_dir))
    for sub in WIKI_SUBDIRS:
        sub_dir = wiki_dir / "wiki" / sub
        if not sub_dir.is_dir():
            continue
        for md in sorted(sub_dir.glob("*.md")):
            pages.append(_page_meta(md, sub, wiki_dir))
    return pages


def _page_meta(path: Path, category: str, wiki_dir: Path) -> dict[str, Any]:
    # rel_path is always relative to ``<wiki>/wiki/`` so the API and the
    # server both see the same shape for overview vs category pages.
    rel = path.resolve().relative_to((wiki_dir / "wiki").resolve()).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    fm, _ = parse_frontmatter(text)
    return {
        "rel_path": rel,
        "category": category,
        "title": str(fm.get("title", path.stem)),
        "type": str(fm.get("type", category.rstrip("s"))),
        "description": str(fm.get("description", "")),
        "updated": str(fm.get("updated", "")),
        "tags": [str(t) for t in (fm.get("tags") or [])]
        if isinstance(fm.get("tags"), list)
        else [],
    }


def _resolve_page_path(wiki_dir: Path, rel: str) -> Path:
    """Resolve a wiki-relative page path against ``wiki_dir/wiki/``."""
    wiki_root = (wiki_dir / "wiki").resolve()
    candidate = (wiki_dir / "wiki" / rel).resolve()
    if wiki_root != candidate and wiki_root not in candidate.parents:
        raise ValueError(f"page path escapes wiki/: {rel}")
    return candidate


def read_page(wiki_dir: Path, rel: str) -> dict[str, Any]:
    """Read a single page by bundle-relative path (e.g. ``concepts/rag.md``)."""
    rel = rel.lstrip("/")
    if rel in {"", "index.md", "log.md"}:
        raise ValueError(f"reserved filename: {rel}")
    page_path = _resolve_page_path(wiki_dir, rel)
    if not page_path.is_file():
        raise FileNotFoundError(f"page not found: {rel}")
    text = page_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    return {
        "rel_path": rel,
        "frontmatter": {k: v for k, v in fm.items()},
        "body": body,
    }


def write_page(wiki_dir: Path, rel: str, *, frontmatter: dict, body: str) -> dict[str, Any]:
    """Create or overwrite a page. Frontmatter is rendered as YAML."""
    rel = rel.lstrip("/")
    if rel in {"", "index.md", "log.md"}:
        raise ValueError(f"reserved filename: {rel}")
    page_path = _resolve_page_path(wiki_dir, rel)
    page_path.parent.mkdir(parents=True, exist_ok=True)
    from .okf_export import emit_frontmatter  # local import — avoid heavy top-level

    rendered = emit_frontmatter(frontmatter) + body.lstrip("\n")
    page_path.write_text(rendered, encoding="utf-8")
    return {"rel_path": rel, "size": page_path.stat().st_size}


def delete_page(wiki_dir: Path, rel: str) -> None:
    rel = rel.lstrip("/")
    if rel in {"", "index.md", "log.md"}:
        raise ValueError(f"reserved filename: {rel}")
    page_path = _resolve_page_path(wiki_dir, rel)
    if page_path.is_file():
        page_path.unlink()


def build_graph(wiki_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Collect nodes (pages) and edges (resolved wikilinks) for the graph view."""
    pages = list_pages(wiki_dir)
    slug_map: dict[str, list[str]] = {}
    for p in pages:
        rel = p["rel_path"]
        slug_map.setdefault(Path(rel).stem, []).append(rel)

    nodes = []
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()
    for p in pages:
        nodes.append(
            {
                "id": p["rel_path"],
                "title": p["title"],
                "type": p["type"],
                "category": p["category"],
            }
        )
        page_path = wiki_dir / "wiki" / p["rel_path"]
        try:
            text = page_path.read_text(encoding="utf-8")
        except OSError:
            continue
        _, body = parse_frontmatter(text)
        source_dir = p["rel_path"].split("/", 1)[0]
        for match in WIKILINK_RE.finditer(body):
            slug = match.group(1).strip()
            candidates = slug_map.get(slug, [])
            same_dir = [c for c in candidates if c.split("/", 1)[0] == source_dir]
            target = (same_dir or candidates)[:1]
            if not target:
                continue
            key = (p["rel_path"], target[0])
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({"source": p["rel_path"], "target": target[0]})
    return {"nodes": nodes, "edges": edges}


def tail_log(wiki_dir: Path, limit: int = 20) -> str:
    log = wiki_dir / "wiki" / "log.md"
    if not log.is_file():
        return ""
    text = log.read_text(encoding="utf-8")
    lines = text.splitlines()
    return "\n".join(lines[-limit:])


# ---------------------------------------------------------------------------
# HTTP layer.


def _json(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False, default=_json_default).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _json_default(value: Any) -> Any:
    """Coerce YAML-loaded scalars to JSON-safe values.

    YAML parsers return ``date`` / ``datetime`` for unquoted ISO dates; the
    HTTP API must serialise those as ISO strings.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON body: {exc}") from exc


class _Handler(BaseHTTPRequestHandler):
    config: ServerConfig  # set per server

    # Silence default per-request stderr access logs; emit one summary line on start/stop.
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib name
        return

    # --- routing ---

    def do_GET(self) -> None:  # noqa: N802 - stdlib name
        path = urlparse(self.path).path
        try:
            if path == "/" or path == "/index.html":
                self._serve_static("index.html")
            elif path.startswith("/static/"):
                self._serve_static(path[len("/static/") :])
            elif path == "/api/wikis":
                _json(self, 200, {"wikis": list_wikis(self.config.wiki_root)})
            elif path == "/api/health":
                _json(self, 200, {"status": "ok", "wiki_root": str(self.config.wiki_root)})
            else:
                self._route_wiki_get(path)
        except FileNotFoundError as exc:
            _json(self, 404, {"error": str(exc)})
        except ValueError as exc:
            _json(self, 400, {"error": str(exc)})
        except Exception as exc:  # last-resort guard so the server keeps running
            _json(self, 500, {"error": f"server error: {exc}"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/wikis":
                self._init_wiki()
            elif path.startswith("/api/wikis/") and path.endswith("/raw/sync"):
                self._raw_sync(path)
            else:
                _json(self, 404, {"error": "not found"})
        except FileExistsError as exc:
            _json(self, 409, {"error": str(exc)})
        except ValueError as exc:
            _json(self, 400, {"error": str(exc)})
        except Exception as exc:
            _json(self, 500, {"error": f"server error: {exc}"})

    def do_PUT(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            self._write_page(path)
        except (FileNotFoundError, ValueError) as exc:
            _json(self, 400, {"error": str(exc)})
        except Exception as exc:
            _json(self, 500, {"error": f"server error: {exc}"})

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            self._delete_page(path)
        except (FileNotFoundError, ValueError) as exc:
            _json(self, 400, {"error": str(exc)})
        except Exception as exc:
            _json(self, 500, {"error": f"server error: {exc}"})

    # --- route handlers ---

    def _route_wiki_get(self, path: str) -> None:
        rest = path[len("/api/wikis/") :]
        parts = rest.split("/", 1)
        if not parts or not parts[0]:
            _json(self, 404, {"error": "wiki name required"})
            return
        wiki = _resolve_wiki(self.config.wiki_root, parts[0])
        if not _is_wiki(wiki):
            _json(self, 404, {"error": f"no wiki at {wiki.name}"})
            return

        if len(parts) == 1:
            _json(
                self,
                200,
                {
                    "name": wiki.name,
                    "description": _read_description(wiki),
                    "counts": _count_pages(wiki),
                },
            )
            return

        sub = parts[1]
        if sub == "pages":
            _json(self, 200, {"pages": list_pages(wiki)})
        elif sub == "graph":
            _json(self, 200, build_graph(wiki))
        elif sub == "log":
            _json(self, 200, {"log": tail_log(wiki)})
        elif sub.startswith("pages/"):
            rel = unquote(sub[len("pages/") :])
            _json(self, 200, read_page(wiki, rel))
        elif sub == "raw":
            code, msg = run_raw_status(wiki / "raw")
            _json(self, 200, {"exit_code": code, "report": msg})
        else:
            _json(self, 404, {"error": f"unknown endpoint: {sub}"})

    def _write_page(self, path: str) -> None:
        rest = path[len("/api/wikis/") :]
        parts = rest.split("/", 2)
        if len(parts) < 3 or parts[1] != "pages":
            _json(self, 404, {"error": "PUT requires /api/wikis/<name>/pages/<rel>"})
            return
        wiki = _resolve_wiki(self.config.wiki_root, parts[0])
        if not _is_wiki(wiki):
            _json(self, 404, {"error": f"no wiki at {wiki.name}"})
            return
        body = _read_json(self)
        rel = unquote(parts[2])
        frontmatter = body.get("frontmatter") or {}
        page_body = body.get("body") or ""
        result = write_page(wiki, rel, frontmatter=frontmatter, body=page_body)
        _json(self, 200, result)

    def _delete_page(self, path: str) -> None:
        rest = path[len("/api/wikis/") :]
        parts = rest.split("/", 2)
        if len(parts) < 3 or parts[1] != "pages":
            _json(self, 404, {"error": "DELETE requires /api/wikis/<name>/pages/<rel>"})
            return
        wiki = _resolve_wiki(self.config.wiki_root, parts[0])
        if not _is_wiki(wiki):
            _json(self, 404, {"error": f"no wiki at {wiki.name}"})
            return
        rel = unquote(parts[2])
        delete_page(wiki, rel)
        _json(self, 200, {"deleted": rel})

    def _init_wiki(self) -> None:
        body = _read_json(self)
        name = str(body.get("name", "")).strip()
        if not name:
            raise ValueError("'name' is required")
        domain = str(body.get("domain", "My Wiki")).strip() or "My Wiki"
        sources = str(body.get("sources", "articles, URLs, papers")).strip() or (
            "articles, URLs, papers"
        )
        from .init_scaffold import init_wiki_tree

        root = _wiki_path(self.config.wiki_root, name)
        try:
            init_wiki_tree(root, domain=domain, source_types=sources, force=False)
        except FileExistsError:
            raise
        code, msg = run_raw_sync(root / "raw")
        _json(self, 201, {"name": name, "domain": domain, "raw_sync": msg})

    def _raw_sync(self, path: str) -> None:
        rest = path[len("/api/wikis/") :]
        parts = rest.split("/")
        wiki = _resolve_wiki(self.config.wiki_root, parts[0])
        if not _is_wiki(wiki):
            _json(self, 404, {"error": f"no wiki at {wiki.name}"})
            return
        code, msg = run_raw_sync(wiki / "raw")
        _json(self, 200, {"exit_code": code, "report": msg})

    def _serve_static(self, rel: str) -> None:
        # Reject path traversal in static filenames.
        if "/" in rel or "\\" in rel or rel.startswith("."):
            _json(self, 400, {"error": "invalid static path"})
            return
        target = (self.config.static_dir / rel).resolve()
        if (
            self.config.static_dir.resolve() not in target.parents
            and target != self.config.static_dir.resolve()
        ):
            _json(self, 400, {"error": "static path escapes static dir"})
            return
        if not target.is_file():
            _json(self, 404, {"error": f"static file not found: {rel}"})
            return
        ctype = {
            "html": "text/html; charset=utf-8",
            "css": "text/css; charset=utf-8",
            "js": "application/javascript; charset=utf-8",
            "svg": "image/svg+xml",
            "png": "image/png",
            "ico": "image/x-icon",
        }.get(target.suffix.lstrip(".").lower(), "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def run_server(wiki_root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Start the HTTP server. Blocks until interrupted."""
    config = ServerConfig(wiki_root=wiki_root.resolve(), host=host, port=port)
    config.wiki_root.mkdir(parents=True, exist_ok=True)
    handler_cls = type("_BoundHandler", (_Handler,), {"config": config})
    httpd = ThreadingHTTPServer((config.host, config.port), handler_cls)
    print(f"llm-wiki server listening on http://{config.host}:{config.port}")
    print(f"  wiki root: {config.wiki_root}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        httpd.server_close()


def serve_args() -> dict[str, Any]:  # pragma: no cover - thin shim
    return asdict(ServerConfig(wiki_root=Path(".")))  # type: ignore[call-arg]
