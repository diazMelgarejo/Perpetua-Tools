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


def test_current_lesson_texts_handles_invalid_utf8_and_malformed_json(monkeypatch, tmp_path):
    """Invalid UTF-8 bytes are decoded with replacement and malformed JSON lines are skipped."""
    mod, memory = _load_module(monkeypatch, tmp_path)
    semantic = memory / "semantic"
    semantic.mkdir()
    lessons_file = semantic / "lessons.jsonl"
    valid_row = json.dumps({"id": "l1", "status": "accepted", "claim": "valid lesson claim"}).encode("utf-8")
    malformed_json = b"NOT VALID JSON\n"
    invalid_utf8 = b'{"id": "l2", "status": "accepted", "claim": "broken \xff\xfe byte"}\n'
    lessons_file.write_bytes(valid_row + b"\n" + malformed_json + invalid_utf8)

    texts = mod._current_lesson_texts(lessons_file)
    assert len(texts) == 2
    assert any("valid lesson claim" in t for t in texts)
    assert any("broken \ufffd\ufffd byte" in t for t in texts)


def test_fallback_to_legacy_bullets_when_lessons_jsonl_empty(monkeypatch, tmp_path):
    """When lessons.jsonl exists but is empty, search indexes LESSONS.md legacy bullets."""
    mod, memory = _load_module(monkeypatch, tmp_path)
    semantic = memory / "semantic"
    semantic.mkdir()
    (semantic / "lessons.jsonl").write_text("", encoding="utf-8")
    (semantic / "LESSONS.md").write_text("- legacy guidance about starlight\n- legacy rule about photons\n", encoding="utf-8")

    monkeypatch.setattr(mod, "_fallback_command", lambda query, targets: (["fake-search", query, *targets], "stub"))
    monkeypatch.setattr(mod.subprocess, "run", lambda command, **kwargs: type("Result", (), {"stdout": str(semantic / "LESSONS.md")})())
    fallback_results = mod.search_fallback("photons")
    assert any("photons" in snippet or "LESSONS.md" in str(fn) for fn, snippet in fallback_results)

    if mod.check_fts5():
        mod.build_index()
        assert any("starlight" in snippet for _, snippet in mod.search_fts5("starlight"))


