"""Tests for .agent/memory/memory_search.py's index-staleness detection."""

import importlib.util
import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest


def _load_module(monkeypatch, tmp_path):
    """Load memory_search.py fresh with MEMORY_DIR/INDEX_PATH pointed at tmp_path.

    The module resolves these paths at import time from its own file location,
    so a fresh spec-based import (rather than a plain `import`) lets each test
    get an isolated module object with monkeypatched constants.
    """
    module_path = (
        Path(__file__).parent.parent / ".agent" / "memory" / "memory_search.py"
    )
    spec = importlib.util.spec_from_file_location("memory_search_test", module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["memory_search_test"] = mod
    spec.loader.exec_module(mod)

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    index_dir = memory_dir / ".index"
    index_dir.mkdir()
    monkeypatch.setattr(mod, "MEMORY_DIR", memory_dir)
    monkeypatch.setattr(mod, "INDEX_DIR", index_dir)
    monkeypatch.setattr(mod, "INDEX_PATH", index_dir / "memory.db")
    return mod, memory_dir


def _build_index(mod, filenames):
    """Write a minimal memories table listing exactly `filenames`."""
    with sqlite3.connect(mod.INDEX_PATH) as conn:
        conn.execute("CREATE TABLE memories (filename TEXT, content TEXT)")
        conn.execute(f"PRAGMA user_version = {mod.INDEX_VERSION}")
        for f in filenames:
            conn.execute("INSERT INTO memories VALUES (?, ?)", (f, ""))


def test_needs_rebuild_false_when_index_matches_filesystem(monkeypatch, tmp_path):
    """An up-to-date index with the same files needs no rebuild."""
    mod, memory_dir = _load_module(monkeypatch, tmp_path)
    (memory_dir / "a.md").write_text("hello", encoding="utf-8")
    _build_index(mod, ["a.md"])
    # Index must be newer than the source file's mtime for the fast-path
    # mtime check to pass.
    time.sleep(0.01)
    mod.INDEX_PATH.touch()
    assert mod.needs_rebuild() is False


def test_needs_rebuild_true_when_indexed_file_deleted(monkeypatch, tmp_path):
    """indexed - current: a row exists for a file no longer on disk."""
    mod, memory_dir = _load_module(monkeypatch, tmp_path)
    _build_index(mod, ["deleted.md"])
    mod.INDEX_PATH.touch()
    assert mod.needs_rebuild() is True


def test_needs_rebuild_true_when_filesystem_file_never_indexed(monkeypatch, tmp_path):
    """current - indexed: regression case for the CR fix.

    Previously `needs_rebuild()` only checked `indexed - current`, so a file
    present on disk but absent from the index (current - indexed) was
    invisible to staleness detection whenever its mtime happened to be <=
    the index mtime — e.g. an index rebuilt from a narrower glob in an
    older run, or same-tick file creation. The fix (symmetric difference)
    must catch this direction too.
    """
    mod, memory_dir = _load_module(monkeypatch, tmp_path)
    (memory_dir / "untracked.md").write_text("hello", encoding="utf-8")
    _build_index(mod, [])  # index knows about nothing
    # Force the index to be newer than the file, so the mtime fast-path
    # cannot catch this — only the symmetric-difference check can.
    time.sleep(0.01)
    mod.INDEX_PATH.touch()
    assert mod.needs_rebuild() is True


def test_search_marks_current_retracted_lesson_and_ignores_old_claim(monkeypatch, tmp_path):
    """Search labels retractions from current JSONL even when markdown is stale."""
    mod, memory = _load_module(monkeypatch, tmp_path)
    semantic = memory / "semantic"
    semantic.mkdir()
    rows = [
        {"id": "lesson_x", "status": "accepted", "claim": "old obsolete guidance nebula"},
        {"id": "lesson_x", "status": "retracted", "claim": " ".join(["word"] * 50) + " current guidance quasar"},
    ]
    (semantic / "lessons.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    (semantic / "LESSONS.md").write_text("- old obsolete guidance nebula\n- " + rows[-1]["claim"])
    mod.build_index()
    results = mod.search_fts5("quasar")
    assert any("[RETRACTED]" in snippet and "quasar" in snippet for _, snippet in results)
    assert not mod.search_fts5("nebula")


def test_fallback_search_uses_current_structured_lessons(monkeypatch, tmp_path):
    """Fallback search also labels retracted results and excludes stale markdown."""
    mod, memory = _load_module(monkeypatch, tmp_path)
    semantic = memory / "semantic"
    semantic.mkdir()
    (semantic / "lessons.jsonl").write_text(
        json.dumps({"id": "x", "status": "retracted", "claim": "current quasar"}) + "\n"
    )
    (semantic / "LESSONS.md").write_text("old nebula")
    assert any("[RETRACTED]" in snippet for _, snippet in mod.search_fallback("quasar"))
    assert not mod.search_fallback("nebula")
