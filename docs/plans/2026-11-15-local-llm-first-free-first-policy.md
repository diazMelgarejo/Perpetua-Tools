# PLAN: Local-LLM-first runtime + free-first financial policy

**Date:** 2026-11-15
**Status:** **unimplemented** (design artifact only; no selector, no JSON policy file, no dispatch change)
**Policy ID:** `local-llm-first-free-first-2026-11-15-v0`
**Does not replace:** [bigmodel-free-first-2026-11-13-v1](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-11-13-bigmodel-free-first-plan.md)

A named policy is not a live gate. Do not treat this file, or
`config/bigmodel-free-first-policy.json`, as implemented until a versioned
artifact exists, is consumed by `consult_gate()` / `resolve_route()`, and
has tests that fail closed in `free_only`.

---

## Cross-links (GitHub)

### Free-first (financial; still proposed)

| Role | Link |
| ---- | ---- |
| Orama SSoT: candidate order, `free_only`, 1113 vs throttle, paid gate, state machine | [orama-system `docs/plans/2026-11-13-bigmodel-free-first-plan.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-11-13-bigmodel-free-first-plan.md) |
| PT companion: ownership checklist, not a second candidate list | [Perpetua-Tools `docs/plans/2026-11-13-bigmodel-free-first-companion-plan.md`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/docs/plans/2026-11-13-bigmodel-free-first-companion-plan.md) |
| Snapshot PRs named in those plans (not runtime policy) | [orama #493](https://github.com/diazMelgarejo/orama-system/pull/493) · [PT #497](https://github.com/diazMelgarejo/Perpetua-Tools/pull/497) |

### Local-LLM-first / frugality (specified; wiring incomplete)

| Role | Link |
| ---- | ---- |
| Tier 0–6 ladder, `ORAMASYS_OFFLINE`, privacy ceiling | [orama `docs/plans/2026-05-29-03-v1.1-definitive.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-05-29-03-v1.1-definitive.md) §2 and §4 |
| Router that encodes those tiers | [`orchestrator/frugality_router.py`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/orchestrator/frugality_router.py) |
| Canonical pre-dispatch gate (2026-07-22) | [`orchestrator/gate.py`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/orchestrator/gate.py) |
| Inference + LAN fallback ladders | [orama `graceful-degradation.md`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/oramasys-method/references/graceful-degradation.md) |
| Search/code cheapest-first chain | [orama `search-and-code-exploration-policy.md`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/references/search-and-code-exploration-policy.md) |
| PT pointer to those ladders | [`.agent/memory/working/GRACEFUL_DEGRADATION_LAN_2026-06-28.md`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/.agent/memory/working/GRACEFUL_DEGRADATION_LAN_2026-06-28.md) |

### Hardware / local models (fail-closed)

