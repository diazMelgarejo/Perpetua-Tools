# Remediation Plan: STM Production Wiring + Threat-Model Premise Re-Check

**Source:** resumed Claude subagent `aac123e82eb006ede` (the same voice as `docs/phase-0-specifications/2026-07-12-ceo-review-quad-voices/03-claude-resumed-original.md`), asked for a concrete remediation plan (not another review) following the CEO quad-review's P5/P6/P13 gate. Tracked as a separate thread from `/autoplan`, run in parallel per user instruction, 2026-07-12.

**Headline correction — read this before anything else:** the integration plan's own §2d hedge, and all four CEO review voices that repeated it, named `orchestrator/agent_tracker.py` / `orchestrator/heartbeat_monitor.py` as the candidate wiring targets for `evaluate_observation()`. **This agent read both files and confirmed the guess is wrong** — those modules operate on a completely different data model (`AgentRecord` / raw `GossipBus` dicts for Claude sub-agent process lifecycle), not `PeerObservation` (backend reachability). Worse: a full grep of every production importer of `orchestrator.membership` found **no production code anywhere in this repo currently constructs a `PeerObservation` at all** — the gap is larger than "STM has no caller," it's "the schema has no producer." This supersedes the wiring guess in `docs/phase-0-specifications/2026-07-11-state-transition-manager-integration-plan.md`'s §2d and Related section.

---

## 1. The real call site

The actual live, currently-executing reachability-check path, bypassing `PeerObservation`/`PeerRecord`/`monotonic_gate.py`/`StateTransitionManager` entirely:

```
orchestrator/fastapi_app.py:395-420   GET /health route
  → backend_health_map(ollama_host, lm_studio_host, mlx_host)
orchestrator/connectivity.py:130-143  backend_health_map()
  → check_ollama() / check_lm_studio() / check_mlx() / check_perplexity() / check_openrouter() / check_anthropic()
orchestrator/connectivity.py:9-14     _probe(url) -> {"ok": bool, "status_code": int|None, "url": str, "error"?: str}
```

**Minimal wiring task:** in `backend_health_map()` (`orchestrator/connectivity.py:130`), after each `_probe()` result, construct a `PeerObservation`, call `await state_transition_manager.evaluate_observation(obs, old_status=...)`, and merge `result.accepted`/`result.decision_type` into the existing `/health` response shape. The `StateTransitionManager` instance already exists at `src/perpetua_tools/orchestrator.py:123` — a *second, distinct* FastAPI app from `orchestrator/fastapi_app.py`. **Flag this app-duplication as a side issue**: confirm whether `fastapi_app.py` and `src/perpetua_tools/orchestrator.py` are the same deployed service or two parallel apps before deciding which owns the STM instance.

**Effort:** 3–5 hours (constructor call, relocate/share the STM instance, consume `.flushed` in the response payload so P9 isn't dead-on-arrival again, 2-3 integration tests asserting an audit_log entry appended on `/health` hits).

---

## 2. Threat-model premise re-check — scoped task

Per `MULTIAGENT-SWARM-SECURITY-ANALYSIS.md:19-24`'s topology table (designed around Kademlia/PBFT/Bitcoin's adversarial-stranger assumptions) vs. the actual single-operator LAN. Concrete task: append a `## Addendum: Single-Operator LAN Premise Check (2026-07-12)` section (additive, not a rewrite) to `MULTIAGENT-SWARM-SECURITY-ANALYSIS.md` answering:

1. **Who are the actual "witnesses"?** `_probe()` shows the orchestrator directly probing its own endpoints — no second independent observer exists today. P5/P6/P13 all presume ≥2 independent witnesses. Does a second witness exist anywhere (orama-system L3 or AlphaClaw L1 independently probing and reporting in)? If not, these patterns have no data to operate on regardless of wiring.
2. **What is the actual trust boundary?** If the operator's own primary machine (Mac) is compromised, does a 2-node quorum with Win provide any real defense? Answer with actual current node count (not the 3–100 aspirational range) and a one-line verdict per P5/P6/P13: "real defense at current scale" vs. "negligible defense at current scale, revisit if/when Fleet Mode adds external tenants."
3. **What's the actual observed failure mode?** Classify real incidents from `docs/LESSONS.md` / operational history: network/DHCP/process-crash flakiness vs. anything resembling a malicious/forged observation. Decisive evidence if the count is zero adversarial incidents.

**Deliverable:** the addendum section above, with a revised trust-tier table (dated, sitting alongside the original), a per-pattern P5/P6/P13 verdict table (Needed-now / Needed-if-Fleet-Mode / Not-needed), and an explicit go/no-go recommendation: proceed with P5/P6/P13 as scoped, or descope to a simpler allowlist+mTLS model until Fleet Mode is real.

**Who:** swarm-topology/Fleet-Mode owner — a research-and-decide task, no code changes. **Effort:** 2–4 hours.

---

## 3. Sequencing and effort

| Step | Task | Depends on | Effort |
|---|---|---|---|
| 1 | Threat-model premise re-check (§2) | Nothing — no code dependency | 2–4 h |
| 2 | Decide: proceed with P5/P6/P13 wiring, or descope to allowlist+mTLS | Step 1's go/no-go verdict | 0 h (decision only) |
| 3a (if proceed) | Wire `evaluate_observation()` into `backend_health_map()` per §1 | Step 2 = proceed | 3–5 h |
| 3b (if proceed) | Resolve the two-FastAPI-app ambiguity | Step 2 = proceed | 1–2 h |
| 4 (if proceed) | Wire `.flushed` into `/health` response, add integration tests | Step 3a | 2–3 h |
| 3' (if descope) | Design allowlist+mTLS replacement, update GATE note | Step 2 = descope | not estimated |

**Recommended order:** run Step 1 first, alone — it's cheap, has no code dependency, and its answer changes whether Step 3 is worth doing at all. **Do not start wiring code before Step 1's verdict lands** — wiring a pipeline whose witness-quorum/reputation/equivocation gates have no real second witness to operate on risks building working code against a pipeline that structurally can't do anything useful yet.

**Total critical-path effort if "proceed":** ~1 day. **If "descope":** the wiring effort is deferred/avoided, replaced by a smaller allowlist+mTLS design task (not yet scoped).
