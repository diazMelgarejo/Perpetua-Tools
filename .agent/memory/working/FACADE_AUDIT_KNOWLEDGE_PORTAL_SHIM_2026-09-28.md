# Perpetua Facade Audit day — Knowledge Portal shim (2026-09-28)

> **Repo:** `diazMelgarejo/Perpetua-Tools` only (V1).  
> **This memory PR:** [Perpetua-Tools #405](https://github.com/diazMelgarejo/Perpetua-Tools/pull/405) (`cursor/facade-audit-memory-2026-09-28-43fe`) — explicit Seth/user ask to record the day — **draft only**; do not merge without Seth.  
> **Facade/shim code PR:** none (CLEAN).  
> **Orama lock (do not touch):** [orama-system #368](https://github.com/diazMelgarejo/orama-system/pull/368) → cloud agent `bc-a3dd2228`.  
> **Related already on PT `main`:** gossip LAN mandate [#287](https://github.com/diazMelgarejo/Perpetua-Tools/pull/287) (`orchestrator/mesh_auth.py`, FastAPI `/gossip/emit` + `/gossip/tail`, `tests/test_mesh_auth.py`).

## Executive summary

Seth created bot **Perpetua Facade Audit** to audit facade gaps for Perpetua-Tools (`diazMelgarejo`) versus Orama’s read-only knowledge / swarm-approval facade. Soft-push a **draft** PR only when that facade needs a Perpetua-side contract, stub, or docs fix; otherwise **CLEAN + zero PRs**. Never merge without Seth. Coordinate with lane owners (V1 Housekeeping vs Oramasys Liaison).

Scope was then narrowed to **V1 only**: audit `diazMelgarejo/Perpetua-Tools`; do **not** touch `oramasys/perpetua-core`.

For the Knowledge Portal slice, PT is **not** an operational adapter owned by Perpetua. It is only a **compatibility shim** so the Orama web portal works when both packages are installed / both repos co-cloned. Do **not** build PT-owned knowledge/MCP/A2A runtime. Draft a PT PR only if a shim (missing export/hook/docs) is required for the portal to connect cleanly when co-installed.

This day: read-only facade audit **CLEAN**; Knowledge Portal shim re-audit **CLEAN**; no facade/shim soft-push. This note is the only PT delta requested.

## Timeline (2026-09-28, PHT)

| When (approx.) | Event |
|----------------|--------|
| Morning (Seth spawn) | Facade Audit assignment created: audit PT + (originally) perpetua-core facade gaps; draft only if needed; else CLEAN. |
| Scope change (Seth) | **V1 only** — Perpetua-Tools; perpetua-core out of scope. |
| Knowledge Portal clarification (Seth) | PT is a **compatibility shim**, not a PT-owned Knowledge Portal adapter/runtime. |
| Coordination | User asked Facade Audit to coordinate with V1 Housekeeping; **split confirmed**. |
| Standing rule (Seth, forever) | Share knowledge with peers; **one agent actively works a given PR**; first to touch wins; others stand down to re-review/babysit only — no competing cloud agents or parallel soft-push. Ownership ends on release or Seth reassign. Current lock: **orama-system #368 → `bc-a3dd2228`**. |
| Facade audit | CLEAN vs Orama knowledge/swarm-approval; zero PRs. |
| Shim re-audit | CLEAN again; Orama portal does not import/discover a PT Knowledge Portal export/hook/docs when co-installed. |
| Housekeeping | Recommended **idle** until a real shim gap; no speculative docs stub. |
| Memory capture | This working-memory note + **draft** PT PR only (explicit ask). |

## Jobs done by Perpetua Facade Audit (this bot)

- Read-only facade audit of Perpetua-Tools vs Orama knowledge/swarm-approval: **CLEAN**, zero PRs.
- Evidence: PT #287 gossip LAN mandate already on `main` (`orchestrator/mesh_auth.py`, `fastapi_app` `/gossip/emit` + `/gossip/tail`, `tests/test_mesh_auth.py`). Swarm HITL (`preview_id` / `approval_token`) correctly **Orama-owned** (`portal_server` / `swarm_approval.py`); plan text said no PT change if the orama gate is authoritative.
- Knowledge Portal shim re-audit under Seth’s clarification: **CLEAN** again. Orama portal does not import/discover any PT Knowledge Portal export/hook/docs when co-installed (`web/` has command-center + routing, swarm API — **no** `/api/knowledge`). Operational co-install bridges (`PERPETUA_TOOLS_ROOT`, jobs proxy, `hardware_policy`, alphaclaw affinity optional imports) are **out of Knowledge-Portal scope**.
- Recommendation to V1 Housekeeping: stay **idle** until a real shim gap; no speculative docs stub.
- Orama doc nit noted but **not** fixed here: ladder acceptance text says `POST /v1/gossip/*` → 401; live PT is `/gossip/*` → 503/403. Orama-owned; do not edit orama-system in this PR (and #368 is locked to another agent).

**Not claimed:** no runtime, orchestrator, packages, tests, or OpenAPI changes; no PT knowledge/MCP/A2A runtime; no orama-system or perpetua-core implementation.

## Jobs done by peer agents (cross-bot continuity)

| Agent | Role | What they did today (this slice) |
|-------|------|----------------------------------|
| Seth (bot id `bd4562e4-…`) | CoS / coordinator | Created Facade Audit assignment; V1-only scope; Knowledge Portal shim clarification; standing one-PR-owner rule; relayed CLEAN to user |
| V1 Housekeeping (`a9bb57e4-…`) | `diazMelgarejo` v1 housecleaning lane | Confirmed task split; residual housecleaning + orama-system portal lane; asked seamless-co-install question; relayed idle recommendation; FYI’d orama-system #368 |
| Cloud agent `bc-a3dd2228` | orama-system Knowledge Portal track | Open draft https://github.com/diazMelgarejo/orama-system/pull/368 tip ~`9f9dd5a`; agent report: no Perpetua changes; **owns #368** under PR lock |
| V1 Portal Knowledge (`02ceaa31-…`) | orama-system Knowledge Portal end-user slice | Named as portal lane collaborator; **not** the PT shim owner |
| Oramasys Liaison / perpetua-core | v2 constellation | Explicitly **out of scope** for this V1-only day |

## Confirmed split

- **Perpetua Facade Audit:** shim-gap gate only on Perpetua-Tools. Soft-push draft only if a real gap; else CLEAN + zero PRs. No PT knowledge/MCP/A2A runtime; no orama-system or perpetua-core implementation.
- **V1 Housekeeping:** residual v1 housecleaning; orama-system Knowledge Portal lane (watching #368 / V1 Portal Knowledge).

## Standing PR ownership rule (2026-09-28, forever)

Share knowledge with peers. Only **one** agent actively works a given PR. First to touch wins. Others stand down to re-review/babysit only — no competing cloud agents or parallel soft-push. Ownership ends on **release** or **Seth reassign**.

- Current lock: **orama-system #368 → `bc-a3dd2228`**.
- This PT memory PR: Facade Audit owns it alone under the standing rule.

## Verdicts

| Check | Result |
|-------|--------|
| Facade audit | **CLEAN** |
| Knowledge Portal shim re-check | **CLEAN** |
| Soft-push for facade/shim code | **none** |
| This memory PR | **explicit Seth/user ask** — draft only; Facade Audit owns this PT PR alone |

## Open / idle

- [ ] Idle on PT shim until orama-system #368 or V1 Portal Knowledge lands a **concrete** PT import/hook contract.
- [ ] Do not touch orama-system #368.
- [ ] No merge of this memory PR without Seth.
- [ ] Orama ladder acceptance nit (`POST /v1/gossip/*` → 401 vs live PT `/gossip/*` → 503/403) remains orama-owned; not fixed here.

## Related PT memory

| Doc | Topic |
|-----|-------|
| `MESH_SECURITY_MIGRATION_2026-07-26.md` | PT #287 gossip LAN mandate already on `main` (evidence for CLEAN gossip facade) |
| `WORKSPACE.md` | Live task board (not rewritten this day; no working-memory README index) |

## Recall

```bash
python .agent/tools/recall.py "Perpetua Facade Audit Knowledge Portal shim 2026-09-28"
python .agent/tools/recall.py "orama-system 368 PR ownership lock bc-a3dd2228"
python .agent/tools/recall.py "PT gossip LAN mandate mesh_auth CLEAN facade"
```

**Recall hints:** Facade Audit · Knowledge Portal shim · not PT-owned adapter · CLEAN · V1 Housekeeping idle · Seth one-PR-owner · orama-system #368 · `bc-a3dd2228` · no `/api/knowledge` · `preview_id` / `approval_token` Orama HITL · `/gossip/*` 503/403 vs documented `/v1/gossip/*` 401.
