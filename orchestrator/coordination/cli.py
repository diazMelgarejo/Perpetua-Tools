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
import aiosqlite
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.gossip_bus import (  # noqa: E402
    GossipBus,
    GossipBusError,
    _canonical_repo_state_dir,
    cancel_pending_embeddings_for_current_loop,
)
from orchestrator.handoff_validation import (  # noqa: E402
    HandoffValidationError,
    load_handoff_packet,
)
from orchestrator.coordination.liveness import (  # noqa: E402
    _heartbeat_check,
    _heartbeat_cleanup,
    _heartbeat_dashboard,
    _heartbeat_kill,
    _heartbeat_list,
    _heartbeat_pulse,
    _heartbeat_timeline,
)
from orchestrator.lan_gossip_bridge import make_gossip_bus  # noqa: E402
from orchestrator.coordination.claims import (  # noqa: E402
    claim_task as _claim,
    list_agents as _agents,
    list_claims as _list,
    log_message as _log,
    register_agent as _register,
    release_task as _release,
)
from orchestrator.coordination.paths import (  # noqa: E402
    canonical_db_path,
    current_worktree_label,
)
from orchestrator.coordination.types import (  # noqa: E402
    ClaimResult,
    ClaimSequence,
    PhaseState,
    PhaseStatus,
    QueuedTaskState,
    ReleaseResult,
    ReorderBuffer,
    TaskPriority,
)
from orchestrator.coordination.phases import (  # noqa: E402
    all_phase_states as _all_phase_states,
    detect_blockers as _detect_blockers,
    fetch_phase_events as _fetch_phase_events,
    get_latest_phase_state as _get_latest_phase_state,
    latest_phase_states as _latest_phase_states,
    phase_block as _phase_block,
    phase_complete as _phase_complete,
    phase_list as _phase_list,
    phase_sort_key as _phase_sort_key,
    phase_start as _phase_start,
    phase_status as _phase_status,
    phase_unblock as _phase_unblock,
    phase_update as _phase_update,
    workflow_critical_path as _workflow_critical_path,
)
from orchestrator.coordination.reorder_buffer import (  # noqa: E402
    buffer_drain as _buffer_drain,
    buffer_status as _buffer_status,
    claim_with_seq as _claim_with_seq,
    fetch_reorder_buffer_events as _fetch_reorder_buffer_events,
    get_reorder_buffers as _get_reorder_buffers,
)
from orchestrator.coordination.task_queue import (  # noqa: E402
    ensure_claims_table as _ensure_claims_table,
    fetch_task_events as _fetch_task_events,
    latest_task_snapshots as _latest_task_snapshots,
    queue_add as _queue_add,
    queue_claim as _queue_claim,
    queue_complete as _queue_complete,
    queue_fail as _queue_fail,
    queue_list as _queue_list,
    queue_status as _queue_status,
    release_claim_with_event as _release_claim_with_event,
    task_snapshot as _task_snapshot,
    try_atomic_claim as _try_atomic_claim,
)


def _error(message: str) -> bool:
    print(f"ERROR: {message}", file=sys.stderr)
    return False


def _warning(message: str) -> bool:
    print(f"WARNING: {message}", file=sys.stderr)
    return False


def _exit_code(result: object) -> int:
    return 1 if result is False else 0


