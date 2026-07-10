"""orchestrator/startup_intelligence.py
---------------------------------------
Startup scenario and fleet mode engine for Perpetua-Tools.

After probing four backends (Mac Ollama, Mac LM Studio, Windows Ollama,
Windows LM Studio) and checking for a cloud API key, this module encodes
exactly which of the six named scenarios the system is in and emits the
corresponding fallback chains and routing hints.

This replaces ad-hoc if/else chains in callers with a clean named vocabulary.

Phase 2 addition: FleetMode enum and classify_fleet_mode() for distributed
peer topology detection (SOLO, PAIR, FLEET).

Public surface:
    StartupScenario       — Enum of the 6 possible startup states
    FallbackChain         — Dataclass carrying ordered backend preferences
    SCENARIO_TABLE        — Mapping from scenario to its FallbackChain
    classify_scenario     — Pure function: bool flags → StartupScenario
    build_routing_hints   — Reads startup_history entries → adaptive hints dict
    FleetMode             — Enum of peer topology states (Phase 2)
    classify_fleet_mode   — Pure function: (peers_reachable, cross_reachable) → FleetMode
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = [
    "StartupScenario",
    "FallbackChain",
    "SCENARIO_TABLE",
    "classify_scenario",
    "build_routing_hints",
    "FleetMode",
    "classify_fleet_mode",
]


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------

class StartupScenario(str, Enum):
    """The six mutually-exclusive states the system can find itself in at startup."""

    FULL_DISTRIBUTED = "FULL_DISTRIBUTED"   # mac_any AND win_any
    MAC_OLLAMA_ONLY  = "MAC_OLLAMA_ONLY"    # mac_ok only
    MAC_LMS_ONLY     = "MAC_LMS_ONLY"       # mac_lms_ok only
    MAC_DUAL         = "MAC_DUAL"           # both mac_ok AND mac_lms_ok
    CLOUD_ONLY       = "CLOUD_ONLY"         # no local backends; cloud API key present
    FULLY_OFFLINE    = "FULLY_OFFLINE"      # nothing reachable


class FleetMode(str, Enum):
    """Peer topology classification (Phase 2 — distributed mesh states).

    Describes the reachability and connectivity of the peer fleet to this node:
        SOLO   — no peer nodes reachable (peers_reachable == 0)
        PAIR   — 1 peer reachable, or 2+ peers but fragmented (cross-reachability lost)
        FLEET  — 2+ peers reachable AND cross-reachable (full mesh topology)
    """

    SOLO = "SOLO"    # No peers reachable
    PAIR = "PAIR"    # 1 peer, or 2+ peers but not fully cross-reachable
    FLEET = "FLEET"  # 2+ peers AND cross-reachable


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class FallbackChain:
    """Ordered backend preferences for a given startup scenario."""

    manager_backends: list[str]  # ordered preference for manager role
    coder_backends: list[str]    # ordered preference for coder role
    cloud_ok: bool               # whether cloud fallback is appropriate
    description: str             # human-readable summary


# ---------------------------------------------------------------------------
# Scenario table
# ---------------------------------------------------------------------------

SCENARIO_TABLE: dict[StartupScenario, FallbackChain] = {
    StartupScenario.FULL_DISTRIBUTED: FallbackChain(
        manager_backends=["mac-ollama", "mac-lmstudio"],
        coder_backends=["windows-lmstudio", "windows-ollama", "mac-ollama", "mac-lmstudio"],
        cloud_ok=False,
        description="Both Mac and Windows backends are reachable — full distributed mode.",
    ),
    StartupScenario.MAC_OLLAMA_ONLY: FallbackChain(
        manager_backends=["mac-ollama"],
        coder_backends=["mac-ollama"],
        cloud_ok=False,
        description="Only Mac Ollama is reachable — single-node local mode.",
    ),
    StartupScenario.MAC_LMS_ONLY: FallbackChain(
        manager_backends=["mac-lmstudio"],
        coder_backends=["mac-lmstudio"],
        cloud_ok=False,
        description="Only Mac LM Studio is reachable — single-node local mode.",
    ),
    StartupScenario.MAC_DUAL: FallbackChain(
        manager_backends=["mac-ollama", "mac-lmstudio"],
        coder_backends=["mac-ollama", "mac-lmstudio"],
        cloud_ok=False,
        description="Both Mac backends are reachable — Mac dual mode.",
    ),
    StartupScenario.CLOUD_ONLY: FallbackChain(
        manager_backends=["cloud-api"],
        coder_backends=["cloud-api"],
        cloud_ok=True,
        description="No local backends reachable — cloud API fallback only.",
    ),
    StartupScenario.FULLY_OFFLINE: FallbackChain(
        manager_backends=[],
        coder_backends=[],
        cloud_ok=False,
        description="No backends reachable and no cloud key — fully offline.",
    ),
}


# ---------------------------------------------------------------------------
# classify_scenario
# ---------------------------------------------------------------------------

def classify_scenario(
    mac_ok: bool,
    mac_lms_ok: bool,
    win_ok: bool,
    lms_ok: bool,
    cloud_ok: bool = False,
) -> StartupScenario:
    """Map backend probe results to a named StartupScenario.

    Priority order (first matching rule wins):
      1. mac_any AND win_any  → FULL_DISTRIBUTED
      2. mac_ok AND mac_lms_ok → MAC_DUAL
      3. mac_ok only          → MAC_OLLAMA_ONLY
      4. mac_lms_ok only      → MAC_LMS_ONLY
      5. cloud_ok             → CLOUD_ONLY
      6. default              → FULLY_OFFLINE

    Note: Win-without-Mac is not a valid manager scenario — it falls through
    to CLOUD_ONLY (if cloud_ok) or FULLY_OFFLINE.
    """
    mac_any = mac_ok or mac_lms_ok
    win_any = win_ok or lms_ok

    if mac_any and win_any:
        return StartupScenario.FULL_DISTRIBUTED
    if mac_ok and mac_lms_ok:
        return StartupScenario.MAC_DUAL
    if mac_ok and not mac_lms_ok:
        return StartupScenario.MAC_OLLAMA_ONLY
    if mac_lms_ok and not mac_ok:
        return StartupScenario.MAC_LMS_ONLY
    if cloud_ok:
        return StartupScenario.CLOUD_ONLY
    return StartupScenario.FULLY_OFFLINE


# ---------------------------------------------------------------------------
# build_routing_hints
# ---------------------------------------------------------------------------

def build_routing_hints(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive adaptive routing hints from the last 5 entries of startup_history.

    Args:
        history: List of dicts loaded from .state/startup_history.jsonl.
                 Expected keys per entry (all optional):
                   win_ip              — str, the Windows IP used that run
                   win_lms_latency_ms  — int/float, Win LM Studio probe latency
                   mac_ol_latency_ms   — int/float, Mac Ollama probe latency

    Returns:
        {
            "win_ip_hint": str | None,
            "win_lms_p50_ms": int | None,
            "mac_ol_p50_ms": int | None,
            "suggested_timeout_win_lms": int,  # 6 if p50 > 2000ms, else 3
            "suggested_timeout_mac_ol": int,   # always 3 (Mac is local)
        }

    Never raises. Returns safe defaults on empty/malformed history.
    """
    _default: dict[str, Any] = {
        "win_ip_hint": None,
        "win_lms_p50_ms": None,
        "mac_ol_p50_ms": None,
        "suggested_timeout_win_lms": 3,
        "suggested_timeout_mac_ol": 3,
    }

    if not history:
        return _default

    try:
        recent = history[-5:]

        # Most recent successful win_ip — scan newest to oldest
        win_ip_hint: str | None = None
        for entry in reversed(recent):
            ip = entry.get("win_ip")
            if isinstance(ip, str) and ip:
                win_ip_hint = ip
                break

        # Collect valid latency samples from the window
        win_lms_latencies: list[float] = []
        mac_ol_latencies: list[float] = []

        for entry in recent:
            wl = entry.get("win_lms_latency_ms")
            if isinstance(wl, (int, float)):
                win_lms_latencies.append(float(wl))

            ml = entry.get("mac_ol_latency_ms")
            if isinstance(ml, (int, float)):
                mac_ol_latencies.append(float(ml))

        win_lms_p50: int | None = (
            int(statistics.median(win_lms_latencies))
            if len(win_lms_latencies) >= 2
            else None
        )
        mac_ol_p50: int | None = (
            int(statistics.median(mac_ol_latencies))
            if len(mac_ol_latencies) >= 2
            else None
        )

        suggested_timeout_win_lms = (
            6 if (win_lms_p50 is not None and win_lms_p50 > 2000) else 3
        )

        return {
            "win_ip_hint": win_ip_hint,
            "win_lms_p50_ms": win_lms_p50,
            "mac_ol_p50_ms": mac_ol_p50,
            "suggested_timeout_win_lms": suggested_timeout_win_lms,
            "suggested_timeout_mac_ol": 3,
        }

    except Exception:  # noqa: BLE001 — never crash callers, always return safe defaults
        return _default


