"""Graduation keeps supersession provenance aligned across durable records."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def graduation(tmp_path, monkeypatch):
    """Run the real graduation entry point against an isolated memory tree."""
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("graduate_supersession_test", root / ".agent/tools/graduate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    candidates = tmp_path / "candidates"
    semantic = tmp_path / "semantic"
    candidates.mkdir()
    semantic.mkdir()
    (semantic / "LESSONS.md").write_text("# Lessons\n", encoding="utf-8")
    candidate = {"id": "testcase", "claim": "Preserve the original decision across graduation retries.",
                 "conditions": ["retry"], "evidence_ids": ["evidence"], "cluster_size": 1}
    (candidates / "testcase.json").write_text(json.dumps(candidate), encoding="utf-8")
    monkeypatch.setattr(module, "CANDIDATES", str(candidates))
    monkeypatch.setattr(module, "SEMANTIC", str(semantic))

    def run(*args):
        """Invoke graduation with the requested additional arguments."""
        monkeypatch.setattr(sys, "argv", ["graduate.py", "testcase", "--rationale", "Reviewed evidence", *args])
        module.main()

    return candidates, semantic, candidate, run


def test_first_graduation_records_supersession_in_candidate(graduation):
    """Both durable records identify the replaced lesson."""
    candidates, semantic, _, run = graduation
    run("--supersedes", "lesson_original")
    lesson = json.loads((semantic / "lessons.jsonl").read_text().splitlines()[-1])
    candidate = json.loads((candidates / "graduated/testcase.json").read_text())
    assert candidate["supersedes"] == lesson["supersedes"] == "lesson_original"


def test_retry_uses_recorded_supersession_not_retry_arguments(graduation):
    """Retry completes the original decision without rewriting semantic history."""
    candidates, semantic, staged, run = graduation
    run("--supersedes", "lesson_original")
    before = (semantic / "lessons.jsonl").read_bytes()
    (candidates / "testcase.json").write_text(json.dumps(staged), encoding="utf-8")
    run("--supersedes", "lesson_different")
    candidate = json.loads((candidates / "graduated/testcase.json").read_text())
    assert candidate["supersedes"] == "lesson_original"
    assert (semantic / "lessons.jsonl").read_bytes() == before


def test_retry_legacy_record_without_supersedes_does_not_invent_link(graduation):
    """A legacy semantic record cannot acquire a new link from retry arguments."""
    candidates, semantic, staged, run = graduation
    run()
    path = semantic / "lessons.jsonl"
    row = json.loads(path.read_text())
    row.pop("supersedes")
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    before = path.read_bytes()
    (candidates / "testcase.json").write_text(json.dumps(staged), encoding="utf-8")
    run("--supersedes", "lesson_different")
    candidate = json.loads((candidates / "graduated/testcase.json").read_text())
    assert candidate.get("supersedes") is None
    assert path.read_bytes() == before
