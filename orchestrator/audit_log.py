"""
orchestrator/audit_log.py — P19 Immutable Append-Only Audit Log (G8).

Records every peer state-change decision (ACTIVE/SUSPECT/INACTIVE
transitions, witness votes, accusations) into a tamper-evident hash chain,
enabling post-incident forensics. This is the concrete implementation of
the pattern already specified in docs/phase-0-specifications/
PATTERN-SYNTHESIS.md P19 — chained by REFERENCE (each entry stores
previous_hash), never by numeric hash magnitude. A cryptographic hash's
numeric value is uniformly distributed and has no meaningful ordering;
requiring "new hash > previous hash" would randomly reject ~50% of
legitimate entries and provides zero tamper-evidence on its own (the fix
for exactly this bug is recorded in PATTERN-SYNTHESIS.md's own history).

Signing scope (explicit, not silently assumed): this module computes and
verifies the hash chain itself. It accepts an optional `signer` callable
(bytes -> str) so a caller can attach a real cryptographic signature (e.g.
Ed25519, matching this codebase's peer_id convention of "ed25519 pub key
hex or hostname" in orchestrator/membership.py) without this module
depending on a specific crypto library. If no signer is supplied, the
`signature` field is left empty and chain verification checks hash
integrity only — key management and signature verification are a separate,
future concern, not implemented here.

Spec reference: PATTERN-SYNTHESIS.md P19 (Immutable Append-Only Audit Log) +
MULTIAGENT-SWARM-SECURITY-ANALYSIS.md Section 3 G8.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Union


@dataclass(frozen=True)
class AuditEntry:
    """
    One immutable audit-log record.

    Fields:
        sequence_number: Monotonic position in this log (0-indexed).
        timestamp: Unix seconds when the state change occurred.
        peer_id: Peer the state change describes.
        old_status: Status before the transition (caller-defined string,
            e.g. "ACTIVE"/"SUSPECT"/"INACTIVE" per StateTransitionManager).
        new_status: Status after the transition.
        witnesses: Tuple of observer_id strings that contributed to this
            decision (empty if not applicable, e.g. a manual accusation).
        previous_hash: SHA256 hex digest of the immediately preceding
            entry's `hash`. Empty string for the first entry (genesis).
        signature: Optional signature over this entry's content, produced
            by the `signer` callable passed to AuditLog.append(). Empty if
            no signer was supplied — see module docstring.
        hash: SHA256 hex digest of (previous_hash || canonical content).
            Computed at construction time; never independently settable.
    """

    sequence_number: int
    timestamp: float
    peer_id: str
    old_status: str
    new_status: str
    witnesses: tuple[str, ...]
    previous_hash: str
    signature: str
    hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hash", self._compute_hash())

    def _content_bytes(self) -> bytes:
        """Canonical, order-stable byte encoding of this entry's content
        (excludes `hash` itself — the hash is computed FROM this content)."""
        payload = {
            "sequence_number": self.sequence_number,
            "timestamp": self.timestamp,
            "peer_id": self.peer_id,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "witnesses": list(self.witnesses),
            "previous_hash": self.previous_hash,
            "signature": self.signature,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _compute_hash(self) -> str:
        return hashlib.sha256(self.previous_hash.encode("utf-8") + self._content_bytes()).hexdigest()


class ChainIntegrityError(ValueError):
    """Raised by AuditLog.verify_chain() when tampering or corruption is detected."""


class AuditLog:
    """
    In-memory, append-only, hash-chained audit log.

    Design:
    - Entries are immutable (AuditEntry is a frozen dataclass); the log
      itself only ever grows via append().
    - Each entry's `previous_hash` equals the prior entry's `hash` — chain
      by reference, not by hash magnitude (see module docstring).
    - verify_chain() walks the whole log, recomputes every entry's hash
      from its content, and confirms it matches both the stored `hash` AND
      the NEXT entry's `previous_hash`. Any mismatch means content was
      altered after the fact, or an entry was inserted/removed/reordered.
    - Optional durable sink (`persist_path`): each `append()` also writes
      the entry's content fields as one JSON line to this file, and the
      constructor replays any existing lines to rebuild in-memory state on
      startup. Only content fields are persisted — `hash` is never stored
      directly, since it is a pure function of content and is recomputed
      by `AuditEntry.__post_init__` on replay; storing it separately would
      let a corrupted file silently claim a false hash instead of the
      mismatch surfacing on read. Descoped from the STM production-wiring
      gate (P5/P6/P13 are not being wired at current single-operator-LAN
      scale — see MULTIAGENT-SWARM-SECURITY-ANALYSIS.md's threat-model
      addendum), but this module's forensic value holds regardless of that
      verdict, so its durability gap is fixed independently.

    Spec reference: PATTERN-SYNTHESIS.md P19 + MULTIAGENT-SWARM-SECURITY-
    ANALYSIS.md G8.
    """

    def __init__(self, persist_path: Optional[Union[str, Path]] = None) -> None:
        self._entries: list[AuditEntry] = []
        self._persist_path = Path(persist_path) if persist_path is not None else None
        if self._persist_path is not None and self._persist_path.exists():
            with self._persist_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    payload = json.loads(line)
                    self._entries.append(
                        AuditEntry(
                            sequence_number=payload["sequence_number"],
                            timestamp=payload["timestamp"],
                            peer_id=payload["peer_id"],
                            old_status=payload["old_status"],
                            new_status=payload["new_status"],
                            witnesses=tuple(payload["witnesses"]),
                            previous_hash=payload["previous_hash"],
                            signature=payload["signature"],
                        )
                    )

    def append(
        self,
        peer_id: str,
        old_status: str,
        new_status: str,
        witnesses: tuple[str, ...] = (),
        *,
        timestamp: Optional[float] = None,
        signer: Optional[Callable[[bytes], str]] = None,
    ) -> AuditEntry:
        """
        Append a new state-change record to the chain.

        Args:
            peer_id: Peer the transition describes.
            old_status: Status before the transition.
            new_status: Status after the transition.
            witnesses: Observer ids that contributed to this decision.
            timestamp: Unix seconds; defaults to time.time() if omitted.
            signer: Optional callable(content_bytes) -> signature string.
                Called with this entry's canonical content bytes (BEFORE
                the hash is computed, so the signature covers the same
                content the hash covers). If omitted, `signature` is "".

        Returns:
            The newly appended, immutable AuditEntry.
        """
        seq = len(self._entries)
        prev_hash = self._entries[-1].hash if self._entries else ""
        ts = time.time() if timestamp is None else timestamp

        # Build twice: once (unsigned) to get canonical content bytes for
        # the signer, once final with the real signature included, since
        # signature is part of the hashed content (frozen dataclass has no
        # in-place mutation path).
        provisional = AuditEntry(
            sequence_number=seq,
            timestamp=ts,
            peer_id=peer_id,
            old_status=old_status,
            new_status=new_status,
            witnesses=tuple(witnesses),
            previous_hash=prev_hash,
            signature="",
        )
        sig = signer(provisional._content_bytes()) if signer is not None else ""

        entry = AuditEntry(
            sequence_number=seq,
            timestamp=ts,
            peer_id=peer_id,
            old_status=old_status,
            new_status=new_status,
            witnesses=tuple(witnesses),
            previous_hash=prev_hash,
            signature=sig,
        )
        self._entries.append(entry)
        if self._persist_path is not None:
            payload = {
                "sequence_number": entry.sequence_number,
                "timestamp": entry.timestamp,
                "peer_id": entry.peer_id,
                "old_status": entry.old_status,
                "new_status": entry.new_status,
                "witnesses": list(entry.witnesses),
                "previous_hash": entry.previous_hash,
                "signature": entry.signature,
            }
            with self._persist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        return entry

    def entries(self) -> tuple[AuditEntry, ...]:
        """Read-only snapshot of the full chain, oldest first."""
        return tuple(self._entries)

    def verify_chain(self) -> bool:
        """
        Walk the entire chain and verify hash-by-reference integrity.

        Returns:
            True if every entry's stored hash matches its recomputed hash,
            AND every entry's previous_hash matches the prior entry's hash
            (genesis entry's previous_hash must be "").

        Raises:
            ChainIntegrityError: if any entry fails verification, with a
                message identifying the sequence_number and the specific
                mismatch (recomputed-hash vs previous-hash-link).
        """
        prev_hash = ""
        for entry in self._entries:
            if entry.previous_hash != prev_hash:
                raise ChainIntegrityError(
                    f"entry {entry.sequence_number}: previous_hash link broken "
                    f"(expected {prev_hash!r}, got {entry.previous_hash!r})"
                )
            recomputed = entry._compute_hash()
            if recomputed != entry.hash:
                raise ChainIntegrityError(
                    f"entry {entry.sequence_number}: stored hash does not match "
                    f"recomputed hash — content was altered after construction"
                )
            prev_hash = entry.hash
        return True