def test_status_counts_distinct_filenames(monkeypatch, tmp_path, capsys):
    """--status reports COUNT(DISTINCT filename), not total row count."""
    mod, memory = _load_module(monkeypatch, tmp_path)
    semantic = memory / "semantic"
    semantic.mkdir()
    rows = [
        {"id": "l1", "status": "accepted", "claim": "first lesson"},
        {"id": "l2", "status": "accepted", "claim": "second lesson"},
        {"id": "l3", "status": "accepted", "claim": "third lesson"},
    ]
    (semantic / "lessons.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    (semantic / "LESSONS.md").write_text("## Auto-promoted entries will be appended below\n", encoding="utf-8")
    (memory / "other.md").write_text("other text", encoding="utf-8")

    mod.build_index()
    monkeypatch.setattr(mod, "feature_enabled", lambda: True)
    mod.cmd_status()
    captured = capsys.readouterr()
    assert "Index: 3 files indexed" in captured.out


def test_preamble_matches_return_snippet_and_structured_rows_return_full_claim(monkeypatch, tmp_path):
    """Preamble matches yield a snippet; structured lesson matches yield the full claim."""
    mod, memory = _load_module(monkeypatch, tmp_path)
    semantic = memory / "semantic"
    semantic.mkdir()
    long_preamble = "Preamble intro with special secret galaxy term: " + ("padding " * 50) + "\n## Auto-promoted entries will be appended below\n"
    rows = [
        {"id": "l1", "status": "accepted", "claim": "Claim with special secret galaxy term and " + ("claim details " * 20)},
    ]
    (semantic / "lessons.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    (semantic / "LESSONS.md").write_text(long_preamble, encoding="utf-8")

    mod.build_index()
    results = mod.search_fts5("galaxy")
    preamble_res = [snippet for fn, snippet in results if not snippet.startswith("[ACCEPTED]")]
    structured_res = [snippet for fn, snippet in results if snippet.startswith("[ACCEPTED]")]
    assert len(structured_res) == 1
    assert structured_res[0] == "[ACCEPTED] " + rows[0]["claim"]
    assert len(preamble_res) == 1 and "galaxy" in preamble_res[0]
    assert len(preamble_res[0]) < len(long_preamble.split("## Auto-promoted")[0])


def test_malformed_ids_and_superseded_lessons(monkeypatch, tmp_path):
    """Malformed identifiers are skipped and accepted replacements label prior claims."""
    mod, memory = _load_module(monkeypatch, tmp_path)
    semantic = memory / "semantic"
    semantic.mkdir()
    rows = [{"id": [], "claim": "bad"}, {"id": {"bad": 1}, "claim": "bad"},
            {"id": "old", "status": "accepted", "claim": "older quasar"},
            {"id": "new", "status": "accepted", "claim": "newer quasar", "supersedes": "old"}]
    (semantic / "lessons.jsonl").write_text("\n".join(map(json.dumps, rows)), encoding="utf-8")
    (semantic / "LESSONS.md").write_text("## Auto-promoted entries will be appended below\n", encoding="utf-8")
    assert {text for _, text in mod.search_fallback("quasar")} == {"[SUPERSEDED] older quasar", "[ACCEPTED] newer quasar"}
    if mod.check_fts5():
        mod.build_index()
        assert {text for _, text in mod.search_fts5("quasar")} == {"[SUPERSEDED] older quasar", "[ACCEPTED] newer quasar"}


def test_unicode_fallback_preserves_query_and_snippet_offsets(monkeypatch, tmp_path):
    """Search commands receive original terms and snippets account for casefold expansion."""
    mod, memory = _load_module(monkeypatch, tmp_path)
    (memory / "other.md").write_text("Straße", encoding="utf-8")
    captured = []
    monkeypatch.setattr(mod, "_fallback_command", lambda query, targets: (captured.append(query) or ["fake"], "stub"))
    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: type("Result", (), {"stdout": str(memory / "other.md")})())
    assert mod.search_fallback("Straße")
    assert captured == ["Straße"]
    assert "needle" in mod._make_snippet("ß" * 300 + "needle", "needle", window=50)


def test_bad_lesson_insert_does_not_rollback_prior_documents(monkeypatch, tmp_path):
    """A bad lesson row cannot roll back unrelated indexed files."""
    mod, memory = _load_module(monkeypatch, tmp_path)
    if not mod.check_fts5():
        pytest.skip("SQLite FTS5 unavailable")
    other = memory / "other.md"
    other.write_text("independent comet", encoding="utf-8")
    semantic = memory / "semantic"
    semantic.mkdir()
    lessons = semantic / "LESSONS.md"
    lessons.write_text("preamble", encoding="utf-8")
    (semantic / "lessons.jsonl").write_text(json.dumps({"id": "bad", "claim": "\ud800"}), encoding="utf-8")
    monkeypatch.setattr(mod, "_memory_files", lambda: iter([other, lessons]))
    assert mod.build_index() == 1
    with sqlite3.connect(mod.INDEX_PATH) as conn:
        assert conn.execute("SELECT filename FROM memories").fetchall() == [("other.md",)]


def test_fallback_search_matches_non_adjacent_terms(monkeypatch, tmp_path):
    """Fallback search finds content where query terms are non-adjacent."""
    mod, memory = _load_module(monkeypatch, tmp_path)
    semantic = memory / "semantic"
    semantic.mkdir()
    rows = [
        {"id": "l1", "status": "accepted", "claim": "quantum telemetry requires orbital alignment"},
    ]
    (semantic / "lessons.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    (semantic / "LESSONS.md").write_text("quantum before\n## Auto-promoted entries will be appended below\n", encoding="utf-8")

    results = mod.search_fallback("quantum orbital")
    assert any("[ACCEPTED]" in snippet and "alignment" in snippet for _, snippet in results)
