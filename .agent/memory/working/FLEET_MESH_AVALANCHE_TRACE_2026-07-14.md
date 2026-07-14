# Fleet Mesh Avalanche Trace

Date: 2026-07-14
Status: working memory / reboot-resume record

This note records fleet-mesh work that was already completed but easy to forget after a reboot or context reset. It complements `.agent/memory/working/FLEET_MESH_CROSS_REPO_INDEX_2026-07-14.md`.

## Root origin — Orama SOLO / PAIR / FLEET mother plan

The first explicit root found for this work is Orama commit:

- `84becc8` — `docs(plan): self-healing mesh with SOLO/PAIR/FLEET degradation modes`

Mother plan path:

- `orama-system/docs/plans/2026-07-08-self-healing-mesh-degradation-modes.md`

That plan introduced:

- `FleetMode` enum: `SOLO`, `PAIR`, `FLEET`
- `classify_fleet_mode()` pure function
- `fleet_topology.json`
- gossip relay
- `/api/fleet-topology`
- `/api/peer-relay-probe`
- coord-pulse extension
- banner/status integration
- self-healing propagation
- split-brain prevention
- five-phase implementation plan, roughly 25h

It defines the root problem: no fleet-level topology state, no SOLO/PAIR/FLEET classification, no gossip relay, and no self-healing propagation.

## PT implements Phase 2

The Orama mother plan produced PT Phase 2:

- `18caf28` — `feat(phase-2): FleetMode classifier + topology state management`

PT delivered:

- `FleetMode` enum
- `classify_fleet_mode()`
- `orchestrator/fleet_topology.py`
- `FleetTopologyState`
- hash-gated `fleet_topology.json`
- `docs/PHASE-2-SPEC.md`
- 16 Phase 2 tests, 36 total Phase 1+2 tests passing

PT's Phase 2 spec implements the FleetMode classifier and topology-state layer from the unified Orama plan.

## Orama integrates the timeline

Orama then added:

- `orama-system/docs/plans/2026-07-10-phase-integration-map.md`

That document ties together:

- PT Phase 1.0–1.3
- Phase 2 FleetMode
- Phase 3 Fleet Topology API
- Phase 4 coord pulse
- Phase 5 banner
- Phase 6 self-healing mesh

It names the original self-healing plan as the Phase 2–6 architecture source.

## Phase 5–6 lands

Orama implemented Phase 5 and Phase 6 in:

- `21ff103` — `feat(phase-5-6): banner display + self-healing mesh (54/54 tests passing)`

Delivered:

- Phase 5 banner display
- `--fleet-status`
- Phase 6 stale detection
- auto-recovery
- split-brain resolution
- 54/54 tests passing

Completed report:

- `orama-system/PHASE-6-IMPLEMENTATION.md`

That file is completed evidence, not the root plan. It leaves the next-step clue:

1. Phase 7 — quorum consensus for 3+ nodes
2. Phase 8 — recovery orchestration notifications and thresholds
3. Phase 9 — topology learning with adaptive jitter-aware grace periods
4. Phase 10+ — trust hardening, verification, witness recovery, and GossipMesh direction

## G7 / Phase 7 notification-awareness branch

The G7 docs are Phase-7-adjacent, not random. Once stale/recovered/split-brain events exist, the operator/control plane needs push awareness instead of polling.

Relevant active docs:

- `orama-system/docs/G7-ASYNC-NOTIFICATIONS-ANALYSIS.md`
- `orama-system/docs/2026-07-14-g7-async-notifications-next-steps.md`

The G7 analysis describes the gap as push notification for agents/operators without polling and recommends a Portal Notification Hub. The next-steps file preserves this as unfinished implementation work.

## Phase 10+ points to GossipMesh / Byzantine direction

The Phase 10+ clue points toward trust, verification, witness-based recovery, and anti-Byzantine behavior.

Nearby companion doc:

- `orama-system/docs/v2/43-gossipbus-mesh-transport.md`

That document defines future mesh gossip as interest-filtered, redacted, append-only GossipBus deltas, not full DB replication. This matches the Phase 10+ hardening direction.

## Better consolidation model

