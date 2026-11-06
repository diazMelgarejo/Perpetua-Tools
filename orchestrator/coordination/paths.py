"""Path and worktree helpers for the coordination package."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.coordination import producer_identity  # noqa: E402
from orchestrator.gossip_bus import (  # noqa: E402
    resolve_gossip_db_path,
)


def canonical_db_path() -> str:
    """Return the canonical GossipBus DB path for this repo."""
    return resolve_gossip_db_path()


def current_worktree_label() -> str:
    """Return this worktree's producer label for coordination events.

    Compatibility name retained (D2). Until 2026-11-06 this returned
    ``<branch>@<cwd>``, which published branch names and workstation layout
    into the shared event log. It now returns the worktree's random opaque
    identifier (``ptp-<32 hex>``), stable across restarts, or the fixed
    placeholder ``ptp-unavailable`` when the identifier cannot be read or
    created. It never raises, so emit paths cannot crash on labeling.
    """
    return producer_identity.current_producer_id()