async def queue_add_from_handoff(
    bus: GossipBus,
    handoff_path: Path,
    task_name: str,
    phase: str,
    priority: str,
    notes: str,
    depends_on: Optional[str],
    *,
    source_ref: Optional[str] = None,
    expected_base_sha: Optional[str] = None,
) -> bool | None:
    """Validate a v1 packet before admitting its task to the queue.

    The resulting `handoff_admitted` event is an audit record only.  It is not
    a heartbeat pulse because an enqueueing coordinator cannot prove that the
    assigned worker is presently alive.
    """
    try:
        packet = load_handoff_packet(handoff_path)
    except HandoffValidationError as exc:
        return _error(str(exc))
    if source_ref is not None and source_ref != packet.source_ref:
        return _error("--source-ref conflicts with handoff branch")
    if expected_base_sha is not None and expected_base_sha.lower() != packet.expected_base_sha:
        return _error("--expected-base-sha conflicts with handoff starting_head")

    result = await _queue_add(
        bus,
        task_name,
        phase,
        priority,
        notes,
        depends_on,
        source_ref=packet.source_ref,
        expected_base_sha=packet.expected_base_sha,
        required_agent_id=packet.assigned_agent_id,
    )
    if result is False:
        return False
    audit_payload = {
        "kind": "handoff_admitted",
        "schema_version": packet.schema_version,
        "session_id": packet.session_id,
        "job_id": packet.job_id,
        "task_id": packet.task_id,
        "queue_task_name": task_name,
        "agent_id": packet.assigned_agent_id,
        "role": packet.role,
        "branch": packet.branch,
        "starting_head": packet.starting_head,
    }
    if packet.monitorability is not None:
        context = packet.monitorability.phylax
        audit_payload.update(
            {
                "monitorability_schema_version": packet.monitorability.schema_version,
                "oramasys.phylax.policy_pack.id": context.policy_pack_id,
                "oramasys.phylax.policy_pack.version": context.policy_pack_version,
                "oramasys.phylax.risk_tier": context.risk_tier,
                "oramasys.phylax.reported_monitor_decision": context.reported_monitor_decision,
                "oramasys.phylax.severity": context.severity,
                "oramasys.phylax.confidence": context.confidence,
                "oramasys.phylax.escalation_state": context.escalation_state,
                "oramasys.phylax.retention_class": context.retention_class,
                "oramasys.phylax.reasoning_availability": context.reasoning_availability,
                "oramasys.evidence.manifest_sha256": packet.monitorability.integrity.redacted_manifest_sha256,
                "oramasys.provenance.commit_sha": packet.monitorability.integrity.provenance_commit_sha,
            }
        )
    await bus.emit(
        "heartbeat",
        audit_payload,
    )
    print(f"handoff admitted: {packet.task_id}")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Queue Helper Functions
# ─────────────────────────────────────────────────────────────────────────────


def canonical_repo_root() -> Path:
    """Resolve the shared repo root common to every worktree of this repo.

    Deliberately independent of resolve_default_state_dir() and PT_STATE_DIR
    -- runtime state location is a configurable override (multiple
    instances, tests, custom layouts); repository identity is not, and must
    never be influenced by where state happens to be pointed. Falls back to
    cwd only when git resolution itself fails (not in a repo).
    """
    state = _canonical_repo_state_dir()
    return state.parent if state is not None else Path.cwd()





async def _amain(args: argparse.Namespace) -> int:
    if args.cmd == "handoff":
        try:
            packet = load_handoff_packet(args.packet)
        except HandoffValidationError as exc:
            _error(str(exc))
            return 1
        print(f"valid handoff: {packet.task_id}")
        return 0

    bus = make_gossip_bus(canonical_db_path())
    await getattr(bus, "local", bus).init_db()
    result = None
    if args.cmd == "register":
        result = await _register(bus, args.agent_id, args.agent_type, args.model or "?", args.notes or "")
    elif args.cmd == "agents":
        result = await _agents(bus)
    elif args.cmd == "claim":
        if hasattr(args, "seq") and args.seq is not None:
            # New claim with sequence number (Phase 1.3.2)
            result = await _claim_with_seq(bus, args.agent_id, args.seq, args.task, args.notes or "")
        else:
            # Legacy claim without sequence number
            result = await _claim(bus, args.agent_id, args.task, args.notes or "")
    elif args.cmd == "release":
        result = await _release(bus, args.agent_id, args.task)
    elif args.cmd == "list":
        result = await _list(bus, args.task)
    elif args.cmd == "log":
        result = await _log(bus, args.agent_id, args.message)
    elif args.cmd == "phase":
        if args.subcmd == "list":
            result = await _phase_list(bus)
        elif args.subcmd == "status":
            result = await _phase_status(bus, args.phase_name)
        elif args.subcmd == "start":
            depends_on = args.depends_on.split(",") if args.depends_on else None
            result = await _phase_start(bus, args.phase_name, depends_on, args.agent)
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
            result = await _phase_update(bus, args.phase_name, tests_passing, total_tests, args.agent)
        elif args.subcmd == "complete":
            result = await _phase_complete(bus, args.phase_name)
        elif args.subcmd == "block":
            result = await _phase_block(bus, args.phase_name, args.reason)
        elif args.subcmd == "unblock":
            result = await _phase_unblock(bus, args.phase_name, args.reason)
    elif args.cmd == "workflow":
        if args.subcmd == "critical-path":
            result = await _workflow_critical_path(bus)
    elif args.cmd == "queue":
        if args.subcmd == "add":
            if args.handoff is not None:
                result = await queue_add_from_handoff(
                    bus,
                    args.handoff,
                    args.task_name,
                    args.phase,
                    args.priority,
                    args.notes or "",
                    args.depends_on,
                    source_ref=args.source_ref,
                    expected_base_sha=args.expected_base_sha,
                )
            else:
                result = await _queue_add(
                    bus,
                    args.task_name,
                    args.phase,
                    args.priority,
                    args.notes or "",
                    args.depends_on,
                    source_ref=args.source_ref,
                    expected_base_sha=args.expected_base_sha,
                )
        elif args.subcmd == "list":
            result = await _queue_list(bus, args.phase, args.priority, args.agent)
        elif args.subcmd == "claim":
            result = await _queue_claim(bus, args.task_id, args.agent_id)
        elif args.subcmd == "complete":
            result = await _queue_complete(bus, args.task_id, args.agent_id, args.notes or "")
        elif args.subcmd == "fail":
            result = await _queue_fail(bus, args.task_id, args.agent_id, args.notes or "")
        elif args.subcmd == "status":
            result = await _queue_status(bus, args.agent)
    elif args.cmd == "heartbeat":
        if args.subcmd == "list":
            result = await _heartbeat_list(bus)
        elif args.subcmd == "check":
            result = await _heartbeat_check(bus, args.agent_id)
        elif args.subcmd == "dashboard":
            result = await _heartbeat_dashboard(bus)
        elif args.subcmd == "pulse":
            result = await _heartbeat_pulse(bus, args.agent_id)
        elif args.subcmd == "kill":
            result = await _heartbeat_kill(bus, args.agent_id, args.reason)
        elif args.subcmd == "timeline":
            result = await _heartbeat_timeline(bus, args.agent_id, args.hours)
        elif args.subcmd == "cleanup":
            result = await _heartbeat_cleanup(bus)
    elif args.cmd == "buffer":
        if args.subcmd == "status":
            result = await _buffer_status(bus, args.agent)
        elif args.subcmd == "drain":
            result = await _buffer_drain(bus, args.agent_id)
    return _exit_code(result)


