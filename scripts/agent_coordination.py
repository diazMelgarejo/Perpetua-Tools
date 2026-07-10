#!/usr/bin/env python3
"""scripts/agent_coordination.py — intra-machine multi-agent claim board.

Reuses the EXISTING orchestrator/GossipBus (SQLite FTS5 event log) as the
coordination channel between concurrent agent sessions on the SAME machine —
different git worktrees, different tools (Claude Code, kimi, cline,
antigravity/gemini), all writing to one shared append-only event log. This is
the intra-machine counterpart to the LAN-peer file-inbox pattern
(lan_peer_assign.py / coord_pulse.sh) used for inter-machine coordination —
same "announce intent, others check before starting" idea, one process away
instead of one network hop away.

Zero new infrastructure: GossipBus.emit()/tail()/search() already exist and
already work from any worktree once pointed at the SAME db file. The only
real problem to solve is path resolution — by default GossipBus resolves
`.state/perpetua_core.db` relative to cwd, so each git worktree would get its
OWN separate db unless something pins them all to one. `git rev-parse
--git-common-dir` gives every worktree of the same repo the same answer
(the main checkout's .git dir) with zero new config or env vars, so that's
the canonical anchor this script uses.

Usage:
    python3 scripts/agent_coordination.py register <agent_id> <agent_type> [model] [notes]
    python3 scripts/agent_coordination.py agents
    python3 scripts/agent_coordination.py claim <agent_id> <task_name> [notes]
    python3 scripts/agent_coordination.py release <agent_id> <task_name>
    python3 scripts/agent_coordination.py list [task_name]
    python3 scripts/agent_coordination.py log <agent_id> <message>

Every agent should REGISTER ONCE per session before claiming anything:
    python3 scripts/agent_coordination.py register kimi-g1-worktree cli-tool kimi-code/kimi-for-coding "G1 provenance dedup"
    python3 scripts/agent_coordination.py register agy-flash-review llm-agent google-antigravity/gemini-3-flash "design review pass"
agent_type is a free string (suggested: cli-tool, llm-agent, human) — this is
an advisory identity registry, not an auth system. `agents` lists every
distinct agent_id ever seen, most recent registration wins per id.

Before starting work on a named task/gap, an agent should:
    1. `register` (once per session) so its identity is visible to others.
    2. `list` to see if anyone else has an open claim on the task.
    3. `claim` to announce intent (worktree path + task + timestamp).
    4. `release` when done (or when abandoning the claim).
Claiming is advisory, not a lock — GossipBus is append-only, so a "claim" is
really "the most recent claim event for this task that has no matching
release event after it." Cheap, good enough for human-supervised concurrent
agent sessions; not a substitute for actual git conflict resolution. An
unregistered agent_id can still claim/release — claim() just prints a
warning — so registration never becomes a hard blocker.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.gossip_bus import GossipBus  # noqa: E402


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


async def _amain(args: argparse.Namespace) -> None:
    bus = GossipBus(canonical_db_path())
    await bus.init_db()
    if args.cmd == "register":
        await _register(bus, args.agent_id, args.agent_type, args.model or "?", args.notes or "")
    elif args.cmd == "agents":
        await _agents(bus)
    elif args.cmd == "claim":
        await _claim(bus, args.agent_id, args.task, args.notes or "")
    elif args.cmd == "release":
        await _release(bus, args.agent_id, args.task)
    elif args.cmd == "list":
        await _list(bus, args.task)
    elif args.cmd == "log":
        await _log(bus, args.agent_id, args.message)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_register = sub.add_parser("register")
    p_register.add_argument("agent_id")
    p_register.add_argument("agent_type")
    p_register.add_argument("model", nargs="?", default="")
    p_register.add_argument("notes", nargs="?", default="")

    sub.add_parser("agents")

    p_claim = sub.add_parser("claim")
    p_claim.add_argument("agent_id")
    p_claim.add_argument("task")
    p_claim.add_argument("notes", nargs="?", default="")

    p_release = sub.add_parser("release")
    p_release.add_argument("agent_id")
    p_release.add_argument("task")

    p_list = sub.add_parser("list")
    p_list.add_argument("task", nargs="?", default=None)

    p_log = sub.add_parser("log")
    p_log.add_argument("agent_id")
    p_log.add_argument("message")

    args = ap.parse_args()
    asyncio.run(_amain(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
