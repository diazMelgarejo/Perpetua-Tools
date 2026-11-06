"""Pin nested redaction, bounded replacements and non-destructive exports."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from orchestrator.coordination.topology_hygiene import (
    LEGACY_REDACTED,
    classify_payload,
    main,
    portable_payload,
)

PRIVATE = "/" + "/".join(("home", "synthetic", "private"))


def test_nested_topology_is_classified_and_redacted() -> None:
    """Nested legacy metadata participates in classification before scrubbing."""
    payload = {"metadata": {"items": [{"worktree": f"topic/private@{PRIVATE}"}]}}
    assert classify_payload(payload) == "legacy_label"
    safe = portable_payload(payload)
    assert safe is not None
    assert safe["metadata"]["items"][0]["worktree"] == LEGACY_REDACTED
    assert PRIVATE not in json.dumps(safe)


def test_nested_unknown_topology_is_withheld() -> None:
    """An unknown nested topology shape cannot masquerade as topology-free."""
    assert portable_payload({"metadata": {"worktree": {"unknown": True}}}) is None


def test_common_branch_name_preserves_unrelated_values() -> None:
    """A short branch name must not corrupt event kinds, actor IDs or prose."""
    payload = {
        "worktree": f"agent@{PRIVATE}",
        "kind": "agent_claim",
        "agent_id": "agent-1",
        "notes": "an agent handles agent_claim; branch=agent",
    }
    safe = portable_payload(payload)
    assert safe is not None
    assert safe["kind"] == "agent_claim"
    assert safe["agent_id"] == "agent-1"
    assert safe["notes"] == f"an agent handles agent_claim; branch={LEGACY_REDACTED}"


@pytest.mark.parametrize("anchor", ["/", "~", "/\\~"])
def test_bare_anchor_does_not_corrupt_unrelated_values(anchor: str) -> None:
    """Bare anchors are not replaced inside unrelated strings or keys."""
    label = f"agent@{anchor}"
    payload = {"worktree": label, "note": f"label={label}; path=/safe/~/name", "/safe/key": "ok"}
    safe = portable_payload(payload)
    assert safe is not None
    assert safe["worktree"] == LEGACY_REDACTED
    assert safe["note"] == f"label={LEGACY_REDACTED}; path=/safe/~/name"
    assert safe["/safe/key"] == "ok"


def test_redacted_key_collision_is_withheld() -> None:
    """Redaction must not silently discard one of two colliding map entries."""
    payload = {"worktree": f"topic/private@{PRIVATE}", PRIVATE: 1, LEGACY_REDACTED: 2}
    assert portable_payload(payload) is None


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_export_refuses_database_alias_without_truncation(tmp_path: Path, alias: str) -> None:
    """Export cannot truncate its own source through any existing file alias."""
    source = tmp_path / "gossip.db"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE gossip(id INTEGER PRIMARY KEY, event_uuid, ts, event_type, payload_json)")
        db.execute("INSERT INTO gossip VALUES(1, 'event-1', 1, 'heartbeat', '{}')")
    output = source if alias == "same" else tmp_path / "output.jsonl"
    if alias == "symlink":
        try:
            output.symlink_to(source)
        except OSError:
            pytest.skip("symlink creation is unavailable for this test account")
    elif alias == "hardlink":
        os.link(source, output)
    before = source.read_bytes()
    assert main(["export", "--db", str(source), "--out", str(output)]) == 1
    assert source.read_bytes() == before


def test_export_writes_distinct_destination(tmp_path: Path) -> None:
    """A valid separate output still receives the sanitized portable view."""
    source = tmp_path / "gossip.db"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE gossip(id INTEGER PRIMARY KEY, event_uuid, ts, event_type, payload_json)")
        db.execute("INSERT INTO gossip VALUES(1, 'event-1', 1, 'heartbeat', '{}')")
    output = tmp_path / "output.jsonl"
    assert main(["export", "--db", str(source), "--out", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["uuid"] == "event-1"