# ---------------------------------------------------------------------------
# classify_fleet_mode (Phase 2)
# ---------------------------------------------------------------------------

def classify_fleet_mode(
    peers_reachable: int,
    cross_reachable: bool,
) -> FleetMode:
    """Classify peer fleet topology based on reachability and cross-connectivity.

    Pure function: no side effects, no I/O. Maps observed peer state to one of
    three fleet modes (SOLO, PAIR, FLEET) used for adaptive degradation behavior.

    Args:
        peers_reachable: count of peer nodes this node can reach directly (0, 1, 2+).
        cross_reachable: whether peers can reach each other (forms a mesh).
                        Only meaningful when peers_reachable >= 2.

    Returns:
        FleetMode.SOLO:  peers_reachable <= 0 (isolated, no peer connectivity)
        FleetMode.PAIR:  peers_reachable == 1 (one peer), or
                        peers_reachable >= 2 but cross_reachable == False (fragmented)
        FleetMode.FLEET: peers_reachable >= 2 AND cross_reachable == True (full mesh)

    Classification logic (priority order, first match wins):
      1. peers_reachable <= 0 → SOLO (baseline isolation, including invalid negative counts)
      2. 1 peer → PAIR (point-to-point link)
      3. 2+ peers, not cross-reachable → PAIR (fragmented topology, fallback to resilient ops)
      4. 2+ peers, cross-reachable → FLEET (full mesh, optimal for quorum/consensus)

    Edge cases:
      • peers_reachable < 0 is invalid; treated as SOLO (safe default)
      • cross_reachable is ignored when peers_reachable < 2
      • Ties and exact boundaries are deterministic (no floating-point)

    Reference: 2026-07-08 self-healing mesh plan § 4.1–4.3
    """
    if peers_reachable <= 0:
        return FleetMode.SOLO
    if peers_reachable == 1:
        return FleetMode.PAIR
    # peers_reachable >= 2
    if cross_reachable:
        return FleetMode.FLEET
    return FleetMode.PAIR  # fragmented topology
