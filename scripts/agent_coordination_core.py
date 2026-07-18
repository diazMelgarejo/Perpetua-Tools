#!/usr/bin/env python3
"""scripts/agent_coordination.py — intra-machine multi-agent claim board with distributed task queue.

Reuses the EXISTING orchestrator/GossipBus (SQLite FTS5 event log) as the
coordination channel between concurrent agent sessions on the SAME machine —
different git worktrees, different tools (Claude Code, kimi, cline,
antigravity/gemini), all writing to one shared append-only event log. This is
the intra-machine counterpart to the LAN-peer file-inbox pattern
(lan_peer_assign.py / coord_pulse.sh) used for inter-machine coordination —
same "announce intent, others check before starting" idea, one process away
instead of one network hop away.

DISTRIBUTED TASK QUEUING LAYER:
Extends the basic claim/release model with:
  - Task priority levels (CRITICAL, HIGH, NORMAL, LOW)
  - Automatic retry mechanism (up to max_retries per task)
  - Cross-phase dependencies (task A must complete before B can run)
  - Comprehensive queue state tracking (queued/claimed/completed/failed)
  - CLI commands for enqueuing, monitoring, and completing work

PHASE-BASED WORKFLOW TRACKING:
Tracks multi-phase orchestration with:
  - Phase status (not_started, in_progress, blocked, complete)
  - Test progress per phase (total and passing counts)
  - Agent assignments per phase
  - Inter-phase dependencies and automatic blocker detection
  - Critical path analysis with ETA calculation
  - Phase blockage/unblockage with reason tracking

Zero new infrastructure: GossipBus.emit()/tail()/search() already exist and
already work from any worktree once pointed at the SAME db file. The only
real problem to solve is path resolution — by default GossipBus resolves
`.state/perpetua_core.db` relative to cwd, so each git worktree would get its
OWN separate db unless something pins them all to one. `git rev-parse
--git-common-dir` gives every worktree of the same repo the same answer
(the main checkout's .git dir) with zero new config or env vars, so that's
the canonical anchor this script uses.

Usage:
    # Legacy claim/release API (still supported)
    python3 scripts/agent_coordination.py register <agent_id> <agent_type> [model] [notes]
    python3 scripts/agent_coordination.py agents
    python3 scripts/agent_coordination.py claim <agent_id> <task_name> [notes] [--seq N]
    python3 scripts/agent_coordination.py release <agent_id> <task_name>
    python3 scripts/agent_coordination.py list [task_name]
    python3 scripts/agent_coordination.py log <agent_id> <message>

    # Reorder buffer (Phase 1.3.2) — out-of-order claim buffering
    python3 scripts/agent_coordination.py claim <agent_id> <task_name> [notes] --seq <N>
    python3 scripts/agent_coordination.py buffer status [--agent <agent_id>]
    python3 scripts/agent_coordination.py buffer drain <agent_id>

    # New queue API
    python3 scripts/agent_coordination.py queue add <task_name> <phase> [--priority critical|high|normal|low] [--notes "..."] [--depends-on task_id,...]
    python3 scripts/agent_coordination.py queue list [--phase <phase>] [--priority <level>] [--agent <agent_id>]
    python3 scripts/agent_coordination.py queue claim <task_id> <agent_id>
    python3 scripts/agent_coordination.py queue complete <task_id> [--notes "..."]
    python3 scripts/agent_coordination.py queue fail <task_id> [--notes "..."]
    python3 scripts/agent_coordination.py queue status [--agent <agent_id>]

    # Phase tracking API
    python3 scripts/agent_coordination.py phase list
    python3 scripts/agent_coordination.py phase status <phase_name>
    python3 scripts/agent_coordination.py phase start <phase_name> [--depends-on phase1,phase2] [--agent agent_id]
    python3 scripts/agent_coordination.py phase update <phase_name> --tests-passing 50/69 [--agent agent_id]
    python3 scripts/agent_coordination.py phase complete <phase_name>
    python3 scripts/agent_coordination.py phase block <phase_name> --reason "reason text"
    python3 scripts/agent_coordination.py phase unblock <phase_name> --reason "reason text"

    # Workflow analysis
    python3 scripts/agent_coordination.py workflow critical-path
"""
from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.gossip_bus import GossipBus  # noqa: E402
from orchestrator.lan_gossip_bridge import make_gossip_bus  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Reorder Buffer & Watermark (Phase 1.3.2)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ClaimSequence:
    """Represents an ordered claim event with sequence number."""
    agent_id: str
    claim_num: int
    task: str
    timestamp: float
    notes: str = ""
    worktree: str = ""

    def to_payload(self) -> dict:
        """Convert to JSON-serializable payload for GossipBus."""
        return {
            "kind": "claim_sequence",
            "agent_id": self.agent_id,
            "claim_num": self.claim_num,
            "task": self.task,
            "timestamp": self.timestamp,
            "notes": self.notes,
            "worktree": self.worktree,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "ClaimSequence":
        """Reconstruct ClaimSequence from GossipBus payload."""
        return cls(
            agent_id=payload["agent_id"],
            claim_num=payload["claim_num"],
            task=payload["task"],
            timestamp=payload["timestamp"],
            notes=payload.get("notes", ""),
            worktree=payload.get("worktree", ""),
        )


@dataclass
class ReorderBuffer:
    """Manages per-agent reorder buffering for out-of-order claims."""
    agent_id: str
    buffer: dict[int, ClaimSequence] = field(default_factory=dict)
    watermark: int = 0  # Next expected sequence number

    def add_claim(self, claim: ClaimSequence) -> tuple[list[ClaimSequence], int]:
        """
        Add a claim to the buffer; return (emitted_claims, new_watermark).

        When claim N arrives:
        - If N == watermark: emit N, then check buffer for N+1, N+2, etc.
        - If N > watermark: buffer N (gap exists)
        - If N < watermark: silently drop (already emitted)

        Returns:
          - list of claims ready to emit (in order from watermark)
          - new watermark value
        """
        if claim.claim_num < self.watermark:
            # Already emitted, silently drop
            return ([], self.watermark)

        if claim.claim_num == self.watermark:
            # Claim matches watermark: emit immediately and advance
            emitted = [claim]
            new_watermark = self.watermark + 1

            # Check buffer for consecutive claims
            while new_watermark in self.buffer:
                emitted.append(self.buffer.pop(new_watermark))
                new_watermark += 1

            self.watermark = new_watermark
            return (emitted, new_watermark)
        else:
            # claim.claim_num > watermark: buffer the claim (gap exists).
            # Preserve the first buffered claim; later duplicates/conflicts
            # must not overwrite the causal record that arrived first.
            if claim.claim_num not in self.buffer:
                self.buffer[claim.claim_num] = claim
            return ([], self.watermark)

    def drain(self) -> tuple[list[ClaimSequence], int]:
        """
        Force-drain all buffered claims (advance watermark to max seen + 1).
        Used when buffer timeout expires or explicit drain command issued.
        """
        if not self.buffer:
            return ([], self.watermark)

        max_seen = max(self.buffer.keys())
        emitted = []
        for seq_num in sorted(self.buffer.keys()):
            emitted.append(self.buffer.pop(seq_num))

        self.watermark = max_seen + 1
        return (emitted, self.watermark)

    def status(self) -> dict:
        """Return buffer status as dict."""
        return {
            "agent_id": self.agent_id,
            "watermark": self.watermark,
            "buffered_count": len(self.buffer),
            "buffered_seqs": sorted(self.buffer.keys()),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Queue Data Structures (Task Priority & State)
# ─────────────────────────────────────────────────────────────────────────────


class TaskPriority(Enum):
    """Task priority levels for work distribution."""
    CRITICAL = 1  # Blocks other phases
    HIGH = 2      # Phase blockers
    NORMAL = 3    # Regular work
    LOW = 4       # Nice-to-have

    @classmethod
    def from_string(cls, s: str) -> TaskPriority:
        """Convert string priority to enum."""
        normalized = s.strip().upper()
        for priority in cls:
            if priority.name == normalized:
                return priority
        raise ValueError(f"Unknown priority: {s}. Must be one of {[p.name for p in cls]}")

    def __str__(self) -> str:
        return self.name


class QueuedTaskState(Enum):
    """Task state progression."""
    QUEUED = "queued"           # Waiting for an agent to claim
    CLAIMED = "claimed"         # Agent has announced intent
    COMPLETED = "completed"     # Task finished successfully
    FAILED = "failed"           # Task failed; retry logic applies


class PhaseStatus(Enum):
    """Phase workflow status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"


@dataclass
class PhaseState:
    """Represents a workflow phase and its current state."""
    phase_name: str
    status: PhaseStatus
    assigned_to: list[str] = field(default_factory=list)
    total_tests: int = 0
    tests_passing: int = 0
    blockers: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    notes: str = ""
    estimated_duration_hours: float = 0.0

    def to_payload(self) -> dict:
        """Convert to JSON-serializable payload for GossipBus."""
        return {
            "kind": "phase_event",
            "phase_name": self.phase_name,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "total_tests": self.total_tests,
            "tests_passing": self.tests_passing,
            "blockers": self.blockers,
            "depends_on": self.depends_on,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "notes": self.notes,
            "estimated_duration_hours": self.estimated_duration_hours,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "PhaseState":
        """Reconstruct PhaseState from GossipBus payload."""
        return cls(
            phase_name=payload["phase_name"],
            status=PhaseStatus(payload["status"]),
            assigned_to=payload.get("assigned_to", []),
            total_tests=payload.get("total_tests", 0),
            tests_passing=payload.get("tests_passing", 0),
            blockers=payload.get("blockers", []),
            depends_on=payload.get("depends_on", []),
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            notes=payload.get("notes", ""),
            estimated_duration_hours=payload.get("estimated_duration_hours", 0.0),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Queue Helper Functions
# ─────────────────────────────────────────────────────────────────────────────


def canonical_repo_root() -> Path:
    """Resolve the shared repo root common to every worktree of this repo."""
    common_dir = subprocess.check_output(
        ["git", "rev-parse", "--git-common-dir"], text=True
    ).strip()
    return Path(common_dir).resolve().parent


def canonical_db_path() -> str:
    return str(canonical_repo_root() / ".state" / "perpetua_core.db")


def current_worktree_label() -> str:
    """Human-readable identifier for the calling worktree (branch + cwd)."""
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"], text=True
        ).strip()
    except subprocess.CalledProcessError:
        branch = "?"
    return f"{branch}@{Path.cwd()}"


async def _known_agent_ids(bus: GossipBus) -> set[str]:
    events = await bus.tail(limit=200, event_type="heartbeat")
    return {
        ev["payload"]["agent_id"]
        for ev in events
        if ev["payload"].get("kind") == "agent_register"
    }


async def _register(
    bus: GossipBus, agent_id: str, agent_type: str, model: str, notes: str
) -> None:
    await bus.emit(
        "heartbeat",
        {
            "kind": "agent_register",
            "agent_id": agent_id,
            "agent_type": agent_type,
            "model": model,
            "worktree": current_worktree_label(),
            "notes": notes,
        },
    )
    print(f"registered: {agent_id} ({agent_type}/{model})")


async def _agents(bus: GossipBus) -> None:
    events = await bus.tail(limit=200, event_type="heartbeat")
    latest: dict[str, dict] = {}
    for ev in reversed(events):  # oldest first, so later overwrites
        p = ev["payload"]
        if p.get("kind") != "agent_register":
            continue
        latest[p["agent_id"]] = {
            "agent_type": p.get("agent_type", "?"),
            "model": p.get("model", "?"),
            "worktree": p.get("worktree", "?"),
            "notes": p.get("notes", ""),
            "ts": ev["ts"],
        }
    if not latest:
        print("no agents registered yet")
        return
    for agent_id, info in latest.items():
        print(
            f"{agent_id}  [{info['agent_type']}/{info['model']}]  "
            f"({info['worktree']})  {info['notes']}"
        )


async def _claim(bus: GossipBus, agent_id: str, task: str, notes: str) -> None:
    known = await _known_agent_ids(bus)
    if agent_id not in known:
        print(
            f"WARNING: '{agent_id}' has not registered this session — "
            f"run 'register {agent_id} <type> <model>' first so others can identify you. "
            f"Proceeding anyway (registration is advisory, not enforced)."
        )
    await bus.emit(
        "heartbeat",
        {
            "kind": "agent_claim",
            "agent_id": agent_id,
            "task": task,
            "worktree": current_worktree_label(),
            "notes": notes,
        },
    )
    print(f"claimed: {task} by {agent_id} ({current_worktree_label()})")


async def _release(bus: GossipBus, agent_id: str, task: str) -> None:
    await bus.emit(
        "heartbeat",
        {
            "kind": "agent_release",
            "agent_id": agent_id,
            "task": task,
            "worktree": current_worktree_label(),
        },
    )
    print(f"released: {task} by {agent_id}")


async def _list(bus: GossipBus, task_filter: str | None) -> None:
    events = await bus.tail(limit=200, event_type="heartbeat")
    # Reduce to open claims: last event per task wins; a release cancels a claim.
    state: dict[str, dict] = {}
    for ev in reversed(events):  # oldest first
        p = ev["payload"]
        if p.get("kind") not in ("agent_claim", "agent_release"):
            continue
        task = p.get("task", "?")
        if task_filter and task != task_filter:
            continue
        if p["kind"] == "agent_claim":
            state[task] = {
                "agent_id": p.get("agent_id"),
                "worktree": p.get("worktree"),
                "notes": p.get("notes", ""),
                "ts": ev["ts"],
            }
        else:
            state.pop(task, None)
    if not state:
        print("no open claims" + (f" for '{task_filter}'" if task_filter else ""))
        return
    for task, info in state.items():
        print(f"OPEN  {task}  <- {info['agent_id']}  ({info['worktree']})  {info['notes']}")


async def _log(bus: GossipBus, agent_id: str, message: str) -> None:
    await bus.emit(
        "heartbeat",
        {"kind": "agent_note", "agent_id": agent_id, "message": message},
    )
    print("logged")


# ─────────────────────────────────────────────────────────────────────────────
# Phase Tracking Functions
# ─────────────────────────────────────────────────────────────────────────────


async def _get_latest_phase_state(bus: GossipBus, phase_name: str) -> Optional[PhaseState]:
    """Retrieve the latest state for a given phase."""
    events = await bus.tail(limit=500, event_type="heartbeat")
    for ev in reversed(events):  # newest first
        p = ev["payload"]
        if p.get("kind") == "phase_event" and p.get("phase_name") == phase_name:
            return PhaseState.from_payload(p)
    return None


async def _all_phase_states(bus: GossipBus) -> dict[str, PhaseState]:
    """Retrieve the latest state for all phases."""
    events = await bus.tail(limit=500, event_type="heartbeat")
    latest: dict[str, PhaseState] = {}
    for ev in reversed(events):  # oldest first, newer overwrites
        p = ev["payload"]
        if p.get("kind") != "phase_event":
            continue
        phase_name = p.get("phase_name")
        if phase_name and phase_name not in latest:
            latest[phase_name] = PhaseState.from_payload(p)
    return latest


async def _phase_start(
    bus: GossipBus,
    phase_name: str,
    depends_on: Optional[list[str]] = None,
    agent_id: Optional[str] = None,
) -> None:
    """Start a phase (transition to in_progress)."""
    existing = await _get_latest_phase_state(bus, phase_name)
    if existing and existing.status == PhaseStatus.COMPLETE:
        print(f"WARNING: Phase '{phase_name}' is already COMPLETE. Cannot restart.")
        return

    phase = existing or PhaseState(phase_name=phase_name, status=PhaseStatus.NOT_STARTED)
    phase.status = PhaseStatus.IN_PROGRESS
    phase.started_at = time.time()
    if depends_on:
        phase.depends_on = depends_on
    if agent_id and agent_id not in phase.assigned_to:
        phase.assigned_to.append(agent_id)

    await bus.emit("heartbeat", phase.to_payload())
    print(f"started: {phase_name} (depends_on: {phase.depends_on})")


async def _phase_update(
    bus: GossipBus,
    phase_name: str,
    tests_passing: Optional[int] = None,
    total_tests: Optional[int] = None,
    agent_id: Optional[str] = None,
) -> None:
    """Update phase test progress."""
    phase = await _get_latest_phase_state(bus, phase_name)
    if not phase:
        print(f"ERROR: Phase '{phase_name}' not found. Run 'phase start' first.")
        return

    if tests_passing is not None:
        phase.tests_passing = tests_passing
    if total_tests is not None:
        phase.total_tests = total_tests
    if agent_id and agent_id not in phase.assigned_to:
        phase.assigned_to.append(agent_id)

    await bus.emit("heartbeat", phase.to_payload())
    pct = (
        f" ({100*phase.tests_passing//phase.total_tests if phase.total_tests else 0}%)"
        if phase.total_tests
        else ""
    )
    print(f"updated: {phase_name} {phase.tests_passing}/{phase.total_tests}{pct}")


async def _phase_complete(bus: GossipBus, phase_name: str) -> None:
    """Mark phase as complete."""
    phase = await _get_latest_phase_state(bus, phase_name)
    if not phase:
        print(f"ERROR: Phase '{phase_name}' not found.")
        return

    if phase.status == PhaseStatus.COMPLETE:
        print(f"Phase '{phase_name}' is already complete.")
        return

    # Verify blockers are cleared
    if phase.blockers:
        print(
            f"WARNING: Phase '{phase_name}' has blockers: {phase.blockers}. "
            f"Clear them before marking complete."
        )
        return

    phase.status = PhaseStatus.COMPLETE
    phase.completed_at = time.time()
    await bus.emit("heartbeat", phase.to_payload())
    print(f"completed: {phase_name}")


async def _phase_block(bus: GossipBus, phase_name: str, reason: str) -> None:
    """Mark phase as blocked."""
    phase = await _get_latest_phase_state(bus, phase_name)
    if not phase:
        print(f"ERROR: Phase '{phase_name}' not found.")
        return

    phase.status = PhaseStatus.BLOCKED
    if reason not in phase.blockers:
        phase.blockers.append(reason)

    await bus.emit("heartbeat", phase.to_payload())
    print(f"blocked: {phase_name} — {reason}")


async def _phase_unblock(bus: GossipBus, phase_name: str, reason: str) -> None:
    """Unblock a phase by removing a specific blocker."""
    phase = await _get_latest_phase_state(bus, phase_name)
    if not phase:
        print(f"ERROR: Phase '{phase_name}' not found.")
        return

    if reason in phase.blockers:
        phase.blockers.remove(reason)

    if not phase.blockers:
        phase.status = PhaseStatus.IN_PROGRESS
    else:
        phase.status = PhaseStatus.BLOCKED

    await bus.emit("heartbeat", phase.to_payload())
    print(f"unblocked: {phase_name}")


def _phase_sort_key(name: str) -> tuple[int, tuple[int, ...] | tuple[()], str]:
    """Sort Phase-N[.M[.…]] names numerically; other names lexically."""
    parts = name.split("-")
    if len(parts) >= 2 and parts[0] == "Phase":
        try:
            components = tuple(int(n) for n in parts[1].split("."))
            return (0, components, name)
        except (ValueError, IndexError):
            pass
    return (1, (), name)


async def _phase_list(bus: GossipBus) -> None:
    """List all phases with status and test progress."""
    phases = await _all_phase_states(bus)
    if not phases:
        print("no phases tracked yet")
        return

    for phase_name in sorted(phases.keys(), key=_phase_sort_key):
        phase = phases[phase_name]
        status_emoji = {
            PhaseStatus.COMPLETE: "✅",
            PhaseStatus.IN_PROGRESS: "🔄",
            PhaseStatus.BLOCKED: "⛔",
            PhaseStatus.NOT_STARTED: "⏳",
        }.get(phase.status, "?")

        test_str = (
            f"{phase.tests_passing}/{phase.total_tests}"
            if phase.total_tests
            else "0/0"
        )
        elapsed = ""
        if phase.started_at:
            end_time = phase.completed_at or time.time()
            hours = (end_time - phase.started_at) / 3600
            elapsed = f" [{hours:.1f}h elapsed]"

        deps_str = f" → Depends-on: {', '.join(phase.depends_on)}" if phase.depends_on else ""
        blockers_str = (
            f" → Blockers: {', '.join(phase.blockers)}" if phase.blockers else ""
        )

        print(
            f"{status_emoji} {phase_name:<30} {phase.status.value:<15} "
            f"{test_str} tests{elapsed}{deps_str}{blockers_str}"
        )


async def _phase_status(bus: GossipBus, phase_name: str) -> None:
    """Show detailed status of a single phase."""
    phase = await _get_latest_phase_state(bus, phase_name)
    if not phase:
        print(f"Phase '{phase_name}' not found.")
        return

    print(f"\n=== Phase: {phase_name} ===")
    print(f"Status: {phase.status.value}")
    print(f"Tests: {phase.tests_passing}/{phase.total_tests}")
    print(f"Assigned to: {', '.join(phase.assigned_to) if phase.assigned_to else 'none'}")
    print(
        f"Dependencies: {', '.join(phase.depends_on) if phase.depends_on else 'none'}"
    )
    print(f"Blockers: {', '.join(phase.blockers) if phase.blockers else 'none'}")
    if phase.started_at:
        print(f"Started at: {phase.started_at}")
    if phase.completed_at:
        print(f"Completed at: {phase.completed_at}")
    if phase.notes:
        print(f"Notes: {phase.notes}")
    print()


async def _detect_blockers(
    bus: GossipBus, phase: PhaseState, all_phases: dict[str, PhaseState]
) -> list[str]:
    """Detect phases blocking this phase (unfulfilled dependencies)."""
    blocking = []
    for dep in phase.depends_on:
        dep_phase = all_phases.get(dep)
        if not dep_phase or dep_phase.status != PhaseStatus.COMPLETE:
            blocking.append(dep)
    return blocking


# ─────────────────────────────────────────────────────────────────────────────
# Reorder Buffer Management Functions (Phase 1.3.2)
# ─────────────────────────────────────────────────────────────────────────────


async def _get_reorder_buffers(bus: GossipBus) -> dict[str, ReorderBuffer]:
    """Reconstruct all per-agent reorder buffers from GossipBus event log."""
    events = await bus.tail(limit=1000, event_type="heartbeat")
    buffers: dict[str, ReorderBuffer] = {}

    for ev in reversed(events):
        p = ev["payload"]
        kind = p.get("kind")
        agent_id = p.get("agent_id")
        if not agent_id:
            continue
        if agent_id not in buffers:
            buffers[agent_id] = ReorderBuffer(agent_id=agent_id)
        if kind == "claim_sequence":
            claim = ClaimSequence.from_payload(p)
            buffers[agent_id].add_claim(claim)
        elif kind == "buffer_drained":
            new_watermark = p.get("new_watermark")
            if isinstance(new_watermark, int):
                buffers[agent_id].watermark = max(buffers[agent_id].watermark, new_watermark)
                for seq_num in list(buffers[agent_id].buffer):
                    if seq_num < buffers[agent_id].watermark:
                        buffers[agent_id].buffer.pop(seq_num, None)

    return buffers


async def _claim_with_seq(
    bus: GossipBus, agent_id: str, seq_num: int, task: str, notes: str
) -> None:
    """Emit a claim with sequence number; reorder buffer processes it."""
    # Get pre-emit buffer state
    buffers_before = await _get_reorder_buffers(bus)
    watermark_before = buffers_before.get(agent_id, ReorderBuffer(agent_id)).watermark

    claim = ClaimSequence(
        agent_id=agent_id,
        claim_num=seq_num,
        task=task,
        timestamp=time.time(),
        notes=notes,
        worktree=current_worktree_label(),
    )

    # Emit to bus
    await bus.emit("heartbeat", claim.to_payload())

    # Reconstruct buffer state from ALL events in bus (including the one we just emitted)
    buffers_after = await _get_reorder_buffers(bus)
    buffer_after = buffers_after.get(agent_id, ReorderBuffer(agent_id))
    watermark_after = buffer_after.watermark

    # Determine status based on watermark advancement
    if watermark_after > seq_num:
        # Claim was processed (emitted)
        num_emitted = watermark_after - watermark_before
        print(
            f"claimed (seq {seq_num}): {task} by {agent_id} "
            f"(watermark now {watermark_after}, emitted {num_emitted} claim(s))"
        )
    elif seq_num in buffer_after.buffer:
        # Claim is buffered
        status = buffer_after.status()
        print(
            f"buffered (seq {seq_num}): {task} by {agent_id} "
            f"(watermark {watermark_after}, buffered seqs: {status['buffered_seqs']})"
        )
    else:
        # Shouldn't happen, but handle it
        print(
            f"claimed (seq {seq_num}): {task} by {agent_id} "
            f"(watermark now {watermark_after})"
        )


async def _buffer_status(bus: GossipBus, agent_filter: Optional[str] = None) -> None:
    """Show reorder buffer status for all or specified agents."""
    buffers = await _get_reorder_buffers(bus)
    if not buffers:
        print("no buffer state found")
        return

    print("\n=== Reorder Buffer Status ===")
    for agent_id in sorted(buffers.keys()):
        if agent_filter and agent_id != agent_filter:
            continue
        status = buffers[agent_id].status()
        print(
            f"\n{agent_id}:"
            f"  watermark={status['watermark']}"
            f"  buffered={status['buffered_count']}"
        )
        if status['buffered_seqs']:
            print(f"  buffered_seqs: {status['buffered_seqs']}")


async def _buffer_drain(bus: GossipBus, agent_id: str) -> None:
    """Force-drain buffered claims for an agent (emit all held claims)."""
    buffers = await _get_reorder_buffers(bus)
    if agent_id not in buffers:
        print(f"ERROR: no buffer state for agent {agent_id}")
        return

    buffer = buffers[agent_id]
    if not buffer.buffer:
        print(f"buffer for {agent_id} is already empty (watermark {buffer.watermark})")
        return

    emitted, new_watermark = buffer.drain()
    print(
        f"drained: {agent_id} ({len(emitted)} claims) "
        f"→ watermark {buffer.watermark} to {new_watermark}"
    )
    for claim in emitted:
        print(f"  - seq {claim.claim_num}: {claim.task}")

    # Emit a drain marker to the bus for audit
    await bus.emit(
        "heartbeat",
        {
            "kind": "buffer_drained",
            "agent_id": agent_id,
            "emitted_count": len(emitted),
            "new_watermark": new_watermark,
        },
    )


async def _workflow_critical_path(bus: GossipBus) -> None:
    """Show critical path (longest dependency chain) and ETA."""
    phases = await _all_phase_states(bus)
    if not phases:
        print("no phases tracked yet")
        return

    # Build dependency graph
    graph: dict[str, list[str]] = {}
    for phase_name, phase in phases.items():
        graph[phase_name] = phase.depends_on

    # Find all roots (phases with no dependencies)
    all_phases_set = set(phases.keys())
    roots = [p for p in all_phases_set if not phases[p].depends_on]
    if not roots:
        print("no root phases (circular dependency?)")
        return

    # Find longest path via DFS
    def longest_chain(node: str, visited: set[str]) -> tuple[list[str], float]:
        """Return (path, total_hours) for longest dependency chain from node."""
        if node in visited:
            return ([], 0.0)  # Cycle detected

        visited.add(node)
        phase = phases.get(node)
        if not phase:
            return ([], 0.0)

        current_duration = phase.estimated_duration_hours or 0.0
        if phase.completed_at and phase.started_at:
            current_duration = (phase.completed_at - phase.started_at) / 3600

        # Find longest path among dependents
        max_path: list[str] = []
        max_duration = 0.0
        for dependent, deps in graph.items():
            if node in deps:
                sub_path, sub_duration = longest_chain(dependent, visited.copy())
                if sub_duration + current_duration > max_duration:
                    max_duration = sub_duration + current_duration
                    max_path = [node] + sub_path

        if not max_path:
            max_path = [node]
            max_duration = current_duration

        return (max_path, max_duration)

    # Compute longest chain from each root
    longest_overall: list[str] = []
    longest_duration = 0.0
    for root in roots:
        path, duration = longest_chain(root, set())
        if duration > longest_duration:
            longest_duration = duration
            longest_overall = path

    # Compute ETA
    eta_hours = longest_duration
    print("\n=== Critical Path Analysis ===")
    print(f"Longest chain: {' → '.join(longest_overall)}")
    print(f"Total duration: {eta_hours:.1f} hours")
    print(f"ETA (if started now): +{eta_hours:.1f} hours\n")

    # Show phase durations
    for phase_name in longest_overall:
        phase = phases[phase_name]
        if phase.completed_at and phase.started_at:
            elapsed = (phase.completed_at - phase.started_at) / 3600
        else:
            elapsed = phase.estimated_duration_hours
        status = (
            "✅" if phase.status == PhaseStatus.COMPLETE else
            "🔄" if phase.status == PhaseStatus.IN_PROGRESS else
            "⏳"
        )
        print(f"  {status} {phase_name:<25} {elapsed:>5.1f}h")



# ─────────────────────────────────────────────────────────────────────────────
# Queue Operations (Task Enqueuing, Claiming, Completing, Retrying)
# ─────────────────────────────────────────────────────────────────────────────


async def _queue_add(bus: GossipBus, task_name: str, phase: str, priority: str, notes: str, depends_on: Optional[str]) -> None:
    """Enqueue a new task with optional priority and dependencies."""
    task_id = f"{phase}-{task_name}-{uuid.uuid4().hex[:8]}"
    priority_enum = TaskPriority.from_string(priority)
    depends_on_list = [t.strip() for t in depends_on.split(",")] if depends_on else []
    await bus.emit("heartbeat", {
        "kind": "task_enqueue",
        "task_id": task_id,
        "task_name": task_name,
        "phase": phase,
        "priority": priority_enum.name,
        "priority_level": priority_enum.value,
        "status": QueuedTaskState.QUEUED.value,
        "assigned_agent": None,
        "retry_count": 0,
        "max_retries": 3,
        "depends_on": depends_on_list,
        "notes": notes,
    })
    print(f"enqueued: {task_id} ({phase}, {priority_enum.name})")


_TASK_EVENT_KINDS = (
    "task_enqueue",
    "task_claim",
    "task_complete",
    "task_failed",
    "task_abandoned",
)


async def _task_snapshot(
    bus: GossipBus, task_id: str, events: Optional[list[dict]] = None
) -> Optional[dict]:
    """Fold append-only heartbeat events for one task into a merged snapshot."""
    if events is None:
        events = await bus.tail(limit=500, event_type="heartbeat")
    snapshot: dict = {}
    for ev in reversed(events):
        p = ev["payload"]
        if p.get("task_id") == task_id and p.get("kind") in _TASK_EVENT_KINDS:
            snapshot.update(p)
    return snapshot or None


async def _queue_claim(bus: GossipBus, task_id: str, agent_id: str) -> None:
    """Claim a queued task, blocking if already claimed or deps not satisfied."""
    events = await bus.tail(limit=500, event_type="heartbeat")
    task_state = await _task_snapshot(bus, task_id, events=events)
    if not task_state:
        print(f"ERROR: task {task_id} not found")
        return
    if task_state.get("status") == QueuedTaskState.CLAIMED.value:
        existing_agent = task_state.get("assigned_agent")
        print(f"ERROR: {task_id} already claimed by {existing_agent}.")
        return
    if task_state.get("status") == QueuedTaskState.COMPLETED.value:
        print(f"ERROR: {task_id} already completed. Cannot reclaim.")
        return
    depends_on = task_state.get("depends_on", [])
    if depends_on:
        completed_tasks = set()
        for ev in events:
            p = ev["payload"]
            if p.get("kind") == "task_complete" and p.get("task_id") in depends_on:
                completed_tasks.add(p["task_id"])
        unmet_deps = [tid for tid in depends_on if tid not in completed_tasks]
        if unmet_deps:
            print(f"ERROR: {task_id} unmet dependencies: {', '.join(unmet_deps)}")
            return
    await bus.emit("heartbeat", {
        "kind": "task_claim",
        "task_id": task_id,
        "assigned_agent": agent_id,
        "status": QueuedTaskState.CLAIMED.value,
        "worktree": current_worktree_label(),
    })
    print(f"claimed: {task_id} by {agent_id}")


async def _queue_complete(bus: GossipBus, task_id: str, notes: str) -> None:
    """Mark a task as completed."""
    await bus.emit("heartbeat", {
        "kind": "task_complete",
        "task_id": task_id,
        "status": QueuedTaskState.COMPLETED.value,
        "notes": notes,
    })
    print(f"completed: {task_id}")


async def _queue_fail(bus: GossipBus, task_id: str, notes: str) -> None:
    """Mark a task as failed; retry logic applies if retry_count < max_retries."""
    task_state = await _task_snapshot(bus, task_id)
    if not task_state:
        print(f"ERROR: task {task_id} not found")
        return
    retry_count = task_state.get("retry_count", 0) + 1
    max_retries = task_state.get("max_retries", 3)
    if retry_count < max_retries:
        await bus.emit("heartbeat", {
            "kind": "task_failed",
            "task_id": task_id,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "status": QueuedTaskState.QUEUED.value,
            "notes": f"Retry {retry_count}/{max_retries}: {notes}",
        })
        print(f"failed: {task_id}, retry {retry_count}/{max_retries}")
    else:
        await bus.emit("heartbeat", {
            "kind": "task_abandoned",
            "task_id": task_id,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "status": "abandoned",
            "notes": f"Abandoned after {max_retries} retries: {notes}",
        })
        print(f"abandoned: {task_id} (max retries exceeded)")


async def _queue_list(bus: GossipBus, phase_filter: Optional[str], priority_filter: Optional[str], agent_filter: Optional[str]) -> None:
    """List queued tasks grouped by status, with optional filters."""
    events = await bus.tail(limit=1000, event_type="heartbeat")
    task_states = {}
    for ev in reversed(events):
        p = ev["payload"]
        task_id = p.get("task_id")
        if not task_id or p.get("kind") not in ("task_enqueue", "task_claim", "task_complete", "task_failed", "task_abandoned"):
            continue
        task_states.setdefault(task_id, {}).update(p)
    queued, claimed, completed, failed = {}, {}, {}, {}
    for task_id, state in task_states.items():
        if phase_filter and state.get("phase") != phase_filter:
            continue
        if priority_filter and state.get("priority") != priority_filter.upper():
            continue
        if agent_filter and state.get("assigned_agent") != agent_filter:
            continue
        status = state.get("status")
        if status == QueuedTaskState.QUEUED.value:
            queued[task_id] = state
        elif status == QueuedTaskState.CLAIMED.value:
            claimed[task_id] = state
        elif status == QueuedTaskState.COMPLETED.value:
            completed[task_id] = state
        elif status in (QueuedTaskState.FAILED.value, "abandoned"):
            failed[task_id] = state
    if queued or claimed or completed or failed:
        if queued:
            print(f"\nQUEUED ({len(queued)} tasks):")
            for task_id in sorted(queued.keys(), key=lambda tid: queued[tid].get("priority_level", 999)):
                state = queued[task_id]
                print(f"  [{state.get('priority', '?'):8s}] {task_id}  {state.get('phase', '?')}/{state.get('task_name', '?')}")
        if claimed:
            print(f"\nCLAIMED ({len(claimed)} tasks):")
            for task_id in sorted(claimed.keys()):
                state = claimed[task_id]
                print(f"  [{state.get('priority', '?'):8s}] {task_id}  ← {state.get('assigned_agent', '?')}")
        if completed:
            print(f"\nCOMPLETED ({len(completed)} tasks):")
            completed_ids = ", ".join(sorted(completed.keys())[:10])
            if len(completed) > 10:
                completed_ids += f", ... +{len(completed) - 10} more"
            print(f"  {completed_ids}")
        if failed:
            print(f"\nFAILED ({len(failed)} tasks):")
            for task_id in sorted(failed.keys()):
                state = failed[task_id]
                print(f"  {task_id}  [{state.get('status', '?')}] retry {state.get('retry_count', 0)}/{state.get('max_retries', 3)}")
    else:
        print("no tasks match the given filters")


async def _queue_status(bus: GossipBus, agent_filter: Optional[str]) -> None:
    """Show status of all claimed tasks per agent."""
    events = await bus.tail(limit=1000, event_type="heartbeat")
    task_states = {}
    for ev in reversed(events):
        p = ev["payload"]
        task_id = p.get("task_id")
        if not task_id or p.get("kind") not in ("task_enqueue", "task_claim", "task_complete", "task_failed", "task_abandoned"):
            continue
        task_states.setdefault(task_id, {}).update(p)
    agent_work = {}
    for task_id, state in task_states.items():
        if state.get("status") == QueuedTaskState.CLAIMED.value:
            agent = state.get("assigned_agent", "?")
            if agent_filter and agent != agent_filter:
                continue
            if agent not in agent_work:
                agent_work[agent] = []
            agent_work[agent].append((task_id, state))
    if agent_work:
        print("\nAGENT WORK STATUS:")
        for agent in sorted(agent_work.keys()):
            tasks = agent_work[agent]
            print(f"\n  {agent}  [{len(tasks)} tasks]:")
            for task_id, state in tasks:
                print(f"    - {task_id}  ({state.get('phase', '?')}/{state.get('task_name', '?')})")
    else:
        print("no claimed tasks" + (f" for agent {agent_filter}" if agent_filter else ""))


async def _amain(args: argparse.Namespace) -> None:
    bus = make_gossip_bus(canonical_db_path())
    await getattr(bus, "local", bus).init_db()
    if args.cmd == "register":
        await _register(bus, args.agent_id, args.agent_type, args.model or "?", args.notes or "")
    elif args.cmd == "agents":
        await _agents(bus)
    elif args.cmd == "claim":
        if hasattr(args, "seq") and args.seq is not None:
            # New claim with sequence number (Phase 1.3.2)
            await _claim_with_seq(bus, args.agent_id, args.seq, args.task, args.notes or "")
        else:
            # Legacy claim without sequence number
            await _claim(bus, args.agent_id, args.task, args.notes or "")
    elif args.cmd == "release":
        await _release(bus, args.agent_id, args.task)
    elif args.cmd == "list":
        await _list(bus, args.task)
    elif args.cmd == "log":
        await _log(bus, args.agent_id, args.message)
    elif args.cmd == "phase":
        if args.subcmd == "list":
            await _phase_list(bus)
        elif args.subcmd == "status":
            await _phase_status(bus, args.phase_name)
        elif args.subcmd == "start":
            depends_on = args.depends_on.split(",") if args.depends_on else None
            await _phase_start(bus, args.phase_name, depends_on, args.agent)
        elif args.subcmd == "update":
            # Parse "50/69" format if provided
            tests_passing = None
            total_tests = None
            if args.tests_passing:
                if "/" in args.tests_passing:
                    tp, tt = args.tests_passing.split("/")
                    tests_passing = int(tp)
                    total_tests = int(tt)
                else:
                    tests_passing = int(args.tests_passing)
            await _phase_update(bus, args.phase_name, tests_passing, total_tests, args.agent)
        elif args.subcmd == "complete":
            await _phase_complete(bus, args.phase_name)
        elif args.subcmd == "block":
            await _phase_block(bus, args.phase_name, args.reason)
        elif args.subcmd == "unblock":
            await _phase_unblock(bus, args.phase_name, args.reason)
    elif args.cmd == "workflow":
        if args.subcmd == "critical-path":
            await _workflow_critical_path(bus)
    elif args.cmd == "queue":
        if args.subcmd == "add":
            await _queue_add(
                bus,
                args.task_name,
                args.phase,
                args.priority,
                args.notes or "",
                args.depends_on,
            )
        elif args.subcmd == "list":
            await _queue_list(bus, args.phase, args.priority, args.agent)
        elif args.subcmd == "claim":
            await _queue_claim(bus, args.task_id, args.agent_id)
        elif args.subcmd == "complete":
            await _queue_complete(bus, args.task_id, args.notes or "")
        elif args.subcmd == "fail":
            await _queue_fail(bus, args.task_id, args.notes or "")
        elif args.subcmd == "status":
            await _queue_status(bus, args.agent)
    elif args.cmd == "heartbeat":
        # Lazy import — see the identical circular-import note in
        # agent_coordination_legacy.py's heartbeat dispatch.
        from scripts.agent_coordination import (
            _heartbeat_list,
            _heartbeat_check,
            _heartbeat_dashboard,
            _heartbeat_pulse,
            _heartbeat_kill,
            _heartbeat_timeline,
            _heartbeat_cleanup,
        )
        if args.subcmd == "list":
            await _heartbeat_list(bus)
        elif args.subcmd == "check":
            await _heartbeat_check(bus, args.agent_id)
        elif args.subcmd == "dashboard":
            await _heartbeat_dashboard(bus)
        elif args.subcmd == "pulse":
            await _heartbeat_pulse(bus, args.agent_id)
        elif args.subcmd == "kill":
            await _heartbeat_kill(bus, args.agent_id, args.reason)
        elif args.subcmd == "timeline":
            await _heartbeat_timeline(bus, args.agent_id, args.hours)
        elif args.subcmd == "cleanup":
            await _heartbeat_cleanup(bus)
    elif args.cmd == "buffer":
        if args.subcmd == "status":
            await _buffer_status(bus, args.agent)
        elif args.subcmd == "drain":
            await _buffer_drain(bus, args.agent_id)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    # Existing agent coordination commands
    p_register = sub.add_parser("register")
    p_register.add_argument("agent_id")
    p_register.add_argument("agent_type")
    p_register.add_argument("model", nargs="?", default="")
    p_register.add_argument("notes", nargs="?", default="")

    sub.add_parser("agents")

    p_claim = sub.add_parser("claim", help="Claim a task (legacy or with sequence number)")
    p_claim.add_argument("agent_id")
    p_claim.add_argument("task")
    p_claim.add_argument("notes", nargs="?", default="")
    p_claim.add_argument(
        "--seq", type=int, default=None,
        help="Sequence number for out-of-order claim buffering (Phase 1.3.2)"
    )

    p_release = sub.add_parser("release")
    p_release.add_argument("agent_id")
    p_release.add_argument("task")

    p_list = sub.add_parser("list")
    p_list.add_argument("task", nargs="?", default=None)

    p_log = sub.add_parser("log")
    p_log.add_argument("agent_id")
    p_log.add_argument("message")

    # Phase tracking commands
    p_phase = sub.add_parser("phase", help="Manage workflow phases")
    phase_sub = p_phase.add_subparsers(dest="subcmd", required=True)

    phase_sub.add_parser("list", help="List all phases with status")

    p_phase_status = phase_sub.add_parser("status", help="Show detailed phase status")
    p_phase_status.add_argument("phase_name")

    p_phase_start = phase_sub.add_parser("start", help="Start a phase")
    p_phase_start.add_argument("phase_name")
    p_phase_start.add_argument("--depends-on", default=None, help="Comma-separated list of phases this depends on")
    p_phase_start.add_argument("--agent", default=None, help="Agent ID starting this phase")

    p_phase_update = phase_sub.add_parser("update", help="Update phase progress")
    p_phase_update.add_argument("phase_name")
    p_phase_update.add_argument("--tests-passing", default=None, help="Tests passing (e.g. '50/69' or '50')")
    p_phase_update.add_argument("--agent", default=None, help="Agent ID updating progress")

    p_phase_complete = phase_sub.add_parser("complete", help="Mark phase as complete")
    p_phase_complete.add_argument("phase_name")

    p_phase_block = phase_sub.add_parser("block", help="Block a phase")
    p_phase_block.add_argument("phase_name")
    p_phase_block.add_argument("--reason", required=True, help="Reason for blocking")

    p_phase_unblock = phase_sub.add_parser("unblock", help="Unblock a phase")
    p_phase_unblock.add_argument("phase_name")
    p_phase_unblock.add_argument("--reason", required=True, help="Blocker reason to remove")

    # Workflow analysis commands
    p_workflow = sub.add_parser("workflow", help="Workflow analysis")
    workflow_sub = p_workflow.add_subparsers(dest="subcmd", required=True)
    workflow_sub.add_parser("critical-path", help="Show critical path and ETA")

    # Distributed task queue commands
    p_queue = sub.add_parser("queue", help="Manage GossipBus-backed queued tasks")
    queue_sub = p_queue.add_subparsers(dest="subcmd", required=True)

    p_queue_add = queue_sub.add_parser("add", help="Enqueue a task")
    p_queue_add.add_argument("task_name")
    p_queue_add.add_argument("phase")
    p_queue_add.add_argument(
        "--priority",
        default="normal",
        choices=("critical", "high", "normal", "low", "CRITICAL", "HIGH", "NORMAL", "LOW"),
    )
    p_queue_add.add_argument("--notes", default="")
    p_queue_add.add_argument("--depends-on", default=None)

    p_queue_list = queue_sub.add_parser("list", help="List queued task snapshots")
    p_queue_list.add_argument("--phase", default=None)
    p_queue_list.add_argument("--priority", default=None)
    p_queue_list.add_argument("--agent", default=None)

    p_queue_claim = queue_sub.add_parser("claim", help="Claim a queued task")
    p_queue_claim.add_argument("task_id")
    p_queue_claim.add_argument("agent_id")

    p_queue_complete = queue_sub.add_parser("complete", help="Mark a queued task complete")
    p_queue_complete.add_argument("task_id")
    p_queue_complete.add_argument("--notes", default="")

    p_queue_fail = queue_sub.add_parser("fail", help="Mark a queued task failed/retry")
    p_queue_fail.add_argument("task_id")
    p_queue_fail.add_argument("--notes", default="")

    p_queue_status = queue_sub.add_parser("status", help="Show claimed queue work by agent")
    p_queue_status.add_argument("--agent", default=None)

    # Heartbeat/liveness commands
    p_heartbeat = sub.add_parser("heartbeat", help="Inspect and manage agent liveness")
    heartbeat_sub = p_heartbeat.add_subparsers(dest="subcmd", required=True)

    heartbeat_sub.add_parser("list", help="List tracked agent liveness")

    p_heartbeat_check = heartbeat_sub.add_parser("check", help="Show one agent's liveness")
    p_heartbeat_check.add_argument("agent_id")

    heartbeat_sub.add_parser("dashboard", help="Show liveness summary")

    p_heartbeat_pulse = heartbeat_sub.add_parser("pulse", help="Emit a pulse for this agent")
    p_heartbeat_pulse.add_argument("agent_id")

    p_heartbeat_kill = heartbeat_sub.add_parser("kill", help="Mark an agent killed")
    p_heartbeat_kill.add_argument("agent_id")
    p_heartbeat_kill.add_argument("--reason", required=True)

    p_heartbeat_timeline = heartbeat_sub.add_parser("timeline", help="Show agent activity")
    p_heartbeat_timeline.add_argument("agent_id")
    p_heartbeat_timeline.add_argument("--hours", type=int, default=24)

    heartbeat_sub.add_parser("cleanup", help="Auto-release claims held by DEAD agents")

    # Reorder buffer management (Phase 1.3.2)
    p_buffer = sub.add_parser("buffer", help="Manage reorder buffers for out-of-order claims")
    buffer_sub = p_buffer.add_subparsers(dest="subcmd", required=True)

    p_buffer_status = buffer_sub.add_parser("status", help="Show reorder buffer status")
    p_buffer_status.add_argument("--agent", default=None, help="Filter by agent ID")

    p_buffer_drain = buffer_sub.add_parser("drain", help="Force-drain buffered claims")
    p_buffer_drain.add_argument("agent_id", help="Agent ID to drain")

    args = ap.parse_args()
    asyncio.run(_amain(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
