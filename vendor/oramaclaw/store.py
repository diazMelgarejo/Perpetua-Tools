"""Persistent state store for oramaclaw V1.

``ControlStore`` owns three durable JSON files inside ``target.state_dir``:

- ``registry.json``  — field ownership ledger: which manager last set each
  field path, with a content fingerprint and ISO-8601 timestamp
- ``journal.json``   — transaction log capped at 200 records; newest entry
  last; each record has a transaction_id, state, resources, and timestamps
- ``pending-resolutions.json`` — conflicts that need operator input before
  they can be applied (serialised PendingResolution records)

Additionally, a per-target PID lock is held in ``target.state_dir/oramaclaw.lock``
to prevent concurrent apply runs. Stale lock detection uses:
  1. ``os.kill(pid, 0)`` to check if the process is still alive
  2. ``psutil.Process(pid).create_time()`` to verify it is the SAME process
     (handles PID reuse on macOS/Linux)
  If liveness cannot be determined, a lock older than ``LOCK_STALE_SECONDS`` is
  considered stale as a last-resort fallback.

All writes use ``os.replace()`` for atomic single-file updates.  No field in
any persisted JSON carries a raw secret (auth is reference-only).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from oramaclaw.types import ConfigTarget, PendingResolution

_log = logging.getLogger(__name__)

JOURNAL_CAP = 200
LOCK_STALE_SECONDS = 300

# ── Internal helpers ──────────────────────────────────────────────────────────

def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON to path atomically via a sibling temp file + os.replace()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp~")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("ControlStore: could not read %s — %s; using default", path, exc)
        return default


def _fingerprint(value: Any) -> str:
    """SHA-256 hex of the canonical JSON encoding of a value."""
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


# ── Lock management ───────────────────────────────────────────────────────────

class LockHeld(Exception):
    """Raised when the target lock is already held by another live process."""
    def __init__(self, pid: int, lock_path: Path) -> None:
        self.pid = pid
        self.lock_path = lock_path
        super().__init__(f"oramaclaw lock held by PID {pid} ({lock_path})")


def _pid_is_alive(pid: int, expected_create_time: float | None) -> bool | None:
    """Return whether pid is a live process matching the expected start time."""
    os_kill_failed = False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't own it — still alive.
        pass
    except Exception:
        os_kill_failed = True

    if expected_create_time is None and not os_kill_failed:
        return True

    try:
        import psutil  # type: ignore[import]
    except Exception:
        if not os_kill_failed:
            return True
        return None

    try:
        actual = psutil.Process(pid).create_time()
        # Allow a small delta for clock granularity.
        if expected_create_time is None:
            return True
        return abs(actual - expected_create_time) < 2.0
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True
    except Exception:
        # If os.kill already proved the PID exists, stay conservative.
        if not os_kill_failed:
            return True
        return None


def _acquire_lock(lock_path: Path) -> None:
    """Write a PID lock file, raising LockHeld if another live process holds it."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if lock_path.exists():
        try:
            data = json.loads(lock_path.read_bytes())
            held_pid: int = data.get("pid", -1)
            held_ts: float = data.get("acquired_at", 0.0)
            expected_create_time: float | None = data.get("create_time")

            age = time.time() - held_ts
            alive = _pid_is_alive(held_pid, expected_create_time)
            if alive is True:
                raise LockHeld(held_pid, lock_path)
            if alive is False:
                _log.warning(
                    "ControlStore: overwriting stale lock from dead process (PID %d, age %.0fs)",
                    held_pid,
                    age,
                )
            elif age > LOCK_STALE_SECONDS:
                _log.warning(
                    "ControlStore: overwriting stale lock with unknown liveness (PID %d, age %.0fs)",
                    held_pid,
                    age,
                )
            else:
                raise LockHeld(held_pid, lock_path)
        except LockHeld:
            raise
        except Exception as exc:
            _log.warning("ControlStore: could not parse lock file %s — %s; overwriting", lock_path, exc)

    my_pid = os.getpid()
    create_time: float | None = None
    try:
        import psutil  # type: ignore[import]
        create_time = psutil.Process(my_pid).create_time()
    except Exception:
        pass

    _atomic_write_json(lock_path, {
        "pid": my_pid,
        "acquired_at": time.time(),
        "create_time": create_time,
    })


