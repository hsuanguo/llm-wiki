"""Tests for the lwiki web UI server (no external deps)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from lwiki.server import (
    ServerConfig,
    _Handler,
    build_graph,
    delete_page,
    list_pages,
    list_wikis,
    read_page,
    tail_log,
    write_page,
)


@pytest.fixture
def server_setup(tmp_path: Path):
    """Build a small wiki and a live HTTP server bound to an ephemeral port."""
    wiki_root = tmp_path / "vault"
    wiki_root.mkdir()
    wiki = wiki_root / "greek-history"
    (wiki / "wiki" / "concepts").mkdir(parents=True)
    (wiki / "wiki" / "entities").mkdir(parents=True)
    (wiki / "raw").mkdir()
    (wiki / "AGENTS.md").write_text("# Greek History Wiki Schema\n", encoding="utf-8")
    (wiki / "wiki" / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    (wiki / "wiki" / "log.md").write_text(
        "# Wiki Log\n\n## [2026-01-01] init | greek-history\n",
        encoding="utf-8",
    )
    (wiki / "wiki" / "overview.md").write_text(
        "---\ntitle: Overview\ntype: overview\n"
        "description: Big-picture synthesis.\nupdated: 2026-01-01\n---\n\n"
        "See [[democracy]].\n",
        encoding="utf-8",
    )
    (wiki / "wiki" / "concepts" / "democracy.md").write_text(
        "---\ntitle: Democracy\ntype: concept\n"
        "description: Athenian democracy.\ntags: [politics]\nupdated: 2026-01-02\n---\n\n"
        "Refers to [[athens]].\n",
        encoding="utf-8",
    )
    (wiki / "wiki" / "entities" / "athens.md").write_text(
        "---\ntitle: Athens\ntype: entity\ndescription: City-state.\nupdated: 2026-01-03\n---\n\n"
        "Body.\n",
        encoding="utf-8",
    )

    config = ServerConfig(wiki_root=wiki_root, host="127.0.0.1", port=0)
    handler_cls = type("_Bound", (_Handler,), {"config": config})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield wiki_root, wiki, port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def _http_get(port: int, path: str) -> tuple[int, dict]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"raw": body}


def _http_send(port: int, path: str, method: str, body: dict | None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else b""
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data if data else None,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"raw": raw}


# --- model functions ---


def test_list_wikis_returns_enumerated_wikis(tmp_path: Path) -> None:
    wiki_root = tmp_path / "v"
    wiki_root.mkdir()
    (wiki_root / "alpha").mkdir()
    (wiki_root / "alpha" / "AGENTS.md").write_text("# a\n")
    (wiki_root / "no-wiki-here").mkdir()
    assert {w["name"] for w in list_wikis(wiki_root)} == {"alpha"}


def test_list_pages_includes_overview_and_concepts(server_setup) -> None:
    _, wiki, _ = server_setup
    pages = list_pages(wiki)
    rels = {p["rel_path"] for p in pages}
    assert "overview.md" in rels
    assert "concepts/democracy.md" in rels
    assert "entities/athens.md" in rels


def test_read_and_write_page_round_trip(server_setup) -> None:
    _, wiki, _ = server_setup
    new_path = "concepts/oligarchy.md"
    write_page(
        wiki,
        new_path,
        frontmatter={
            "title": "Oligarchy",
            "type": "concept",
            "description": "Rule by few.",
            "tags": ["politics"],
            "updated": "2026-02-01",
        },
        body="# Oligarchy\n\nRefers to [[athens]].\n",
    )
    data = read_page(wiki, new_path)
    assert data["frontmatter"]["title"] == "Oligarchy"
    assert "athens" in data["body"]
    delete_page(wiki, new_path)
    with pytest.raises(FileNotFoundError):
        read_page(wiki, new_path)


def test_build_graph_resolves_wikilinks(server_setup) -> None:
    _, wiki, _ = server_setup
    graph = build_graph(wiki)
    nodes = {n["id"] for n in graph["nodes"]}
    assert "concepts/democracy.md" in nodes
    edges = {(e["source"], e["target"]) for e in graph["edges"]}
    assert ("overview.md", "concepts/democracy.md") in edges
    assert ("concepts/democracy.md", "entities/athens.md") in edges


def test_tail_log_returns_lines(server_setup) -> None:
    _, wiki, _ = server_setup
    text = tail_log(wiki, limit=5)
    assert "init" in text


# --- HTTP layer ---


def test_http_root_serves_spa(server_setup) -> None:
    _, _, port = server_setup
    req = urllib.request.Request(f"http://127.0.0.1:{port}/")
    with urllib.request.urlopen(req, timeout=2) as resp:
        assert resp.status == 200
        body = resp.read().decode("utf-8")
    assert "llm-wiki" in body


def test_http_health(server_setup) -> None:
    _, _, port = server_setup
    status, payload = _http_get(port, "/api/health")
    assert status == 200
    assert payload["status"] == "ok"


def test_http_list_wikis(server_setup) -> None:
    _, _, port = server_setup
    status, payload = _http_get(port, "/api/wikis")
    assert status == 200
    names = {w["name"] for w in payload["wikis"]}
    assert "greek-history" in names


def test_http_wiki_pages_and_detail(server_setup) -> None:
    _, _, port = server_setup
    status, payload = _http_get(port, "/api/wikis/greek-history/pages")
    assert status == 200
    rels = {p["rel_path"] for p in payload["pages"]}
    assert "concepts/democracy.md" in rels

    status, payload = _http_get(port, "/api/wikis/greek-history/pages/concepts/democracy.md")
    assert status == 200
    assert payload["frontmatter"]["title"] == "Democracy"


def test_http_write_and_delete_page(server_setup) -> None:
    _, _, port = server_setup
    rel = "concepts/oligarchy.md"
    status, _ = _http_send(
        port,
        f"/api/wikis/greek-history/pages/{rel}",
        "PUT",
        {
            "frontmatter": {
                "title": "Oligarchy",
                "type": "concept",
                "description": "Rule by few.",
                "tags": ["politics"],
                "updated": "2026-02-02",
            },
            "body": "# Oligarchy\n",
        },
    )
    assert status == 200

    status, payload = _http_get(port, "/api/wikis/greek-history/pages/concepts/oligarchy.md")
    assert status == 200
    assert payload["frontmatter"]["title"] == "Oligarchy"

    status, _ = _http_send(port, f"/api/wikis/greek-history/pages/{rel}", "DELETE", None)
    assert status == 200


def test_http_init_wiki(tmp_path: Path) -> None:
    """POST /api/wikis creates a new wiki folder."""
    wiki_root = tmp_path / "vault2"
    config = ServerConfig(wiki_root=wiki_root, host="127.0.0.1", port=0)
    handler_cls = type("_B", (_Handler,), {"config": config})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        status, payload = _http_send(
            port,
            "/api/wikis",
            "POST",
            {"name": "fresh", "domain": "Fresh wiki", "sources": "articles"},
        )
        assert status == 201
        assert payload["name"] == "fresh"
        assert (wiki_root / "fresh" / "AGENTS.md").is_file()
        assert (wiki_root / "fresh" / "raw" / "files.log").is_file()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_http_path_traversal_blocked(server_setup) -> None:
    _, _, port = server_setup
    status, payload = _http_get(port, "/api/wikis/..%2Fetc/pages")
    assert status in (400, 404)
    assert "error" in payload


def test_http_static_serves_css(server_setup) -> None:
    _, _, port = server_setup
    req = urllib.request.Request(f"http://127.0.0.1:{port}/static/app.css")
    with urllib.request.urlopen(req, timeout=2) as resp:
        assert resp.status == 200
        body = resp.read().decode("utf-8")
    assert "llm-wiki" in body or "background" in body
