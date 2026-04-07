"""Tests for raw_tracker."""

from pathlib import Path

import pytest

from lwiki.raw_tracker import (
    compute_drift,
    format_drift_report,
    read_log,
    run_raw_status,
    run_raw_sync,
    scan_directory,
    write_log,
)


def test_scan_empty(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    assert scan_directory(raw) == {}


def test_drift_new_file(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.md").write_text("hello", encoding="utf-8")
    d = compute_drift(raw)
    assert d.has_drift
    assert "a.md" in d.new_files


def test_sync_writes_log(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "x.md").write_text("x", encoding="utf-8")
    code, msg = run_raw_sync(raw)
    assert code == 0
    assert "files.log updated" in msg
    logged = read_log(raw / "files.log")
    assert "x.md" in logged


def test_status_clean_after_sync(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "x.md").write_text("x", encoding="utf-8")
    run_raw_sync(raw)
    code, msg = run_raw_status(raw)
    assert code == 0
    assert "No changes" in msg


def test_status_modified(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "x.md").write_text("x", encoding="utf-8")
    run_raw_sync(raw)
    (raw / "x.md").write_text("y", encoding="utf-8")
    code, msg = run_raw_status(raw)
    assert code == 1
    assert "Modified" in msg or "~" in msg


def test_invalid_raw_dir(tmp_path: Path) -> None:
    code, msg = run_raw_status(tmp_path / "nonexistent")
    assert code == 2


def test_format_drift_empty() -> None:
    from lwiki.raw_tracker import DriftResult

    r = DriftResult(frozenset(), frozenset(), frozenset())
    assert "No changes" in format_drift_report(r)