Do not treat `PHASE-6-IMPLEMENTATION.md` as the root. It is a completed milestone report.

Intended documentation model:

```text
docs/next/fleet-mesh/
  README.md
  2026-07-08-self-healing-mesh-degradation-modes.md
  2026-07-10-phase-integration-map.md
  2026-07-10-oasn-p2p-architecture-research.md
  G7-ASYNC-NOTIFICATIONS-ANALYSIS.md
  2026-07-14-g7-async-notifications-next-steps.md
  phase-7-to-10-roadmap.md

docs/archive/fleet-mesh/
  README.md
  PHASE-6-IMPLEMENTATION.md
  2026-07-10-pr2-phase0-review-crossreference.md
```

Active folder gets the original SOLO/PAIR/FLEET plan. Archive gets completed reports and historical ledgers.

## Avalanche chain

```text
SOLO / PAIR / FLEET plan
  -> PT Phase 2 FleetMode + fleet_topology.py
  -> Orama Phase Integration Map
  -> Orama Phase 3/4/5/6 implementation
  -> PHASE-6-IMPLEMENTATION.md completed report
  -> Phase 7-10+ next-step clue
     -> Phase 7 / G7 async notifications
     -> Phase 8 recovery orchestration
     -> Phase 9 topology learning
     -> Phase 10+ Byzantine / GossipMesh / witness recovery
```

## Orama-system changes already done on main

- `docs/next/fleet-mesh/README.md`
  - Commit: `3ef0bbf`
  - Purpose: active fleet-mesh index; makes the SOLO / PAIR / FLEET plan the mother plan.

- `docs/archive/fleet-mesh/README.md`
  - Commit: `72dbb59`
  - Purpose: archive index; treats `PHASE-6-IMPLEMENTATION.md` as completed report.

- `docs/next/fleet-mesh/phase-7-to-10-roadmap.md`
  - Commit: `5efe356`
  - Purpose: active Phase 7-10+ roadmap derived from the Phase 6 next-step clue.

- `bin/orama-system/references/branch-local-pattern-remediation.md`
  - Commit: `ae42d20`
  - Purpose: reusable branch-local CodeRabbit remediation discipline card.

- `bin/orama-system/references/review-remediation-crosslinks.md`
  - Commit: `43a3cde`
  - Purpose: crosslink index for skills that should refer to the remediation card.

## PT change already done

Initial PT pointer:

- `dbb0671` — `memory(fleet-mesh): record Orama active/archive indexes`
- Path: `.agent/memory/working/FLEET_MESH_CROSS_REPO_INDEX_2026-07-14.md`

This file adds the full avalanche trace because the initial pointer was too short.

## Future navigation rule

When resuming SOLO / PAIR / FLEET, Phase 7/G7, Phase 8, Phase 9, or Phase 10+ work:

1. Start from `orama-system/docs/next/fleet-mesh/README.md`.
2. Check `orama-system/docs/next/fleet-mesh/phase-7-to-10-roadmap.md` for the active continuation.
3. Treat `orama-system/PHASE-6-IMPLEMENTATION.md` as completed evidence.
4. Use `orama-system/docs/archive/fleet-mesh/README.md` only for historical provenance.
5. Cross-check PT implementation status in `orchestrator/fleet_topology.py`, `docs/PHASE-2-SPEC.md`, heartbeat/liveness primitives, and Phase 0/1/2 swarm-security docs.

## Git-mv limitation

The prior connector pass added canonical active/archive indexes without physically moving legacy source files because the available connector path could not perform a true local `git mv`, and the container could not clone GitHub due DNS resolution failure.

A destructive delete/recreate move would make history worse. If physical relocation is still desired, use a real local checkout and perform `git mv` so history is preserved.

## Why this memory exists

This note prevents future agents from:

- starting from completed `PHASE-6-IMPLEMENTATION.md` as if it were the root plan;
- overlooking the `84becc8` SOLO/PAIR/FLEET mother plan;
- treating G7 async notifications as unrelated to Phase 7;
- missing the Phase 10+ GossipMesh/Byzantine lineage;
- redoing active/archive index work already committed on Orama main;
- attempting destructive connector-based moves instead of true local `git mv` relocation.
