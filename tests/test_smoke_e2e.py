"""End-to-end smoke: init → write → validate → migrate → serve → drop.

Single test that exercises every public surface in <5s. Acts as the
regression net for the whole OKF-native flow.
"""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path

from lwiki.cli import app
from lwiki.conformance import is_conformant, validate_bundle
from lwiki.migrate import convert
from lwiki.server import ServerConfig, _Handler
from typer.testing import CliRunner


runner = CliRunner()


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


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


def test_smoke_full_flow(tmp_path: Path) -> None:
    """Full OKF-native flow in one go. Runs in well under 5 seconds."""
    bundle_root = tmp_path / "wikis"
    bundle = bundle_root / "demo"
    legacy = tmp_path / "legacy-wiki"
    legacy.mkdir()

    # 1. INIT — scaffold a fresh OKF bundle
    r = runner.invoke(app, ["init", str(bundle), "-d", "Smoke test domain"])
    assert r.exit_code == 0, r.output
    for top in ("index.md", "log.md", "overview.md", "AGENTS.md", "CLAUDE.md", "README.md"):
        assert (bundle / top).is_file(), top
    for sub in ("summaries", "concepts", "entities", "insights", "raw"):
        assert (bundle / sub).is_dir(), sub

    # 2. CONFORMANCE — scaffolded bundle passes OKF 0.2
    violations = validate_bundle(bundle)
    assert is_conformant(violations), violations

    # 3. WRITE — server PUT writes a concept with OKF frontmatter
    port = _free_port()
    config = ServerConfig(wiki_root=bundle_root, host="127.0.0.1", port=port)
    handler_cls = type("_B", (_Handler,), {"config": config})
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        time.sleep(0.05)  # let the server bind
        status, payload = _http_send(
            port,
            "/api/wikis/demo/pages/concepts/democracy.md",
            "PUT",
            {
                "frontmatter": {
                    "title": "Democracy",
                    "type": "concept",
                    "description": "Athenian democracy.",
                    "tags": ["politics"],
                    "generated": {"by": "lwiki/0.2", "at": "2026-08-19"},
                },
                "body": "# Democracy\n\nSee [athens](../entities/athens.md).\n",
            },
        )
        assert status == 200, payload
        assert (bundle / "concepts" / "democracy.md").is_file()

        # 3a. READ — server GET reads the page back
        status, payload = _http_get(
            port, "/api/wikis/demo/pages/concepts/democracy.md"
        )
        assert status == 200
        assert payload["frontmatter"]["title"] == "Democracy"
        assert payload["body"].startswith("# Democracy")

        # 3b. VALIDATE endpoint — bundle remains conformant
        status, payload = _http_get(port, "/api/wikis/demo/validate")
        assert status == 200
        assert payload["conformant"] is True

        # 3c. Legacy frontmatter rejected
        status, payload = _http_send(
            port,
            "/api/wikis/demo/pages/concepts/bad.md",
            "PUT",
            {
                "frontmatter": {
                    "type": "concept",
                    "title": "Bad",
                    "updated": "2026-08-01",  # legacy field
                },
                "body": "x\n",
            },
        )
        assert status == 400
        assert "updated" in payload["error"]

        # 3d. GRAPH endpoint — markdown link is resolved into an edge
        # First add a target the link can resolve to.
        _http_send(
            port,
            "/api/wikis/demo/pages/entities/athens.md",
            "PUT",
            {
                "frontmatter": {
                    "type": "entity",
                    "title": "Athens",
                    "description": "City-state.",
                    "generated": {"by": "lwiki/0.2", "at": "2026-08-19"},
                },
                "body": "Body.\n",
            },
        )
        status, payload = _http_get(port, "/api/wikis/demo/graph")
        assert status == 200
        targets = {e["target"] for e in payload["edges"]}
        assert "entities/athens.md" in targets
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

    # 4. MIGRATE — convert a legacy wiki to the OKF bundle shape
    (legacy / "AGENTS.md").write_text("# x\n", encoding="utf-8")
    (legacy / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (legacy / "raw").mkdir()
    (legacy / "raw" / "files.log").write_text("# empty\n", encoding="utf-8")
    (legacy / "wiki" / "concepts").mkdir(parents=True)
    (legacy / "wiki" / "index.md").write_text("# idx\n", encoding="utf-8")
    (legacy / "wiki" / "log.md").write_text("# log\n", encoding="utf-8")
    (legacy / "wiki" / "overview.md").write_text(
        "---\ntitle: Overview\ntype: overview\ndescription: x\n"
        "updated: 2026-07-01\n---\n\nBody.\n",
        encoding="utf-8",
    )
    (legacy / "wiki" / "concepts" / "x.md").write_text(
        "---\ntitle: X\ntype: concept\ndescription: x\n"
        "updated: 2026-07-02\nsources: [raw/foo.md]\n---\n\nSee [[y]].\n",
        encoding="utf-8",
    )
    (legacy / "wiki" / "concepts" / "y.md").write_text(
        "---\ntitle: Y\ntype: concept\ndescription: y\nupdated: 2026-07-03\n---\n\n",
        encoding="utf-8",
    )
    new_bundle = tmp_path / "migrated"
    result = convert(legacy, new_bundle)
    assert result.pages_migrated >= 2
    assert (new_bundle / "concepts" / "x.md").is_file()
    assert is_conformant(validate_bundle(new_bundle)), validate_bundle(new_bundle)

    # 5. VALIDATE — CLI runs against both bundles
    r = runner.invoke(app, ["validate", str(bundle)])
    assert r.exit_code == 0, r.output
    assert "OK" in r.output
    r = runner.invoke(app, ["validate", str(new_bundle)])
    assert r.exit_code == 0, r.output