| Role | Link |
| ---- | ---- |
| Architecture SSoT; Mac Ollama + Win LM Studio hard requirements | [orama `2026-05-14--UNIFIED-ABSORPTION-PLAN.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md) §1–2, §5.3 |
| Live Mac/Win lists (`qwen3.5:9b-mlx` replaced retired `nvfp4`) | [`config/model_hardware_policy.yml`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/config/model_hardware_policy.yml) |
| Selection order; ladder must not be reordered by harness pins | [`SKILL.md`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/SKILL.md) |
| Governance pin does **not** reorder the ladder | [`docs/standards/model-governance.md`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/docs/standards/model-governance.md) |
| Sister pin | [orama `docs/standards/model-governance.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/standards/model-governance.md) |
| Upstream (cite; do not copy model ids) | [alexandria `model-governance.md`](https://github.com/oramasys/alexandria/blob/docs/mig-pack-ingest-20260925/docs/standards/model-governance.md) |

When citing Unified Plan §5.3, the Mac id `qwen3.5:9b-nvfp4` is retired. Use
[`config/model_hardware_policy.yml`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/config/model_hardware_policy.yml).

### Memory / decisions (history, not a live selector)

| Claim | Link |
| ----- | ---- |
| Router was a separate unwired spike (`lesson_ce9e6af5200b`) | [`.agent/memory/semantic/LESSONS.md`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/.agent/memory/semantic/LESSONS.md) |
| `resolve_route()` is the gate; human override, never silent (`lesson_fe447a995aed`) | same |
| Cloud default-deny; ladder not reordered | [`docs/LESSONS.md`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/docs/LESSONS.md) (2026-10-03) |
| Local-first by contract | [`docs/2026-06-22-oramasys-v2-intent-and-interpretation-gap.md`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/docs/2026-06-22-oramasys-v2-intent-and-interpretation-gap.md) §4.3 |
| Frugality + SSRF convergence (aspirational paid-tier table) | [`.agent/memory/working/UNIFIED_STANDARDS_SSRF_FRUGALITY_CONVERGENCE_2026-08-20.md`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/.agent/memory/working/UNIFIED_STANDARDS_SSRF_FRUGALITY_CONVERGENCE_2026-08-20.md) |

---

## Two stacked policies (do not conflate)

```text
1. Local-LLM-first   (runtime / hardware)   — PT owns
2. Free-first        (financial / remote)   — unimplemented until JSON + selector exist
3. Paid last resort  (HITL + finite budget) — blocked without per-run authorization
```

Local success **stops the chain**. Free remote is not a substitute for a missing
Mac Ollama or Win LM Studio probe. Paid never preserves availability.

Default remote financial mode in the 2026-11-13 plan is `free_only`: the
complete eligible free list may end in a **safe failure**. Reliability targets
do not override the money boundary.

---

## Local-LLM-first (what “implemented” would mean)

Already specified:

- Tiers 0–2 first: in-context → local OSS (Ollama / LM Studio) → local indexes
  ([v1.1 definitive §2](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-05-29-03-v1.1-definitive.md)).
- `ORAMASYS_OFFLINE=1` rejects tier ≥ 3.
- `privacy_critical` forbids tier ≥ 4.
- Win coder pool before Mac-local for coder roles ([Unified Plan §5.3](https://github.com/diazMelgarejo/orama-system/blob/main/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md);
  [graceful-degradation B1](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/oramasys-method/references/graceful-degradation.md)).
- Startup fail-closed if Mac lacks Ollama `qwen3.5:9b-mlx` + `bge-m3`, or Win
  lacks `LM_STUDIO_WIN_ENDPOINTS`.
- Hardware affinity never silently cross-hosts MLX onto Win or 27B CUDA onto Mac.
- [`gate.py`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/orchestrator/gate.py)
  must not invent policy: missing `frugality_tier` + no registry is **no opinion**,
  which is why local-first is not yet universal.

Gaps to close (implementation, not this docs patch):

1. Classify every dispatchable model in `config/models.yml` with `frugality_tier`
   so the gate cannot fall through.
2. Make `route_task()` / `/orchestrate` / CLI workers **refuse** “no opinion”
   in production (keep tests for the historical fall-through).
3. Probe live `/api/tags` and `/v1/models` before picking a local id; never
   hardcode names in production paths ([`SKILL.md`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/SKILL.md)).
4. Treat `glm-5.3-flash:cloud` on Mac as **not** local-LLM-first until it is
   either a verified local Ollama tag or an explicit free/paid remote candidate.
5. Escalate past the default ceiling only after human confirmation
   (`AskUserQuestion` / CLI modal), never a config flag
   (`lesson_fe447a995aed`).
6. Keep Alexandria / harness pins from reordering this ladder
   ([model-governance](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/docs/standards/model-governance.md)).

---

## Free-first (crafted from stated goals; remains unimplemented)

Until `config/bigmodel-free-first-policy.json` exists and is tested, **label
every free-first claim unimplemented**. The following is the policy text to
implement, not a claim that it runs.

**Owner:** PT owns the versioned JSON + pure selector API. Orama consumes
policy id/hash one-way. No PT → orama import
([companion § PT ownership](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/docs/plans/2026-11-13-bigmodel-free-first-companion-plan.md);
[orama plan §7](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-11-13-bigmodel-free-first-plan.md)).

**Mode:** `free_only` by default. Exhaust **allowlisted eligible** free
candidates for this task and lane, not “every model that returned non-200”.

**Proposed text/coding order** (qualify before promotion; vision is a separate list):

1. `glm-4.7-flash` — primary coding/text (source-supported; execution unqualified)
2. `glm-4.5-flash` — secondary (terms/tools pending)
3. `glm-4-flash-250414` — basic text (capability tests pending)
4. `glm-5.3-flash` — **paid last resort**, blocked without per-run budget + HITL

Never treat `glm-z1-flash`, FlashX, or generic `glm-4.7` as free replacements.
Zero listed input/output price ≠ account eligibility, cache storage, or
concurrency. Unknown price is never zero.

**Identity:** free/paid is pinned to exact scheme + host + API path + model id.
Unrecognized endpoint overrides fail closed (reuse
[`endpoint_policy_core`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/src/utils/endpoint_policy_core.py);
do not add a second URL parser).

**Errors:** HTTP 429 with structured code `1113` is
`billing_or_entitlement_blocked` — no generic retry, no recharge, no paid
escalation. Timeouts, partial streams, and tool side effects are
`outcome_unknown` / `recovery_required`, not free exhaustion. Do not rotate
accounts to evade throttle or safety.

**Paid gate (all required):** explicit per-run authorization; finite positive
budget + token/request limits; complete free-candidate ledger; resolved
entitlement; fresh rates; atomic reservation across workers. An env var or
profile switch is not authorization.

**Lanes stay independent:** PT SDK, Cline 3.0.74, ClinePass, W&B, OpenRouter,
and Coding Plan successes do not qualify each other.

**Reasoning:** never emit `max` or `xhigh`. Do not invent `medium` for models
that reject it.

---

## Next (after this document is on main)

These are queued work, not done by this patch:

1. Keep **free-first labeled unimplemented** in skills, SKILL.md, and PRs until
   the JSON artifact + tests exist.
2. Dedicated PT branch: `config/bigmodel-free-first-policy.json` +
   `select_next_candidate` / `classify_provider_result` as specified in orama
   plan §7; wire through `gate.py` without a second parser.
3. Dedicated PT branch: close local-LLM-first fall-through (`frugality_tier` on
   every model; production refuse of “no opinion”).
4. Orama lockstep: policy-backed Cline profile and runner after PT policy hash
   exists ([orama plan §8](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-11-13-bigmodel-free-first-plan.md)).
5. Offline fixtures: paid transport unreachable in `free_only`; 1113 ≠ throttle.
6. Do not expand [PT #497](https://github.com/diazMelgarejo/Perpetua-Tools/pull/497)
   or [orama #493](https://github.com/diazMelgarejo/orama-system/pull/493) with
   this work.

No runtime code, credentials, provider profiles, or paid inference are changed
by this file.

## Selector

`config/bigmodel-free-first-policy.json` and `orchestrator/policy_stacks.py`
implement the selector. `route_task` keeps the local chain, appends the
automatic free chain, and ends at `openrouter/free`. Tier 5 stays out unless
`paid_authorization` is a per-run human approval with a positive finite
budget. Qualification lanes stay blocked. Every `config/models.yml` model
now has a frugality tier, and `route_task` drops a model with no tier.
`consult_gate` still has no opinion for a missing tier so the oramasys hop
keeps its historical fall-through.
