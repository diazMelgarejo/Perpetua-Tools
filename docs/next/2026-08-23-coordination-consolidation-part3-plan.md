# Coordination Consolidation Part 3: Operational & Daemon Integration Plan

> **2026-11-06 ratification:** Automatic expiry/release is approved for v2 only,
> with expiry and fencing rules; PT stays manual. Retain compatibility shims,
> and qualify both platforms before promotion. See
> [the master handoff](MASTER-CLOSURE-HANDOFF-2026-11-06.md).
> The original v1 daemon and identifier examples below are superseded proposals.
>
> **2026-11-06 scope note:** The Orama master closure plan ("Part 3 review and
> revised scope", items 1 and 4–7) supersedes these implementation details: §2
> (no PT daemon; `heartbeat.py` and `heartbeat_cleanup(...)` do not exist),
> §3 (assert one committed race winner and a valid outcome vocabulary, not nine
> fixed codes; test the reorder buffer's real contract instead of N=1000; label
> simulated and live evidence separately), §4 (retain shims per D2; a repository
> search lists known callers only) and §5 (random opaque identifier, not a
> path/name hash). PT's current manual behavior is in
> [`../coordination/manual-cleanup-characterization-2026-11-06.md`](../coordination/manual-cleanup-characterization-2026-11-06.md).

---

> **2026-11-06 reconciliation:** This remains a v1 draft, not authorization to
> add claim-release behavior or implement the v2 controller. Reconcile its
> proposed daemon behavior with the current master plan and Orama doc 68 first.

**Date:** 2026-08-23  
**Status:** Planning / Architecture Draft  
**Author:** Agnes (Antigravity-Claude)  
**Related Tasks:** `Coordination-Consolidation Part 3: plan next steps-87099ab9`,
PR #263 (Part 1), PR #267 (Part 2)

---

## 1. Overview & Context

With **Part 1 (Atomic Integrity & SQLite lock hardening)** landed via PR #263 and
**Part 2 (Modular package split: `task_queue`, `phases`, `heartbeat`, `reorder_buffer`,
`cli`)** landed via PR #267, the coordination infrastructure is modular and atomically
sound.

**Part 3** addresses the operational and automation layer:

1. Multi-Worktree Coordination Daemon (`heartbeat daemon`).
2. CI Concurrency & Multi-Agent Swarm Test Suite.
3. Legacy CLI Caller Deprecation & Phaseout.
4. Privacy Boundary & Topology Sanitization (Opaque Worktree IDs).

---

## 2. Multi-Worktree Heartbeat Daemon (`orchestrator/coordination/daemon.py`)

### Problem Statement

Currently, `heartbeat cleanup` must be invoked manually or via one-shot scripts to sweep
dead agents and release stale task claims. In environments with 3+ concurrent agent
worktrees (e.g., Claude + Codex + Kimi + Antigravity), stalled agents can block tasks
until human intervention.

### Design

* Implement a non-blocking asyncio daemon `orchestrator.coordination.daemon`:

  ```python
  async def run_coordination_daemon(
      bus: GossipBus,
      sweep_interval_sec: float = 30.0,
      stale_threshold_sec: float = 300.0
  ):
      while True:
          await heartbeat_cleanup(bus, stale_threshold_sec=stale_threshold_sec)
          await asyncio.sleep(sweep_interval_sec)
  ```

* Register daemon command: `python3 -m orchestrator.coordination.cli daemon start --sweep-interval 30`.

---

## 3. Concurrency & LAN Replication CI Pipeline

### GitHub Actions Workflow (`.github/workflows/coordination-ci.yml`)

Add a dedicated multi-worker stress test matrix:

1. **Contention Stress:** Run 10 parallel subagents attempting to claim the same queued
   task simultaneously; assert exactly 1 winner and 9 deterministic contention /
   lost-race codes (`LOST_RACE` vs `CONTENTION`).
2. **Replication Fidelity:** Validate GossipBus broadcast and tailing across mock
   network bridges with latency and packet-reordering fixtures.
3. **Reorder Buffer Drain Matrix:** Validate sequence numbers and out-of-order packet
   reconciliation up to $N=1000$ events.

---

## 4. Legacy API Deprecation & Clean Removal

### Target Files to Retire

* `scripts/agent_coordination_legacy.py`
* `scripts/agent_coordination_core.py` (replaced entirely by `orchestrator.coordination.*`)
* `scripts/agent_coordination_phases.py`

### Migration Strategy

1. Issue a `DeprecationWarning` on any direct invocation of legacy scripts.
2. Provide a shim in `scripts/agent_coordination.py` that delegates 100% of subcommands to `orchestrator.coordination.cli:main()`.
3. Verify zero external callers via `grep -rn "agent_coordination_legacy"` across all
   3 repositories before dropping files.

---

## 5. Privacy Boundary & Event Topology Opsec

### Problem

Event payloads currently capture absolute host paths via `current_worktree_label()`
(e.g., `$REPO_ROOT/...` under a real operator's home directory).

### Solution

1. Hash or tokenize the worktree path into an opaque identifier:

   ```python
   def get_portable_worktree_id(repo_root: Path, worktree_path: Path) -> str:
       # e.g., "pt:branch-fix-pt-standards-convergence:a1b2c3d4"
       rel = worktree_path.relative_to(repo_root.parent) if repo_root.parent in worktree_path.parents else worktree_path.name
       return f"{repo_root.name}:{worktree_path.name}:{hashlib.sha256(str(worktree_path).encode()).hexdigest()[:8]}"
   ```

2. Ensure no private workstation username or absolute directory structure enters the
   `gossip` table or `.agent` episodic memory rows.
