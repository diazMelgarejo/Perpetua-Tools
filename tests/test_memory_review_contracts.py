from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / ".agent"
MEMORY = AGENT / "memory"
HARNESS = AGENT / "harness"


def _load(name: str, path: Path):
    for candidate in (str(AGENT), str(MEMORY), str(HARNESS)):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shared_feature_reader_fails_closed_and_enables_explicit_key(tmp_path):
    flags = _load("pt_feature_flags", AGENT / "feature_flags.py")
    path = tmp_path / "features.json"
    assert flags.feature_enabled(path, "memory_search_fts") is False
    path.write_text("not json", encoding="utf-8")
    assert flags.feature_enabled(path, "memory_search_fts") is False
    path.write_text(json.dumps({"memory_search_fts": {"enabled": True}}), encoding="utf-8")
    assert flags.feature_enabled(path, "memory_search_fts") is True


def test_auto_dream_write_all_handles_short_writes_and_interrupts(monkeypatch):
    dream = _load("pt_auto_dream", MEMORY / "auto_dream.py")
    calls = []

    def short_write(_fd, view):
        calls.append(bytes(view))
        if len(calls) == 1:
            raise InterruptedError
        return min(2, len(view))

    monkeypatch.setattr(dream.os, "write", short_write)
    dream._write_all(9, b"abcdef")
    assert len(calls) >= 4
    assert calls[-1] == b"ef"


def test_auto_dream_rewrite_sanitizes_nested_entries(tmp_path, monkeypatch):
    dream = _load("pt_auto_dream_sanitize", MEMORY / "auto_dream.py")
    episodic = tmp_path / "events.jsonl"
    monkeypatch.setattr(dream, "EPISODIC", str(episodic))
    dream._write_entries_locked(None, [{"source": {"path": "/home/example/repo"}}])
    text = episodic.read_text(encoding="utf-8")
    assert "/home/example/" not in text
    assert "$HOME/repo" in text


def test_review_state_rejects_candidate_path_escape(tmp_path):
    state = _load("pt_review_state", MEMORY / "review_state.py")
    with pytest.raises(ValueError):
        state.mark_rejected("../escape", "reviewer", "reason", str(tmp_path))


def test_review_state_save_sanitizes_complete_candidate(tmp_path):
    state = _load("pt_review_state_save", MEMORY / "review_state.py")
    path = tmp_path / "candidate.json"
    state.save_candidate({"claim": "/home/example/repo", "nested": {"path": "/home/example/other"}}, str(path))
    text = path.read_text(encoding="utf-8")
    assert "/home/example/" not in text
    assert "$HOME/repo" in text


def test_promote_rolls_back_new_stage_when_prior_cleanup_fails(tmp_path, monkeypatch):
    promote = _load("pt_promote", MEMORY / "promote.py")
    candidates = tmp_path / "candidates"
    rejected = candidates / "rejected"
    rejected.mkdir(parents=True)
    pattern = {
        "id": "candidate1",
        "name": "candidate1",
        "claim": "new durable claim",
        "conditions": [],
        "evidence_ids": ["new"],
        "cluster_size": 1,
        "canonical_salience": 8.0,
    }
    prior = {
        "id": "candidate1",
        "status": "rejected",
        "staged_at": "2026-01-01T00:00:00+00:00",
        "decisions": [{"evidence_snapshot": []}],
        "rejection_count": 1,
    }
    prior_path = rejected / "candidate1.json"
    prior_path.write_text(json.dumps(prior), encoding="utf-8")
    original_remove = promote.os.remove

    def fail_prior(path):
        if Path(path) == prior_path:
            raise OSError("cleanup failed")
        return original_remove(path)

    monkeypatch.setattr(promote.os, "remove", fail_prior)
    with pytest.raises(OSError):
        promote.write_candidates({"candidate1": pattern}, str(candidates))
    assert not (candidates / "candidate1.json").exists()
    assert prior_path.exists()
