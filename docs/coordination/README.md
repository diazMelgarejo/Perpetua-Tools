# Coordination module — docs hub

> **Not STM Phase 0.** This folder covers **`agent_coordination.py`** and
> `orchestrator/coordination/*`. For PeerObservation / STM / threat T1–T7, see
> [`../phase-0-specifications/README.md`](../phase-0-specifications/README.md).

**Terminology:** [`PHASE-0-TERMINOLOGY-DISAMBIGUATION.md`](PHASE-0-TERMINOLOGY-DISAMBIGUATION.md)
— canonical “Phase 0” vs “Phase 0F” guide (link this whenever naming is ambiguous).

---

## What lives here

| Doc | Role |
| --- | --- |
| [`PHASE-0-TERMINOLOGY-DISAMBIGUATION.md`](PHASE-0-TERMINOLOGY-DISAMBIGUATION.md) | **Canonical** — STM Phase 0 ≠ coordination Phase 0F |
| [`../next/2026-07-17-coordination-module-consolidation-plan.md`](../next/2026-07-17-coordination-module-consolidation-plan.md) | Mother plan (Parts 1–3, migration ladder) |
| [`../references/coordination-consolidation-plan-review-2026-07-18.md`](../references/coordination-consolidation-plan-review-2026-07-18.md) | Codex review — **in-repo** evidence (supersedes off-repo handoffs) |
| [`../next/2026-07-27-coordination-phase-0f-part2-autoplan.plan.md`](../next/2026-07-27-coordination-phase-0f-part2-autoplan.plan.md) | **Autoplan intake** — 0F completion + `liveness.py` |

---

## Coordination Phase 0F (CLI contract freeze)

**Goal:** Freeze the executable CLI contract (29 parser leaves) before further
extraction into `orchestrator/coordination/`.

| Item | Status on `main` |
| --- | --- |
| `tests/test_agent_coordination_cli_contract.py` | **DONE** — 29 leaves, arg contract, handler dispatch |
| `orchestrator/coordination/cli.py` `build_parser()` | **DONE** — separated for contract freeze |
| Live provenance re-verify vs handlers | **OPEN** |
| Bus constructor inventory (`GossipBus` vs `make_gossip_bus`) | **OPEN** |
| State/side-effect characterization (cleanup, races) | **OPEN** |

```bash
pytest tests/test_agent_coordination_cli_contract.py -q
```

---

## Part 2 (extraction — in progress)

| Module | Status |
| --- | --- |
| `paths.py`, `claims.py`, `types.py`, `reorder_buffer.py`, `task_queue.py`, `phases.py` | **DONE** on `main` |
| `liveness.py` (heartbeat handlers) | **TODO** — see autoplan |
| Compat wrapper deletion (`agent_coordination_core.py` etc.) | **Gated** — after parity tests |
| `phases.py` standalone `GossipBus` vs `make_gossip_bus` LAN gap | **TODO** |

---

## Validated handoffs (v1)

New standard dispatches can use a typed JSON packet before queue admission:

```bash
python scripts/agent_coordination.py handoff validate handoff.json
python scripts/agent_coordination.py queue add <task> <phase> --handoff handoff.json
```

The packet is validated before any queue mutation; accepted packets record a
non-liveness `handoff_admitted` audit event. Read
[the template](agent-handoff-template.md) and start from
[the executable example](examples/handoff-packet-v1.json).

`log()` remains a board-status message, not a heartbeat. A long-running worker
must emit its own `heartbeat pulse <agent-id>` periodically; queue admission
and later logs never keep a dead or stalled worker falsely ACTIVE.

The optional v1 `monitorability` envelope is privacy-redacted and contains only
typed evidence metadata plus a caller-reported advisory state. Its full Phylax
v2 migration, derived-inference boundary, and assurance gates are governed by
[the three-part Orama reference plan](https://github.com/diazMelgarejo/orama-system/tree/main/docs/v2/references).

---

## Cross-links

- STM / swarm security graph:
  [`../phase-0-specifications/README.md`](../phase-0-specifications/README.md)
- Pre-v2 master checklist (both domains):
  [`../phase-0-specifications/PHASE-0-MASTER-PLAN-2026-07-27.md`](../phase-0-specifications/PHASE-0-MASTER-PLAN-2026-07-27.md)
- Multi-agent wiki:
  [`../wiki/07-multi-agent-collab.md`](../wiki/07-multi-agent-collab.md)
