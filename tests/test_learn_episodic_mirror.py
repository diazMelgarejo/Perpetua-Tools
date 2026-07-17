"""Regression tests for .agent/tools/learn.py's episodic-mirror fix.

See .agent/memory/working/2026-07-16-learn-py-manual-stage-episodic-mirror-
diagnosis.md for the full incident: stage() wrote candidate JSON with
evidence_ids: [now] but never wrote a matching AGENT_LEARNINGS.jsonl
record, so the evidence_id never resolved to anything. Found via a
CodeRabbit referential-integrity finding on PT PR #246.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_module(monkeypatch, tmp_path):
    """Load learn.py fresh with BASE/CANDIDATES pointed at tmp_path.

    learn.py resolves BASE from its own __file__ location and does
    sys.path inserts for sibling harness/memory utility modules at import
    time — those utility imports (text.word_set, cluster.pattern_id,
    path_hygiene.sanitize_tracked_path_leaks) are fine to resolve against
    the real .agent/ tree since they're standalone helpers, not tied to
    any specific candidates/episodic directory. Only BASE and CANDIDATES
    (used inside stage()/_append_episodic_mirror for file I/O) need to be
    monkeypatched to keep this test isolated from real memory files.
    """
    module_path = Path(__file__).parent.parent / ".agent" / "tools" / "learn.py"
    spec = importlib.util.spec_from_file_location("learn_test", module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["learn_test"] = mod
    spec.loader.exec_module(mod)

    base = tmp_path / "agent"
    (base / "memory" / "candidates").mkdir(parents=True)
    (base / "memory" / "episodic").mkdir(parents=True)
    (base / "memory" / "semantic").mkdir(parents=True)
    monkeypatch.setattr(mod, "BASE", str(base))
    monkeypatch.setattr(mod, "CANDIDATES", str(base / "memory" / "candidates"))
    return mod, base


def _read_episodic(base):
    path = base / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_stage_writes_episodic_mirror(monkeypatch, tmp_path):
    mod, base = _load_module(monkeypatch, tmp_path)
    cid, path = mod.stage(
        "Always serialize timestamps in UTC to avoid comparison bugs",
        ["timestamps", "utc"],
    )
    entries = _read_episodic(base)
    assert len(entries) == 1
    assert entries[0]["action"] == f"manual-stage:{cid}"
    assert entries[0]["source"]["skill"] == "learn"
    assert Path(path).is_file()


def test_evidence_id_resolves_to_the_mirror(monkeypatch, tmp_path):
    """The regression this fix targets: evidence_ids[0] in the candidate
    must equal the timestamp of a real episodic record, not a promise
    with nothing behind it.
    """
    mod, base = _load_module(monkeypatch, tmp_path)
    cid, path = mod.stage(
        "Always serialize timestamps in UTC to avoid comparison bugs",
        ["timestamps", "utc"],
    )
    candidate = json.loads(Path(path).read_text())
    evidence_ts = candidate["evidence_ids"][0]

    entries = _read_episodic(base)
    matching = [e for e in entries if e["timestamp"] == evidence_ts]
    assert len(matching) == 1, (
        f"evidence_id {evidence_ts!r} must resolve to exactly one episodic "
        f"record, found {len(matching)}"
    )
    assert matching[0]["evidence_ids"] == [evidence_ts]


def test_stage_routes_episodic_mirror_through_append_jsonl(monkeypatch, tmp_path):
    """Manual staging must use the locked append_jsonl helper so concurrent
    auto_dream os.replace cycles cannot orphan mirror writes.
    """
    mod, base = _load_module(monkeypatch, tmp_path)
    captured = []

    def _capture(path, entry):
        captured.append((path, dict(entry)))
        episodic = base / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl"
        episodic.parent.mkdir(parents=True, exist_ok=True)
        with episodic.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry) + "\n")
        return entry

    monkeypatch.setattr(mod, "append_jsonl", _capture)
    cid, _path = mod.stage(
        "Always serialize timestamps in UTC to avoid comparison bugs",
        ["timestamps", "utc"],
    )
    assert len(captured) == 1
    episodic_path, entry = captured[0]
    assert episodic_path.endswith("AGENT_LEARNINGS.jsonl")
    assert entry["action"] == f"manual-stage:{cid}"
    assert entry["evidence_ids"]


def test_stage_fails_closed_when_mirror_write_errors(monkeypatch, tmp_path):
    """Mirror-write success is enforced: a forced OSError from the mirror
    must propagate, leave no published candidate JSON, and leave no
    success result behind.
    """
    mod, base = _load_module(monkeypatch, tmp_path)

    def _boom(*_args, **_kwargs):
        raise OSError("forced mirror-write failure")

    monkeypatch.setattr(mod, "_append_episodic_mirror", _boom)

    with pytest.raises(OSError, match="forced mirror-write failure"):
        mod.stage(
            "Always serialize timestamps in UTC to avoid comparison bugs",
            ["timestamps", "utc"],
        )

    candidates_dir = base / "memory" / "candidates"
    assert list(candidates_dir.glob("*.json")) == []
    assert list(candidates_dir.glob("*.tmp")) == []
    assert _read_episodic(base) == []
