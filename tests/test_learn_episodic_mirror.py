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


def test_append_episodic_mirror_fails_open_on_write_error(monkeypatch, tmp_path):
    """The actual fail-open guarantee: _append_episodic_mirror itself
    swallows OSError rather than propagating it.
    """
    mod, base = _load_module(monkeypatch, tmp_path)
    # Point at a path that cannot be written (parent directory missing).
    monkeypatch.setattr(mod, "BASE", str(tmp_path / "does-not-exist"))
    # Must not raise.
    mod._append_episodic_mirror("deadbeef", "some claim", "2026-01-01T00:00:00+00:00")
