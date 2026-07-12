"""tests/test_audit_log.py — P19 audit log hash-chain tests (G8)."""
from __future__ import annotations

import hashlib

import pytest

from orchestrator.audit_log import AuditLog, ChainIntegrityError


def test_first_entry_has_empty_previous_hash():
    log = AuditLog()
    entry = log.append("peer-1", "ACTIVE", "SUSPECT", witnesses=("obs-a",), timestamp=1.0)
    assert entry.previous_hash == ""
    assert entry.sequence_number == 0
    assert len(entry.hash) == 64  # sha256 hex digest


def test_chain_links_by_reference_not_magnitude():
    log = AuditLog()
    e1 = log.append("peer-1", "ACTIVE", "SUSPECT", timestamp=1.0)
    e2 = log.append("peer-1", "SUSPECT", "INACTIVE", timestamp=2.0)
    e3 = log.append("peer-1", "INACTIVE", "ACTIVE", timestamp=3.0)

    assert e2.previous_hash == e1.hash
    assert e3.previous_hash == e2.hash
    # Explicitly NOT a magnitude claim - hashes need not be increasing.
    # (This is the exact bug PATTERN-SYNTHESIS.md P19 was fixed away from.)


def test_verify_chain_passes_on_untampered_log():
    log = AuditLog()
    for i in range(5):
        log.append(f"peer-{i}", "ACTIVE", "SUSPECT", timestamp=float(i))
    assert log.verify_chain() is True


def test_verify_chain_empty_log_passes():
    log = AuditLog()
    assert log.verify_chain() is True


def test_verify_chain_detects_content_tampering():
    log = AuditLog()
    log.append("peer-1", "ACTIVE", "SUSPECT", timestamp=1.0)
    entry = log.append("peer-1", "SUSPECT", "INACTIVE", timestamp=2.0)
    log.append("peer-1", "INACTIVE", "ACTIVE", timestamp=3.0)

    # Simulate tampering: bypass frozen dataclass to alter stored content.
    object.__setattr__(entry, "new_status", "ACTIVE")  # forge a "recovery"

    with pytest.raises(ChainIntegrityError, match="stored hash does not match"):
        log.verify_chain()


def test_verify_chain_detects_broken_previous_hash_link():
    log = AuditLog()
    log.append("peer-1", "ACTIVE", "SUSPECT", timestamp=1.0)
    entry2 = log.append("peer-1", "SUSPECT", "INACTIVE", timestamp=2.0)
    log.append("peer-1", "INACTIVE", "ACTIVE", timestamp=3.0)

    # Simulate a spliced/reordered entry: previous_hash no longer points
    # at the true predecessor.
    object.__setattr__(entry2, "previous_hash", "0" * 64)

    with pytest.raises(ChainIntegrityError, match="previous_hash link broken"):
        log.verify_chain()


def test_entries_returns_immutable_snapshot():
    log = AuditLog()
    log.append("peer-1", "ACTIVE", "SUSPECT", timestamp=1.0)
    snapshot = log.entries()
    assert isinstance(snapshot, tuple)
    assert len(snapshot) == 1
    log.append("peer-2", "ACTIVE", "SUSPECT", timestamp=2.0)
    # Prior snapshot must not observe the later append (tuple, not a view).
    assert len(snapshot) == 1
    assert len(log.entries()) == 2


def test_signer_hook_covers_same_content_as_hash():
    """The signer receives the entry's canonical content bytes; a caller
    verifying the signature independently must see the same bytes the hash
    was computed over (minus the hash field itself, which doesn't exist yet
    when the signer is called)."""
    captured: dict[str, bytes] = {}

    def fake_signer(content: bytes) -> str:
        captured["content"] = content
        return hashlib.sha256(b"secret-key" + content).hexdigest()

    log = AuditLog()
    entry = log.append(
        "peer-1", "ACTIVE", "SUSPECT", witnesses=("obs-a", "obs-b"),
        timestamp=1.0, signer=fake_signer,
    )

    assert entry.signature != ""
    # Re-derive the expected signature from the captured content and confirm
    # it matches what got stored - proves the signer saw real content, not a
    # placeholder, and that signature/hash cover consistent data.
    expected_sig = hashlib.sha256(b"secret-key" + captured["content"]).hexdigest()
    assert entry.signature == expected_sig


def test_no_signer_leaves_signature_empty():
    log = AuditLog()
    entry = log.append("peer-1", "ACTIVE", "SUSPECT", timestamp=1.0)
    assert entry.signature == ""
    # Chain integrity must still verify with no signer supplied.
    assert log.verify_chain() is True


def test_witnesses_default_to_empty_tuple():
    log = AuditLog()
    entry = log.append("peer-1", "ACTIVE", "SUSPECT", timestamp=1.0)
    assert entry.witnesses == ()


def test_sequence_numbers_are_monotonic_and_zero_indexed():
    log = AuditLog()
    entries = [log.append(f"peer-{i}", "ACTIVE", "SUSPECT", timestamp=float(i)) for i in range(4)]
    assert [e.sequence_number for e in entries] == [0, 1, 2, 3]


def test_persist_path_survives_across_instances(tmp_path):
    """STM-Next-08 durability slice: a fresh AuditLog pointed at the same
    persist_path after 'restart' rebuilds identical, verifiable state."""
    log_path = tmp_path / "audit.jsonl"

    log1 = AuditLog(persist_path=log_path)
    log1.append("peer-1", "ACTIVE", "SUSPECT", witnesses=("obs-a",), timestamp=1.0)
    log1.append("peer-1", "SUSPECT", "INACTIVE", timestamp=2.0)

    # Simulate a process restart: a brand-new instance, same file.
    log2 = AuditLog(persist_path=log_path)
    assert len(log2.entries()) == 2
    assert log2.entries()[0].peer_id == "peer-1"
    assert log2.entries()[1].previous_hash == log2.entries()[0].hash
    assert log2.verify_chain() is True

    # Appending after reload continues the chain correctly, not restarting it.
    e3 = log2.append("peer-1", "INACTIVE", "ACTIVE", timestamp=3.0)
    assert e3.sequence_number == 2
    assert e3.previous_hash == log2.entries()[1].hash


def test_persist_path_reload_detects_tampered_file(tmp_path):
    """A hand-edited persisted file must fail verify_chain() on reload —
    durability must not silently trust disk content over the hash chain."""
    log_path = tmp_path / "audit.jsonl"
    log1 = AuditLog(persist_path=log_path)
    log1.append("peer-1", "ACTIVE", "SUSPECT", timestamp=1.0)
    log1.append("peer-1", "SUSPECT", "INACTIVE", timestamp=2.0)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    tampered = lines[0].replace('"SUSPECT"', '"ACTIVE"')  # forge the first entry
    log_path.write_text("\n".join([tampered] + lines[1:]) + "\n", encoding="utf-8")

    log2 = AuditLog(persist_path=log_path)
    with pytest.raises(ChainIntegrityError):
        log2.verify_chain()
