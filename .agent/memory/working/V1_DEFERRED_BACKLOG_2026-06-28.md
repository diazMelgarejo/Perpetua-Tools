# v1.1 deferred & archived backlog — collected 2026-06-28

**Source:** `orama-system/docs/plans/2026-05-29-03-v1.1-definitive.md` §9 Out of Scope + §7 Timeline gaps  
**Purpose:** Resume when coord cycles idle >15 min or operator unblocks

## Explicitly out of scope (v1.1)

| Item | Notes |
|------|-------|
| LanceDB migration | gbrain stays pgvector |
| MAESTRO / Human-in-Loop | post-v1.1 |
| Redis distributed PT | MVP uses `.state/agents.json` |
| Multi-tenant cost ledgers | single-operator LAN |
| Cross-machine LAN handoff | **partially done** via `lan_peer_assign` file inbox (v1.1 said OOS; shipped as coord overlay) |
| Win RTX 3080 dual-load | single-tenant LM Studio enforced |
| Native gbrain provider in CRG | CRG SQLite only |
| `.claude/agents/ultrathink-*.md` rename | low priority |

## P1 frugality router (not fully landed)

| Deliverable | Status |
|-------------|--------|
| `orchestrator/frugality_router.py` single chokepoint | **deferred** — doctrine in graceful-degradation ladders |
| G1 local-first ≥ 85% telemetry | measure post-coord |
| G2 skills auto-loaded ≤ 5 | partial (oramasys-method triggers) |
| `ORAMASYS_OFFLINE=1` tier ≥ 3 reject | verify in acceptance test |

## P2 OpenRouter pipelines

| Deliverable | Status |
|-------------|--------|
| `config/pipelines.yml` | **deferred** |
| `PIPELINE_TIERED_ENABLED=0` default | keep off until G1 baseline |
| Tier-5 governed spans | post-v1.1 |

## Co-orchestration overlay (shipped beyond v1.1 OOS)

| Capability | Artifact |
|------------|----------|
| Mac↔Win file inbox | `lan_peer_assign.py` |
| Sequential Win queues | `win_job_queue.py` |
| H5 cross-host benchmark | `run_h5_gpu_benchmark.py` |
| Graceful degradation SSOT | `graceful-degradation.md` Ladders A–F |

## Pending operator actions

1. **PR:** `subagent/win-coder/bridge-http-local` → PT `main` (`win-bridge-pr-ready.md`)
2. **PR:** `subagent/mac-researcher/h5-ollama-parallel` → orama `main` (optional)
3. **Mac peer:** restart portal if `probe_lan_peer` timeout (`PORTAL_BIND_LAN=1`)

## Resume trigger

When Win coder + autoresearcher queues idle >15 min with no new inbox cards: pick highest row from **Pending operator actions**, then P1 frugality_router spike.
