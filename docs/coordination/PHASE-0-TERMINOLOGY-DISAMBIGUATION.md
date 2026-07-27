# Phase 0 terminology — disambiguation (canonical)

Two different programs use “Phase 0” naming in Perpetua-Tools. They are **not**
the same workstream. Link here whenever a doc says “Phase 0” without a folder
path.

---

## Quick rule

| If you see… | It means… |
| --- | --- |
| **Phase 0** (no letter) + `phase-0-specifications/` | **STM / swarm security** — PeerObservation, STM, T1–T7, mesh *evidence* |
| **Phase 0F** | **Coordination CLI freeze** — lock `agent_coordination.py`’s 29 commands before more extraction |

**`0F` = “freeze”** inside the *coordination consolidation* migration ladder
(0F → Part 1 → Part 2…). It is **not** “Phase 0 subsection F” of the STM
graph.

---

## 1. STM / swarm Phase 0 (security graph)

| | |
| --- | --- |
| **Question** | How do peer observations, liveness, replay, quorum, and threats become one decision boundary? |
| **Canonical home** | [`../phase-0-specifications/README.md`](../phase-0-specifications/README.md) + [`../phase-0-specifications/wiki/`](../phase-0-specifications/wiki/) |
| **Master checklist** | [`../phase-0-specifications/PHASE-0-MASTER-PLAN-2026-07-27.md`](../phase-0-specifications/PHASE-0-MASTER-PLAN-2026-07-27.md) |
| **Runtime** | `orchestrator/state_transition_manager.py`, `membership.py` (tested; **dormant in production** per descope) |
| **“Phase 1 / 2” here** | STM integration phases (1.0–1.3, job board) — **security/STM**, not coordination |
| **Orama tie-in** | D23 descope, mesh finality, fleet-mesh security companions |

Use when discussing: T1–T7, `evaluate_observation()`, descope of P5/P6/P13,
PR #203/#205, swarm security analysis.

---

## 2. Coordination Phase 0F (CLI contract freeze)

| | |
| --- | --- |
| **Question** | What is the live CLI/parser/dispatch contract before more code moves into `orchestrator/coordination/`? |
| **Canonical home** | [`README.md`](README.md) (this folder) |
| **Mother plan** | [`../next/2026-07-17-coordination-module-consolidation-plan.md`](../next/2026-07-17-coordination-module-consolidation-plan.md) |
| **Review (in-repo)** | [`../references/coordination-consolidation-plan-review-2026-07-18.md`](../references/coordination-consolidation-plan-review-2026-07-18.md) — supersedes off-repo handoff copies |
| **Runtime** | `orchestrator/coordination/cli.py`, `scripts/agent_coordination.py` |
| **0F artifact** | `tests/test_agent_coordination_cli_contract.py` (29 leaves + handler dispatch) |
| **Part 2 after 0F** | `liveness.py` extraction, module split completion, compat deletion gate |

Use when discussing: queue claim races, heartbeat handlers, `make_gossip_bus` vs
`GossipBus`, provenance table, “freeze 29 CLI leaves.”

---

## Side-by-side

```text
STM Phase 0 (security)              Coordination Phase 0F (CLI freeze)
─────────────────────              ─────────────────────────────────
PeerObservation / STM              agent_coordination 29 commands
Threat T1–T7                       Parser + dispatch contract
docs/phase-0-specifications/       docs/coordination/
DORMANT BFT in prod                 Part 2: liveness.py extraction
Mesh P5/P6 (orama runtime)         ≠ STM P5/P6 (dormant on PT)
```

**Mesh P5/P6** (swarm approval, discovery trust on orama) and **STM P5/P6/P13**
(witness/reputation on PT) share pattern names but live in different repos and
layers.

---

## Other “Phase 0” strings (third context)

| Term | Domain |
| --- | --- |
| **gbrain CRG Phase 0–1** | Code-review-graph indexing — unrelated |
| **Coordination “Phase 1” skeleton** | `orchestrator/coordination/` package layout — coordination ladder, not STM Phase 1 |
| **Fleet Phase 7–10+** | GossipBus / G7 — separate numbering line |

When a doc says “Phase 0” without a path, check the **folder**
(`phase-0-specifications` vs `coordination` vs `fleet-mesh`) or the letter **F**
(`0F`).

---

## Doc naming convention

| Avoid | Prefer |
| --- | --- |
| “Phase 0” alone | **STM Phase 0** or **coordination Phase 0F** |
| “Phase 0F” in STM docs | Never — keep STM graph free of 0F |
| “Phase 0 master plan” for coordination | **Coordination CLI contract (Phase 0F)** |