def build_parser() -> argparse.ArgumentParser:
    """Build the agent coordination CLI parser.

    Kept separate from main() so Phase 0F can freeze the executable command
    contract before the coordination modules are extracted.
    """
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

    p_handoff = sub.add_parser("handoff", help="Validate agent handoff packets")
    handoff_sub = p_handoff.add_subparsers(dest="subcmd", required=True)
    p_handoff_validate = handoff_sub.add_parser("validate", help="Validate a v1 JSON handoff packet")
    p_handoff_validate.add_argument("packet", type=Path)

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
    p_queue_add.add_argument(
        "--handoff",
        type=Path,
        default=None,
        help="Validated HandoffPacketV1 JSON required by the standard dispatch path",
    )
    p_queue_add.add_argument(
        "--source-ref", default=None,
        help="Git ref (branch/commit-ish) this job's work should be based on"
    )
    p_queue_add.add_argument(
        "--expected-base-sha", default=None,
        help="Expected git SHA at --source-ref; claimants verify HEAD matches before starting work"
    )

    p_queue_list = queue_sub.add_parser("list", help="List queued task snapshots")
    p_queue_list.add_argument("--phase", default=None)
    p_queue_list.add_argument("--priority", default=None)
    p_queue_list.add_argument("--agent", default=None)

    p_queue_claim = queue_sub.add_parser("claim", help="Claim a queued task")
    p_queue_claim.add_argument("task_id")
    p_queue_claim.add_argument("agent_id")

    p_queue_complete = queue_sub.add_parser("complete", help="Mark a queued task complete")
    p_queue_complete.add_argument("task_id")
    p_queue_complete.add_argument("agent_id", help="Must match the task's current claimant")
    p_queue_complete.add_argument("--notes", default="")

    p_queue_fail = queue_sub.add_parser("fail", help="Mark a queued task failed/retry")
    p_queue_fail.add_argument("task_id")
    p_queue_fail.add_argument("agent_id", help="Must match the task's current claimant")
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

    return ap


async def _run_cli(args: argparse.Namespace) -> int:
    try:
        return await _amain(args)
    except GossipBusError as exc:
        _error(str(exc))
        return 1
    finally:
        await cancel_pending_embeddings_for_current_loop()


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()
    return asyncio.run(_run_cli(args))


if __name__ == "__main__":
    raise SystemExit(main())
