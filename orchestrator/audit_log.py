"""
orchestrator/audit_log.py — P19 Immutable Append-Only Audit Log (G8).

Records every peer state-change decision into a tamper-evident hash chain.
Each durable row persists the original hash as well as the content fields, so
replay can distinguish intact history from content that was rewritten and then
silently re-hashed. Optional signature verification can provide authenticity;
without it, the chain detects accidental or partial tampering but a fully
rewritten file still requires an external anchor for adversarial protection.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Union


@dataclass(frozen=True)
class AuditEntry:
    """One immutable audit-log record."""

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

    def _unsigned_content_bytes(self) -> bytes:
        """Canonical bytes supplied to signer/signature verifier."""
        unsigned = AuditEntry(
            sequence_number=self.sequence_number,
            timestamp=self.timestamp,
            peer_id=self.peer_id,
            old_status=self.old_status,
            new_status=self.new_status,
            witnesses=self.witnesses,
            previous_hash=self.previous_hash,
            signature="",
        )
        return unsigned._content_bytes()

    def _compute_hash(self) -> str:
        return hashlib.sha256(
            self.previous_hash.encode("utf-8") + self._content_bytes()
        ).hexdigest()


class ChainIntegrityError(ValueError):
    """Raised when persisted or in-memory audit history fails verification."""


SignatureVerifier = Callable[[bytes, str], bool]


class AuditLog:
    """Append-only hash chain with optional durable JSONL persistence.

    Durable appends are committed to disk before the in-memory chain advances.
    Existing durable rows are replayed with their persisted hashes checked, the
    complete chain is verified before any new append is accepted, and optional
    signatures can bind records to an authenticated signer. For hostile storage
    rewrites, callers should additionally anchor a known chain hash externally.
    """

    def __init__(
        self,
        persist_path: Optional[Union[str, Path]] = None,
        *,
        signature_verifier: Optional[SignatureVerifier] = None,
    ) -> None:
        self._entries: list[AuditEntry] = []
        self._persist_path = Path(persist_path) if persist_path is not None else None
        self._signature_verifier = signature_verifier

        if self._persist_path is not None and self._persist_path.exists():
            self._replay_persisted()
            self.verify_chain()

    def _replay_persisted(self) -> None:
        assert self._persist_path is not None
        replayed: list[AuditEntry] = []
        with self._persist_path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    persisted_hash = payload["hash"]
                    entry = AuditEntry(
                        sequence_number=payload["sequence_number"],
                        timestamp=payload["timestamp"],
                        peer_id=payload["peer_id"],
                        old_status=payload["old_status"],
                        new_status=payload["new_status"],
                        witnesses=tuple(payload["witnesses"]),
                        previous_hash=payload["previous_hash"],
                        signature=payload["signature"],
                    )
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ChainIntegrityError(
                        f"invalid persisted audit row at line {line_number}: {exc}"
                    ) from exc

                if entry.hash != persisted_hash:
                    raise ChainIntegrityError(
                        f"entry {entry.sequence_number}: persisted hash does not match "
                        "reconstructed content"
                    )
                if (
                    self._signature_verifier is not None
                    and entry.signature
                    and not self._signature_verifier(
                        entry._unsigned_content_bytes(), entry.signature
                    )
                ):
                    raise ChainIntegrityError(
                        f"entry {entry.sequence_number}: signature verification failed"
                    )
                replayed.append(entry)

        self._entries = replayed

    @staticmethod
    def _payload(entry: AuditEntry) -> dict[str, object]:
        return {
            "sequence_number": entry.sequence_number,
            "timestamp": entry.timestamp,
            "peer_id": entry.peer_id,
            "old_status": entry.old_status,
            "new_status": entry.new_status,
            "witnesses": list(entry.witnesses),
            "previous_hash": entry.previous_hash,
            "signature": entry.signature,
            "hash": entry.hash,
        }

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
        """Persist and then append one immutable audit entry."""
        # Never extend history that has become invalid in memory or after replay.
        self.verify_chain()

        seq = len(self._entries)
        prev_hash = self._entries[-1].hash if self._entries else ""
        ts = time.time() if timestamp is None else timestamp

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
        signature = signer(provisional._content_bytes()) if signer is not None else ""
        entry = AuditEntry(
            sequence_number=seq,
            timestamp=ts,
            peer_id=peer_id,
            old_status=old_status,
            new_status=new_status,
            witnesses=tuple(witnesses),
            previous_hash=prev_hash,
            signature=signature,
        )

        if self._persist_path is not None:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            with self._persist_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(self._payload(entry), sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())

        # Memory may advance only after the sink has durably accepted the row.
        self._entries.append(entry)
        return entry

    def entries(self) -> tuple[AuditEntry, ...]:
        """Read-only snapshot of the full chain, oldest first."""
        return tuple(self._entries)

    def verify_chain(self) -> bool:
        """Verify hashes, links, sequence numbers, and optional signatures."""
        previous_hash = ""
        for expected_sequence, entry in enumerate(self._entries):
            if entry.sequence_number != expected_sequence:
                raise ChainIntegrityError(
                    f"entry {entry.sequence_number}: expected sequence {expected_sequence}"
                )
            if entry.previous_hash != previous_hash:
                raise ChainIntegrityError(
                    f"entry {entry.sequence_number}: previous_hash link broken "
                    f"(expected {previous_hash!r}, got {entry.previous_hash!r})"
                )
            recomputed = entry._compute_hash()
            if recomputed != entry.hash:
                raise ChainIntegrityError(
                    f"entry {entry.sequence_number}: stored hash does not match "
                    "recomputed hash"
                )
            if (
                self._signature_verifier is not None
                and entry.signature
                and not self._signature_verifier(
                    entry._unsigned_content_bytes(), entry.signature
                )
            ):
                raise ChainIntegrityError(
                    f"entry {entry.sequence_number}: signature verification failed"
                )
            previous_hash = entry.hash
        return True
