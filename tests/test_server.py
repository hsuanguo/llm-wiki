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
    _count_pages,
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
    """Build a small OKF bundle and a live HTTP server bound to an ephemeral port."""
    wiki_root = tmp_path / "vault"
    wiki_root.mkdir()
    wiki = wiki_root / "greek-history"
    wiki.mkdir()
    (wiki / "concepts").mkdir()
    (wiki / "entities").mkdir()
    (wiki / "raw").mkdir()
    (wiki / "AGENTS.md").write_text("# Greek History Wiki Schema\n", encoding="utf-8")
    (wiki / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (wiki / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n\n# Bundle Index\n",
        encoding="utf-8",
    )
    (wiki / "log.md").write_text(
        "# Bundle Log\n\n## [2026-01-01] init | greek-history\n",
        encoding="utf-8",
    )
    (wiki / "overview.md").write_text(
        "---\ntitle: Overview\ntype: overview\n"
        "description: Big-picture synthesis.\n"
        "generated: { by: 'lwiki/0.2', at: '2026-01-01' }\n---\n\n"
        "See [democracy](concepts/democracy.md).\n",
        encoding="utf-8",
    )
    (wiki / "concepts" / "democracy.md").write_text(
        "---\ntitle: Democracy\ntype: concept\n"
        "description: Athenian democracy.\ntags: [politics]\n"
        "generated: { by: 'lwiki/0.2', at: '2026-01-02' }\n---\n\n"
        "Refers to [athens](../entities/athens.md).\n",
        encoding="utf-8",
    )
    (wiki / "entities" / "athens.md").write_text(
        "---\ntitle: Athens\ntype: entity\ndescription: City-state.\n"
        "generated: { by: 'lwiki/0.2', at: '2026-01-03' }\n---\n\n"
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
    (wiki_root / "alpha" / "index.md").write_text(
        "---\nokf_version: '0.2'\n---\n", encoding="utf-8"
    )
    (wiki_root / "no-wiki-here").mkdir()
    assert {w["name"] for w in list_wikis(wiki_root)} == {"alpha"}


def test_list_wikis_ignores_non_bundle_dirs(tmp_path: Path) -> None:
    """A folder without an ``okf_version`` index is not a bundle."""
    wiki_root = tmp_path / "v"
    wiki_root.mkdir()
    (wiki_root / "alpha").mkdir()
    (wiki_root / "alpha" / "AGENTS.md").write_text("# a\n")  # no index.md
    assert list_wikis(wiki_root) == []


def test_list_pages_includes_overview_and_concepts(server_setup) -> None:
    _, wiki, _ = server_setup
    pages = list_pages(wiki)
    rels = {p["rel_path"] for p in pages}
    assert "overview.md" in rels
    assert "concepts/democracy.md" in rels
    assert "entities/athens.md" in rels


def test_list_pages_and_counts_ignore_subdir_indexes_and_readmes(server_setup) -> None:
    _, wiki, _ = server_setup
    (wiki / "concepts" / "README.md").write_text("# Concepts Index\n", encoding="utf-8")
    (wiki / "concepts" / "index.md").write_text("# Concepts Index\n", encoding="utf-8")
    (wiki / "summaries").mkdir(exist_ok=True)
    (wiki / "summaries" / "README.md").write_text("# Summaries Index\n", encoding="utf-8")

    pages = list_pages(wiki)
    rels = {p["rel_path"] for p in pages}
    assert "concepts/README.md" not in rels
    assert "concepts/index.md" not in rels
    assert "summaries/README.md" not in rels

    counts = _count_pages(wiki)
    assert counts["concepts"] == 1  # only democracy.md
    assert counts["summaries"] == 0

    (wiki / "concepts" / "democracy.md").write_text(
        "---\ntitle: Democracy\ntype: concept\n"
        "description: Athenian democracy.\ntags: [politics]\n"
        "generated: { by: 'lwiki/0.2', at: '2026-01-02' }\n---\n\n"
        "Refers to [athens](../entities/athens.md), [index](../index.md), [readme](../README.md), "
        "and [local index](index.md), plus [[index]] and [[README]].\n",
        encoding="utf-8",
    )

    graph = build_graph(wiki)
    node_ids = {node["id"] for node in graph["nodes"]}
    assert "concepts/README.md" not in node_ids
    assert "concepts/index.md" not in node_ids
    assert "summaries/README.md" not in node_ids
    assert "README.md" not in node_ids
    assert "index.md" not in node_ids

    # Edges should only connect valid concept pages (democracy -> athens)
    for edge in graph["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids
        assert not edge["target"].endswith("index.md")
        assert not edge["target"].endswith("README.md")


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
            "generated": {"by": "lwiki/0.2", "at": "2026-02-01"},
        },
        body="# Oligarchy\n\nRefers to [athens](../entities/athens.md).\n",
    )
    data = read_page(wiki, new_path)
    assert data["frontmatter"]["title"] == "Oligarchy"
    assert "athens" in data["body"]
    delete_page(wiki, new_path)
    with pytest.raises(FileNotFoundError):
        read_page(wiki, new_path)


def test_write_page_rejects_legacy_updated_field(server_setup) -> None:
    _, wiki, _ = server_setup
    with pytest.raises(ValueError, match="legacy 'updated:' field"):
        write_page(
            wiki,
            "concepts/x.md",
            frontmatter={
                "type": "concept",
                "title": "X",
                "updated": "2026-02-01",  # legacy wiki field
            },
            body="body\n",
        )


def test_write_page_rejects_legacy_cited_field(server_setup) -> None:
    _, wiki, _ = server_setup
    with pytest.raises(ValueError, match="legacy 'cited:' field"):
        write_page(
            wiki,
            "concepts/x.md",
            frontmatter={
                "type": "concept",
                "title": "X",
                "cited": ["foo"],  # legacy wiki field
            },
            body="body\n",
        )


def test_write_page_rejects_legacy_sources_paths(server_setup) -> None:
    _, wiki, _ = server_setup
    with pytest.raises(ValueError, match="legacy 'sources:"):
        write_page(
            wiki,
            "concepts/x.md",
            frontmatter={
                "type": "concept",
                "title": "X",
                "sources": ["raw/foo.md"],  # legacy wiki field
            },
            body="body\n",
        )


def test_write_page_requires_type(server_setup) -> None:
    _, wiki, _ = server_setup
    with pytest.raises(ValueError, match="non-empty 'type'"):
        write_page(
            wiki,
            "concepts/x.md",
            frontmatter={"title": "X"},
            body="body\n",
        )


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

    # Also works without .md extension
    status, payload = _http_get(port, "/api/wikis/greek-history/pages/concepts/democracy")
    assert status == 200
    assert payload["frontmatter"]["title"] == "Democracy"
    assert payload["rel_path"] == "concepts/democracy.md"


def test_read_page_without_md_extension(server_setup) -> None:
    _, wiki, _ = server_setup
    data = read_page(wiki, "concepts/democracy")
    assert data["rel_path"] == "concepts/democracy.md"
    assert data["frontmatter"]["title"] == "Democracy"


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
                "generated": {"by": "lwiki/0.2", "at": "2026-02-02"},
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


def test_http_write_page_rejects_legacy_frontmatter(server_setup) -> None:
    """Server rejects the legacy `updated:` field with a clear error."""
    _, _, port = server_setup
    status, payload = _http_send(
        port,
        "/api/wikis/greek-history/pages/concepts/x.md",
        "PUT",
        {
            "frontmatter": {
                "type": "concept",
                "title": "X",
                "updated": "2026-02-01",
            },
            "body": "body\n",
        },
    )
    assert status == 400
    assert "updated" in payload.get("error", "")


def test_http_validate_endpoint_conformant(server_setup) -> None:
    """`/api/wikis/<name>/validate` returns conformance violations."""
    _, _, port = server_setup
    status, payload = _http_get(port, "/api/wikis/greek-history/validate")
    assert status == 200
    assert payload["conformant"] is True
    assert payload["violations"] == []


def test_http_validate_endpoint_reports_errors(server_setup) -> None:
    """Mutate a page to drop its `type` and confirm /validate flags it."""
    wiki_root, _, port = server_setup
    target = wiki_root / "greek-history" / "concepts" / "democracy.md"
    target.write_text(
        "---\ntitle: Democracy\n"
        "generated: { by: 'lwiki/0.2', at: '2026-01-02' }\n---\n\nbody\n",
        encoding="utf-8",
    )
    status, payload = _http_get(port, "/api/wikis/greek-history/validate")
    assert status == 200
    assert payload["conformant"] is False
    codes = {v["code"] for v in payload["violations"]}
    assert "concept.type_missing" in codes


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
