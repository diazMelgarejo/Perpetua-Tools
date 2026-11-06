"""Classify, sanitize, inventory and export coordination topology (closure row C4).

Historical gossip rows carry ``worktree`` labels of the form
``<branch>@<absolute path>``. A new producer identifier does not repair those
rows, and the tracked append-only sources must not be rewritten. This module
therefore works on derived views only:

* ``classify_payload`` sorts a payload into ``opaque``, ``legacy_label``,
  ``no_topology`` or ``unclassified``.
* ``sanitize_topology`` removes a recognized legacy label (and its branch and
  path parts) from every string in the payload. Unclassified topology is
  withheld. Memory recall uses this.
* ``portable_payload`` applies the same sanitization and then fails closed if
  any private-looking path remains. Portable export uses this.
* ``inventory_topology`` / ``inventory_episodic`` report counts only, never
  stored values, and open their inputs read-only.

Command line (counts or sanitized rows only)::

    python -m orchestrator.coordination.topology_hygiene inventory --db PATH
    python -m orchestrator.coordination.topology_hygiene inventory-episodic PATH
    python -m orchestrator.coordination.topology_hygiene export --db PATH --out FILE
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

from orchestrator.coordination.producer_identity import (
    UNAVAILABLE_PRODUCER_ID,
    is_opaque_producer_id,
)

TopologyClass = Literal["opaque", "legacy_label", "no_topology", "unclassified"]

TOPOLOGY_FIELDS = ("worktree", "current_worktree")
LEGACY_REDACTED = "legacy-redacted"
_PLACEHOLDERS = frozenset({"", "?", "-", UNAVAILABLE_PRODUCER_ID, LEGACY_REDACTED})
# ``<branch or ?>@<absolute POSIX path | drive path | home-relative path>``.
_LEGACY_LABEL_RE = re.compile(r"^(?P<branch>[^@\s]*)@(?P<path>(?:/|~|[A-Za-z]:[\\/]).*)$")
# Absolute POSIX roots must start a path (not follow a word, dot or tilde), so
# repository-relative paths such as ``.cursor/private/...`` are not flagged.
# Private home-path fragments with user identifiers (e.g. ``~user/...``) are flagged,
# while approved generic anchors (e.g. ``~/...``) are respected.
_PRIVATE_PATH_RE = re.compile(
    r"(?:(?<![\w.-])/(?:home|Users|root)/|(?<![\w.-])/(?:private/)?(?:tmp|var/folders)/"
    r"|[A-Za-z]:[\\/]Users[\\/]|(?<![\w.-])\\\\Users\\\\"
    r"|(?<![\w.~-])~[a-zA-Z0-9_-]+(?:[/\\:]|$))",
    re.IGNORECASE,
)


class TopologyInventoryError(Exception):
    """An inventory or export input could not be opened read-only."""


def _topology_values(payload: dict[str, Any]) -> list[Any]:
    """Return the values of the topology fields present in ``payload``."""
    return [payload[name] for name in TOPOLOGY_FIELDS if name in payload]


def _classify_value(value: Any) -> TopologyClass:
    """Classify a single topology field value."""
    if value is None or (isinstance(value, str) and value.strip() in _PLACEHOLDERS):
        return "no_topology"
    if is_opaque_producer_id(value):
        return "opaque"
    if isinstance(value, str) and _LEGACY_LABEL_RE.match(value.strip()):
        return "legacy_label"
    return "unclassified"


def classify_payload(payload: Any) -> TopologyClass:
    """Classify a gossip payload by the shape of its topology fields.

    ``unclassified`` wins over ``legacy_label``, which wins over ``opaque``.
    Non-dict payloads are ``unclassified``.
    """
    if not isinstance(payload, dict):
        return "unclassified"
    classes = {_classify_value(value) for value in _topology_values(payload)}
    for rank in ("unclassified", "legacy_label", "opaque"):
        if rank in classes:
            return rank  # type: ignore[return-value]
    return "no_topology"


def _legacy_fragments(payload: dict[str, Any]) -> list[str]:
    """Return label, path and branch fragments to scrub, longest first."""
    fragments: set[str] = set()
    for value in _topology_values(payload):
        if not isinstance(value, str):
            continue
        match = _LEGACY_LABEL_RE.match(value.strip())
        if not match:
            continue
        fragments.add(value.strip())
        fragments.add(match.group("path"))
        branch = match.group("branch")
        if branch and branch not in {"?", "HEAD", "main", "master"}:
            fragments.add(branch)
    return sorted((f for f in fragments if f), key=len, reverse=True)


def _scrub(value: Any, fragments: list[str]) -> Any:
    """Recursively replace legacy fragments inside strings and dictionary keys of ``value``."""
    if isinstance(value, str):
        for fragment in fragments:
            value = value.replace(fragment, LEGACY_REDACTED)
        return value
    if isinstance(value, dict):
        return {
            (_scrub(key, fragments) if isinstance(key, str) else key): _scrub(
                item, fragments
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub(item, fragments) for item in value]
    return value


def _contains_private_path(value: Any) -> bool:
    """Return True when any string inside ``value`` (including dict keys) looks like a private path."""
    if isinstance(value, str):
        return bool(_PRIVATE_PATH_RE.search(value))
    if isinstance(value, dict):
        return any(
            _contains_private_path(k) or _contains_private_path(v)
            for k, v in value.items()
        )
    if isinstance(value, list):
        return any(_contains_private_path(v) for v in value)
    return False


def sanitize_topology(payload: Any) -> Optional[dict[str, Any]]:
    """Return a copy with legacy topology removed, or None if unclassified.

    Opaque identifiers and payloads without topology are returned unchanged
    (as copies). The input is never mutated.
    """
    topology_class = classify_payload(payload)
    if topology_class == "unclassified":
        return None
    result = copy.deepcopy(payload)
    if topology_class == "legacy_label":
        result = _scrub(result, _legacy_fragments(payload))
        for name in TOPOLOGY_FIELDS:
            if name in result and _classify_value(payload[name]) == "legacy_label":
                result[name] = LEGACY_REDACTED
    return result


def portable_payload(payload: Any) -> Optional[dict[str, Any]]:
    """Return an export-safe copy of ``payload`` or None when it must be blocked.

    Blocks unclassified topology and any payload that still contains a
    private-looking path after legacy labels were removed (fail closed).
    """
    sanitized = sanitize_topology(payload)
    if sanitized is None or _contains_private_path(sanitized):
        return None
    return sanitized


def _connect_read_only(db_path: str) -> sqlite3.Connection:
    """Open ``db_path`` read-only; never create or migrate the database."""
    if not Path(db_path).is_file():
        raise TopologyInventoryError("coordination database not found")
    try:
        return sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise TopologyInventoryError(f"cannot open coordination database: {exc}") from exc


def _iter_rows(db_path: str):
    """Yield ``(event_uuid, ts, event_type, payload)`` in row order."""
    conn = _connect_read_only(db_path)
    try:
        cursor = conn.execute(
            "SELECT event_uuid, ts, event_type, payload_json FROM gossip ORDER BY id ASC"
        )
        for event_uuid, ts, event_type, payload_json in cursor:
            try:
                payload = json.loads(payload_json)
            except (TypeError, ValueError):
                payload = None
            yield event_uuid, ts, event_type, payload
    except sqlite3.Error as exc:
        raise TopologyInventoryError(f"cannot read coordination database: {exc}") from exc
    finally:
        conn.close()


def inventory_topology(db_path: str) -> dict[str, int]:
    """Count gossip rows per topology class without returning any values."""
    counts: dict[str, int] = {}
    for _uuid, _ts, _event_type, payload in _iter_rows(db_path):
        topology_class = classify_payload(payload)
        counts[topology_class] = counts.get(topology_class, 0) + 1
    return counts


def inventory_episodic(path: Path) -> dict[str, int]:
    """Count episodic JSONL rows that contain private-looking paths.

    The file is only read. Matching rows are counted, not printed, so the
    inventory itself cannot leak them.
    """
    rows = private = unparseable = 0
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows += 1
            try:
                record = json.loads(line)
            except ValueError:
                unparseable += 1
                continue
            if _contains_private_path(record) or (
                isinstance(record, dict) and _contains_legacy_label(record)
            ):
                private += 1
    return {"rows": rows, "private_path_rows": private, "unparseable_rows": unparseable}


def _contains_legacy_label(value: Any) -> bool:
    """Return True when a string inside ``value`` embeds a legacy label."""
    if isinstance(value, str):
        return any(_LEGACY_LABEL_RE.match(token) for token in value.split())
    if isinstance(value, dict):
        return any(_contains_legacy_label(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_legacy_label(v) for v in value)
    return False


@dataclass
class PortableExport:
    """Result of a portable export: sanitized rows plus per-class counts."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    blocked: int = 0
    counts: dict[str, int] = field(default_factory=dict)


