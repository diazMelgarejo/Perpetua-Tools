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
    """Read episodic records from the test workspace."""
    path = base / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_stage_writes_episodic_mirror(monkeypatch, tmp_path):
    """Verify stage writes episodic mirror."""
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
        """Capture the supplied episodic entry."""
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
        """Raise the simulated mirror-write failure."""
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


def test_append_jsonl_survives_malformed_history_lines(tmp_path):
    """Malformed history lines in JSONL do not prevent recording new events."""
    sys.path.insert(0, str(Path(__file__).parent.parent / ".agent" / "harness" / "hooks"))
    from _episodic_io import append_jsonl

    jsonl_file = tmp_path / "test.jsonl"
    jsonl_file.write_text("{\"valid\": 1}\nNOT VALID JSON\n{\"valid\": 2}\n", encoding="utf-8")
    history = jsonl_file.read_bytes()

    entry = {"new": "entry"}
    result = append_jsonl(str(jsonl_file), entry)
    assert result == entry
    assert jsonl_file.read_bytes().startswith(history)

    lines = jsonl_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    assert json.loads(lines[-1]) == entry


def test_append_jsonl_accepts_write_only_log(tmp_path, monkeypatch):
    """Append safely when existing history cannot be opened for reading."""
    import builtins

    sys.path.insert(0, str(Path(__file__).parent.parent / ".agent" / "harness" / "hooks"))
    from _episodic_io import append_jsonl

    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"old":1}')
    real_open = builtins.open

    def deny_read(target, mode="r", *args, **kwargs):
        """Simulate a write-only existing history file."""
        if str(target) == str(path) and "+" in mode:
            raise PermissionError("write-only log")
        return real_open(target, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", deny_read)
    append_jsonl(str(path), {"new": 2})
    assert path.read_bytes() == b'{"old":1}\n{"new": 2}\n'


@pytest.mark.parametrize("module_name", ["data_layer_export", "data_flywheel_export"])
def test_event_export_skips_undecodable_row_and_keeps_following_event(tmp_path, module_name):
    """Verify event export skips undecodable row and keeps following event."""
    module_path = Path(__file__).parent.parent / ".agent" / "tools" / (module_name + ".py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"torn":"\xc3\n{"action":"recorded"}\n')
    rows, quality = module.read_jsonl(path)
    assert rows == [{"action": "recorded"}]
    assert quality["malformed_lines"] == 1


@pytest.mark.parametrize("module_name", ["data_layer_export", "data_flywheel_export"])
@pytest.mark.parametrize("payload,expected,malformed", [
    ('{"action":"utf16"}'.encode("utf-16"), [], 1),
    (b'{"action":"one"}\r\xff\r{"action":"two"}\r',
     [{"action": "one"}, {"action": "two"}], 1),
])
def test_event_export_rejects_non_utf8_and_reads_cr_records(tmp_path, module_name, payload, expected, malformed):
    """Keep CR-delimited UTF-8 events while counting invalid records."""
    module_path = Path(__file__).parent.parent / ".agent" / "tools" / (module_name + ".py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    path = tmp_path / "events.jsonl"
    path.write_bytes(payload)
    rows, quality = module.read_jsonl(path)
    assert rows == expected
    assert quality["malformed_lines"] == malformed