def _release_lock(lock_path: Path) -> None:
    try:
        if lock_path.exists():
            data = json.loads(lock_path.read_bytes())
            held_pid = data.get("pid")
            if held_pid != os.getpid():
                _log.warning(
                    "ControlStore: lock stolen before release (held by PID %s), skipping unlink",
                    held_pid,
                )
                return
        lock_path.unlink(missing_ok=True)
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("ControlStore: could not release lock %s — %s", lock_path, exc)


# ── Public store ──────────────────────────────────────────────────────────────

class ControlStore:
    """Manages registry, journal, pending resolutions, and PID lock for a target.

    Usage::

        with ControlStore.open(target) as store:
            store.record_ownership("manager", "provider:x", "/effort", "high")
            store.append_journal(tx_id, "committed", ["provider:x"], [], [])
    """

    def __init__(self, target: ConfigTarget) -> None:
        self._target = target
        sd = target.state_dir
        self._registry_path = sd / "registry.json"
        self._journal_path = sd / "journal.json"
        self._pending_path = sd / "pending-resolutions.json"
        self._lock_path = sd / "oramaclaw.lock"
        self._lock_held = False

    # ── Context manager (acquires / releases PID lock) ─────────────────────

    @classmethod
    def open(cls, target: ConfigTarget) -> "ControlStore":
        """Acquire the PID lock and return a ControlStore.

        Caller must call ``close()`` or use as a context manager.
        """
        store = cls(target)
        _acquire_lock(store._lock_path)
        store._lock_held = True
        return store

    def close(self) -> None:
        if self._lock_held:
            _release_lock(self._lock_path)
            self._lock_held = False

    def __enter__(self) -> "ControlStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ── Registry (field ownership ledger) ─────────────────────────────────

    def load_registry(self) -> dict[str, Any]:
        """Return current registry dict keyed by ``<resource_key>/<json_pointer>``."""
        return _load_json(self._registry_path, {})

    def record_ownership(
        self,
        manager: str,
        resource_key: str,
        managed_path: str,
        value: Any,
        *,
        iso_timestamp: str | None = None,
    ) -> None:
        """Record that ``manager`` last set ``managed_path`` on ``resource_key``."""
        registry = self.load_registry()
        entry_key = f"{resource_key}{managed_path}"
        registry[entry_key] = {
            "manager": manager,
            "resource_key": resource_key,
            "managed_path": managed_path,
            "fingerprint": _fingerprint(value),
            "timestamp": iso_timestamp or _iso_now(),
        }
        _atomic_write_json(self._registry_path, registry)

    def get_ownership(self, resource_key: str, managed_path: str) -> dict[str, Any] | None:
        """Return the ownership record for a field, or None if unset."""
        registry = self.load_registry()
        return registry.get(f"{resource_key}{managed_path}")

    def field_fingerprint(self, resource_key: str, managed_path: str) -> str | None:
        """Return the stored fingerprint for a field, or None if unknown."""
        entry = self.get_ownership(resource_key, managed_path)
        return entry["fingerprint"] if entry else None

    # ── Auto-weave overrides ───────────────────────────────────────────────

    def get_auto_weave_override(self, resource_key: str, managed_path: str) -> dict[str, Any] | None:
        """Return the cooperative auto-weave override for a field, or None.

        Override dict shape: {
          "source_field_fingerprint": str,   # fingerprint of desired when override was recorded
          "observed_value": Any,             # the live drift value that was auto-woven
          "observed_fingerprint": str,
          "auto_woven_at": str,              # ISO-8601
        }
        """
        registry = self.load_registry()
        entry = registry.get(f"{resource_key}{managed_path}")
        if entry is None:
            return None
        return entry.get("auto_weave_override")

    def set_auto_weave_override(
        self,
        manager: str,
        resource_key: str,
        managed_path: str,
        observed_value: Any,
        source_field_fingerprint: str,
        *,
        iso_timestamp: str | None = None,
    ) -> None:
        """Record a cooperative drift override for a field."""
        registry = self.load_registry()
        entry_key = f"{resource_key}{managed_path}"
        entry = registry.get(entry_key, {
            "manager": manager,
            "resource_key": resource_key,
            "managed_path": managed_path,
            "fingerprint": _fingerprint(observed_value),
            "timestamp": iso_timestamp or _iso_now(),
        })
        entry["auto_weave_override"] = {
            "source_field_fingerprint": source_field_fingerprint,
            "observed_value": observed_value,
            "observed_fingerprint": _fingerprint(observed_value),
            "auto_woven_at": iso_timestamp or _iso_now(),
        }
        registry[entry_key] = entry
        _atomic_write_json(self._registry_path, registry)

    # ── Journal (transaction log) ──────────────────────────────────────────

    def load_journal(self) -> list[dict[str, Any]]:
        """Return journal records (newest last), capped at JOURNAL_CAP."""
        return _load_json(self._journal_path, [])

    def append_journal(
        self,
        transaction_id: str,
        state: str,
        applied: list[str],
        auto_woven: list[str],
        conflicts: list[str],
        *,
        iso_timestamp: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Append a journal record, trimming to JOURNAL_CAP entries."""
        journal = self.load_journal()
        record: dict[str, Any] = {
            "transaction_id": transaction_id,
            "state": state,
            "applied": applied,
            "auto_woven": auto_woven,
            "conflicts": conflicts,
            "timestamp": iso_timestamp or _iso_now(),
        }
        if extra:
            record.update(extra)
        journal.append(record)
        if len(journal) > JOURNAL_CAP:
            journal = journal[-JOURNAL_CAP:]
        _atomic_write_json(self._journal_path, journal)

    def last_transaction(self) -> dict[str, Any] | None:
        """Return the most recent journal record, or None."""
        journal = self.load_journal()
        return journal[-1] if journal else None

    # ── Pending resolutions ────────────────────────────────────────────────

    def load_pending(self) -> list[dict[str, Any]]:
        """Return all unresolved pending-resolution records."""
        return _load_json(self._pending_path, [])

    def add_pending(self, resolution: PendingResolution) -> None:
        """Persist a new pending resolution (idempotent by resolution_id)."""
        records = self.load_pending()
        # Replace if already present (re-apply of the same conflict).
        records = [r for r in records if r.get("resolution_id") != resolution.resolution_id]
        records.append(_serialise_pending(resolution))
        _atomic_write_json(self._pending_path, records)

    def resolve_pending(self, resolution_id: str, chosen: str, iso_timestamp: str | None = None) -> bool:
        """Mark a pending resolution as resolved.  Returns True if found."""
        records = self.load_pending()
        found = False
        for record in records:
            if record.get("resolution_id") == resolution_id:
                record["resolved_at"] = iso_timestamp or _iso_now()
                record["chosen"] = chosen
                found = True
        if found:
            _atomic_write_json(self._pending_path, records)
        return found

    def pending_by_id(self, resolution_id: str) -> dict[str, Any] | None:
        """Return the raw pending record with the given ID, or None."""
        for record in self.load_pending():
            if record.get("resolution_id") == resolution_id:
                return record
        return None

    def open_conflicts(self) -> list[dict[str, Any]]:
        """Return pending records that have not been resolved yet."""
        return [r for r in self.load_pending() if r.get("resolved_at") is None]


# ── Utilities ─────────────────────────────────────────────────────────────────

def _iso_now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _serialise_pending(resolution: PendingResolution) -> dict[str, Any]:
    c = resolution.conflict
    return {
        "resolution_id": resolution.resolution_id,
        "transaction_id": resolution.transaction_id,
        "created_at": resolution.created_at,
        "resolved_at": resolution.resolved_at,
        "chosen": resolution.chosen,
        "conflict": {
            "resource_key": c.resource_key,
            "manager": c.manager,
            "managed_path": c.managed_path,
            "base_fingerprint": c.base_fingerprint,
            "observed_fingerprint": c.observed_fingerprint,
            "desired_fingerprint": c.desired_fingerprint,
            "security_topology": c.security_topology,
            "choices": list(c.choices),
            "resolution_id": c.resolution_id,
        },
    }
