"""
orchestrator/fleet_topology.py — Fleet topology state management (Phase 2).

Manages the persistent topology state file (~/.openclaw/state/fleet_topology.json)
which records the local node's peer reachability and fleet mode classification.

Core design:
- Immutable FleetTopologyState dataclass (snapshot at a point in time)
- Read/write helpers with hash-gated idempotency (same content = no-op write)
- Schema validation and safe JSON serialization
- Never crashes on I/O errors (returns None or safe defaults)

Reference: 2026-07-08 self-healing mesh plan § 4.1–4.3
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

from orchestrator.startup_intelligence import FleetMode

__all__ = [
    "FleetTopologyState",
    "read_fleet_topology",
    "write_fleet_topology",
    "get_fleet_topology_path",
]

_logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Constants
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FLEET_TOPOLOGY_FILENAME = "fleet_topology.json"


def get_fleet_topology_path() -> Path:
    """Return the canonical path to the fleet topology state file.

    Returns ~/.openclaw/state/fleet_topology.json (creating the directory if needed).
    """
    state_dir = Path.home() / ".openclaw" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / FLEET_TOPOLOGY_FILENAME


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dataclass
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass(frozen=True)
class FleetTopologyState:
    """Immutable snapshot of this node's peer topology state at a point in time.

    Fields:
        local_node: hostname or node ID of this node
        fleet_mode: FleetMode enum (SOLO, PAIR, FLEET)
        peers: list of reachable peer identifiers
        cross_reachable: whether peers can reach each other (only meaningful if 2+ peers)
        timestamp: Unix timestamp (float) when this snapshot was recorded

    Design:
        - Frozen: all fields immutable after creation
        - Schema is JSON-serializable (compatible with fleet_topology.json)
    """

    local_node: str
    fleet_mode: FleetMode
    peers: list[str]  # reachable peer node IDs
    cross_reachable: bool
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        d = asdict(self)
        # Enum → string
        if isinstance(d.get("fleet_mode"), FleetMode):
            d["fleet_mode"] = d["fleet_mode"].value
        return d


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Read/Write Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def read_fleet_topology(path: Path | None = None) -> FleetTopologyState | None:
    """Read fleet topology state from disk.

    Args:
        path: explicit path to fleet_topology.json (default: ~/.openclaw/state/fleet_topology.json)

    Returns:
        FleetTopologyState on success, None if file doesn't exist or is malformed.
        Never raises; logs warnings instead.
    """
    if path is None:
        path = get_fleet_topology_path()

    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        fleet_mode_str = data.get("fleet_mode")
        fleet_mode = FleetMode(fleet_mode_str) if fleet_mode_str else FleetMode.SOLO

        return FleetTopologyState(
            local_node=data.get("local_node", "unknown"),
            fleet_mode=fleet_mode,
            peers=data.get("peers", []),
            cross_reachable=data.get("cross_reachable", False),
            timestamp=data.get("timestamp", 0.0),
        )
    except (ValueError, KeyError, json.JSONDecodeError, OSError) as exc:
        _logger.warning(f"Could not read fleet topology from {path}: {exc}")
        return None


def write_fleet_topology(
    state: FleetTopologyState,
    path: Path | None = None,
) -> bool:
    """Write fleet topology state to disk with hash-gated idempotency.

    Hash-gated idempotency: if the content being written has the same hash as
    the file currently on disk, skip the write (zero I/O). This prevents
    spurious filesystem activity when the topology state is stable.

    Args:
        state: FleetTopologyState to persist
        path: explicit path to fleet_topology.json (default: ~/.openclaw/state/fleet_topology.json)

    Returns:
        True if written, False on any error (permission, disk full, etc.).
        Never raises; logs warnings instead.
    """
    if path is None:
        path = get_fleet_topology_path()

    try:
        # Serialize to JSON
        json_text = json.dumps(state.to_dict(), indent=2, sort_keys=True, ensure_ascii=True)
        json_bytes = json_text.encode("utf-8")

        # Compute hash of new content
        new_hash = hashlib.sha256(json_bytes).hexdigest()

        # Check if file already exists with the same content
        if path.exists():
            existing_content = path.read_bytes()
            existing_hash = hashlib.sha256(existing_content).hexdigest()
            if existing_hash == new_hash:
                # Same content, skip write (idempotent)
                return True

        # Write new content
        path.write_text(json_text, encoding="utf-8")
        return True

    except (OSError, EnvironmentError) as exc:
        _logger.warning(f"Could not write fleet topology to {path}: {exc}")
        return False