def export_portable_events(db_path: str) -> PortableExport:
    """Build the portable view of the gossip log.

    Rows without topology fields are not counted in ``counts`` but are still
    subject to the private-path block. Local row ids are omitted; the event
    UUID is the portable identity.
    """
    result = PortableExport()
    for event_uuid, ts, event_type, payload in _iter_rows(db_path):
        topology_class = classify_payload(payload)
        if topology_class != "no_topology":
            result.counts[topology_class] = result.counts.get(topology_class, 0) + 1
        safe = portable_payload(payload)
        if safe is None:
            result.blocked += 1
            continue
        result.rows.append(
            {"uuid": event_uuid, "ts": ts, "event_type": event_type, "payload": safe}
        )
    return result


def main(argv: Optional[list[str]] = None) -> int:
    """Command-line entry point; prints counts or writes sanitized rows only."""
    parser = argparse.ArgumentParser(prog="topology_hygiene")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_inv = sub.add_parser("inventory", help="Count gossip rows per topology class")
    p_inv.add_argument("--db", required=True)
    p_epi = sub.add_parser("inventory-episodic", help="Count episodic rows with private paths")
    p_epi.add_argument("path")
    p_exp = sub.add_parser("export", help="Write the sanitized portable view as JSONL")
    p_exp.add_argument("--db", required=True)
    p_exp.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "inventory":
            print(json.dumps(inventory_topology(args.db), sort_keys=True))
        elif args.cmd == "inventory-episodic":
            print(json.dumps(inventory_episodic(Path(args.path)), sort_keys=True))
        else:
            exported = export_portable_events(args.db)
            with open(args.out, "w", encoding="utf-8") as handle:
                for row in exported.rows:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
            print(json.dumps(
                {"exported": len(exported.rows), "blocked": exported.blocked,
                 "counts": exported.counts},
                sort_keys=True,
            ))
    except TopologyInventoryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        # The OS message can echo the supplied path; report the class only.
        print(f"ERROR: {type(exc).__name__} while reading or writing", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
