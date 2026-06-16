# ADR-002 — MultiLLMRouter: Caching/Batching Decorator over `_dispatch`

> **Status:** Proposed — gate doc. MUST be approved BEFORE any v2 runtime build (the live Fable 5 routing/caching/batching work in Perpetua-Tools).
> **Convention:** This repo uses `docs/adr/ADR-NNN-slug.md`. At time of writing the only existing ADR is [`ADR-001-three-repo-adapter-architecture.md`](ADR-001-three-repo-adapter-architecture.md); this doc is ADR-002. No flat `docs/v2/NN-` tree exists — earlier drafts referenced one in error.
> **Companions:** [`ADR-001-three-repo-adapter-architecture.md`](ADR-001-three-repo-adapter-architecture.md) (three-repo / L2-L3 adapter boundary, the layer rule this ADR inherits). The supervisor/Anthropic invariants this decorator depends on are sourced **directly from code** (`orchestrator/supervisor.py`), cited inline below, since no standalone "supervisor patterns" ADR exists in this repo yet. A future ADR may extract them; until it does, treat the code citations as authoritative.
> Added: 2026-06-15.

---

## 1 — Why this doc exists (Context)

The Fable 5 distill work has two halves with a hard seam between them.

- **v1 — DONE, offline.** `distill_session.py` runs offline, emits proposals, and performs **no Perpetua-Tools mutation**. It is methodology (L3): it adds no runtime state, cost, or dependency, and it shipped under the existing v1 CLI. v1 stays offline by design — this is the L3-stateless / L2-runtime boundary established in [`ADR-001`](ADR-001-three-repo-adapter-architecture.md).
- **v2 — NOT YET BUILT, live.** v2 needs **live frontier routing, caching, and batching** against cloud frontier models (Fable 5 / Opus 4.8 / GPT-5.5 / Grok / OpenRouter). This introduces runtime state (a cache), recurring cost (paid cloud calls), and a new dependency (`anthropic`). Per the v2 doctrine, **every v2 item that adds runtime state, cost, or a dependency needs an approved ADR before any code is written.** This is that ADR, and it is the gate.

`MultiLLMRouter` is **greenfield** — it does **not** exist today. There is no `multi_llm_router` module to "adapt"; the Grok / AntiGravity reference is exactly that — a reference, not a baseline. The danger this doc exists to prevent is the obvious-but-wrong move: writing a second router. The supervisor already routes (`worker_registry` + `model_registry` + `backend_resolver`). A parallel router would duplicate and drift from all of it.

This doc binds the shape of `MultiLLMRouter` before the first line is written, and locks decision **D17** centrally (see §10).

---

## 2 — The decision (Decorator over `_dispatch`, never a parallel router)

**Decision:** `MultiLLMRouter` is built as a **caching/batching decorator that wraps the existing dispatch seam** `OrchestrationSupervisor._dispatch` (`orchestrator/supervisor.py:534`). It is **never** a parallel router. (DRY / single-source-of-routing principle.)

The existing dispatch path already owns every routing concern, and the decorator MUST NOT re-implement any of them:

| Concern | Owned by | Decorator MUST NOT |
|---------|----------|--------------------|
| Backend selection / route order | `_dispatch` resolve chain (`supervisor.py:534`) | re-route, re-resolve, or add a second echo fallback |
| Model pinning + affinity-shaping of the spec | `_prepare_spec_for_inference` (`supervisor.py:722`; called on the dispatch path at `:616`, and for the Win leg at `:592`) | re-pin a model or re-shape the spec |
| Pure backend policy function + mirror exclusion (`_MIRROR_BACKENDS`) | `orchestrator/backend_resolver.py:24` (CLI path; caller `agent_launcher.py:611`) | import or duplicate it into the dispatch path |
| HTTP route-task entry | `ModelRegistry.route_task` (`model_registry.py:173`; HTTP `/orchestrate` only) | call it from the dispatch path |
| Windows pre-emption (probe, endpoint inject, `routed_to_windows`, lines 575–611) | `_dispatch` Win-preempt block | re-probe Windows or re-inject endpoints |

**What the decorator adds, and ONLY this:** a read-through cache check before delegating to the wrapped `_dispatch`, and (later, gated) request batching. On a cache miss it calls the real `_dispatch` unchanged and stores the successful result. The `JobSpec` contract (`prompt`, `backend_hint`, `constraints`, `metadata`, `role`, `depth`) and the `dict` return shape are preserved verbatim, so every existing caller (`_run_worker:384` ← `submit_job:268`) and the Win-preempt `routed_to_windows` marker keep working.

**Layer boundary (inherited from [`ADR-001`](ADR-001-three-repo-adapter-architecture.md)).** `MultiLLMRouter` and all caching/cost-guarding logic live in **Perpetua-Tools (L2 runtime) ONLY**. They **never** live in orama (L3 stateless methodology). Target package is the greenfield `perpetua.core.multi_llm_router` — a new v2 package, not an adaptation of anything existing. orama stays stateless: no cache, no Redis, no L2 state crosses the import boundary.

**Wrap the seam, not the workers.** The decorator wraps `_dispatch` — a single chokepoint — **not** the individual workers. This keeps it compatible with the supervisor invariants (see §6): the decorator sits above worker dispatch and inherits, rather than re-implements, depth/thread/affinity/audit semantics.

```python
# perpetua/core/multi_llm_router.py  (greenfield — illustrative shape, not final code)
class MultiLLMRouter:
    """Caching/batching DECORATOR over OrchestrationSupervisor._dispatch.
    NOT a router: it owns no route/affinity/Win-probe logic (DRY)."""

    def __init__(self, inner_dispatch, cache, cost_guard):
        self._inner = inner_dispatch    # bound OrchestrationSupervisor._dispatch.
        # _inner OWNS provider-client selection: the Anthropic leg INSIDE
        # _dispatch MUST use anthropic.AsyncAnthropic() + POST /v1/messages
        # (see §4). The decorator never instantiates an LLM client itself.
        self._cache = cache             # L2-only, TTL'd, redact-first, key-isolated
        self._cost_guard = cost_guard   # extends orchestrator/cost_guard.py (§5)

    async def __call__(self, spec) -> dict:
        # READ path: cacheable hit short-circuits BEFORE the cost gate (no spend).
        # NOTE: a cache hit still re-applies the SAME MAESTRO class gate as a miss
        # for Class 3/4 paths (see §6) — caching never skips a human gate.
        if self._is_cacheable(spec):           # deterministic request shape (§3)
            key = self._key(spec)              # key computed over POST-redaction form
            hit = self._cache.get(key)
            if hit is not None and self._class_gate_ok(spec):
                return hit
        # WRITE/cloud path: cost gate is default-deny + fail-closed (§5).
        # gate(spec) MUST RAISE on any deny OR any inability-to-evaluate.
        # ANY exception from the guard is treated as DENY (fail-closed) and is
        # NEVER swallowed; _inner is NOT called on the cloud leg unless gate()
        # returned normally.
        self._cost_guard.gate(spec)            # NEW method added in §5 extension;
                                               # wraps can_spend/record_spend, raises
                                               # BudgetExceededError/EscalationDeniedError
        result = await self._inner(spec)       # the REAL dispatch — unchanged
        if self._is_cacheable(spec) and self._succeeded(result):
            # redact -> canonicalize -> hash(key) -> store(redacted value) (§3)
            self._cache.set(self._key(spec), self._redacted(result))
        return result
```

---

## 3 — Cache correctness and safety (binding)

The cache is the new runtime state this ADR introduces, so its safety rules are binding, not advisory.

### 3.1 — Determinism gate (provider-aware, NOT `temperature`-anchored)

The cache stores a single sample as if it were canonical, so it may only do so when the request is **deterministic for the resolved provider**. Determinism is **provider-dependent**, and the gate must reflect that:

| Leg | Determinism gate |
|-----|------------------|
| **Anthropic (Fable 5 / Opus 4.8 / Sonnet)** | `temperature`/`top_p`/`top_k` **do not exist** on these models (sending `temperature` returns 400). Gate cacheability on a **deterministic request shape per resolved model** (e.g. no nondeterministic thinking/effort settings), never on `temperature == 0`. |
| OpenAI-compatible legs (OpenRouter / Grok / GPT-5.5) | `temperature == 0` is permitted as a *necessary-but-not-sufficient* signal, scoped to these legs only. |
| **All legs** | `temperature == 0` (where it exists) is **necessary-but-not-sufficient**. temp-0 does **not** guarantee determinism (no seed; MoE/batching nondeterminism; provider-side sampling floors). Cacheability is tied to **verified determinism**, via a **per-provider determinism flag** (and seed pinning where supported). Providers without a verified determinism flag are **non-cacheable** — or, if cached at all, only as best-effort dedupe under a **short TTL**, never as a correctness guarantee. |

### 3.2 — Cache-key correctness (full canonical request, not messages+model)

| Rule | Binding requirement |
|------|---------------------|
| **Key = full canonicalized request** | The key is `keyed_hash(` **canonical message-list + resolved model id + EVERY inference parameter that affects output** `)`. That parameter set explicitly includes: **system prompt, tools / tool definitions, tool_choice, response_format, max_tokens, stop sequences**, and (where they exist) **temperature, top_p, top_k, seed**. A change in *any* of these MUST **miss**, never collide. This closes the `role`-changes-system-prompt collision: in this codebase `JobSpec` carries `constraints`/`metadata`/`role`, and a `role` change alone can change the effective system prompt while leaving messages+model identical — that MUST produce a different key. |
| **Key-namespace** | Keys are namespaced by **model / tenant / session / backend** so entries cannot collide or leak across them. A Fable 5 result is never served for an Opus 4.8 key; one session's cache is never visible to another. |
| **Keyed/salted hash** | The key uses a **keyed (salted) hash**, not a bare digest of guessable content, so a low-entropy prompt cannot be reconstructed or guessed from the key. |

### 3.3 — Redaction pipeline order (binding)

The pipeline order is **binding and fixed**:

> **redact → canonicalize → hash(key) → store(redacted value)**

- Redact PII/secrets **first**, before the canonical form is computed.
- The key is computed over the **post-redaction canonical form**, so raw secrets never enter the keyspace.
- Only the **redacted** value is stored. **Output redaction** runs on the model response too (not just input), because model outputs can reproduce secrets present in the input even after input redaction.

### 3.4 — Substrate, at-rest, invalidation

| Rule | Binding requirement |
|------|---------------------|
| **Cache a successful, deterministic call only** | Cache **only** when the call passed the §3.1 determinism gate **and** succeeded. Never cache errors, partial/streamed-aborted results, or nondeterministic-provider results. |
| **Substrate named + scoped** | Default substrate is an **in-process LRU inside PT (L2)**. Any **persistent** substrate (on-disk or Redis) MUST: (a) be **PT-local and tenant-scoped**, (b) **encrypt values at rest** *or* store no value that can contain secrets, and (c) apply **output redaction**. **Redis is permitted in PT L2** only under that tenant isolation; it remains **forbidden in orama L3** (§8). |
| **TTL** | Every entry carries a TTL and is absent once expired. No unbounded-lifetime entries. Nondeterministic-provider dedupe (if enabled) uses a **short** TTL. |
| **Invalidation** | Explicit invalidation by **key**, by **model id** (a model-version bump must miss — the model id is in the key), and by **TTL**. **Plus a global / namespace-wide purge** and a **runtime feature-flag to disable caching entirely**, so a discovered **redaction or poisoning defect can be contained without a redeploy** (§7). |

This is the Helicone-style emulation locus (§9): a **hash-based LRU inside PT's `_dispatch` path**, never a separate proxy service, never a Langfuse-style trace tree promoted into runtime state.

---

## 4 — Provider matrix (Anthropic is NOT OpenAI-compatible)

The reference code routes everything through `AsyncOpenAI(base_url="https://api.anthropic.com")`. That is **wrong for Anthropic** and MUST be corrected before any v2 code. The provider-client selection lives **inside `_dispatch`** (`self._inner`), not in the decorator.

| Leg | Client | Endpoint | Notes |
|-----|--------|----------|-------|
| **Anthropic (Fable 5 / Opus / Sonnet)** | `anthropic.AsyncAnthropic()` | `POST /v1/messages` | **MUST** use the Anthropic SDK. The Anthropic API is `/v1/messages`, **not** `/v1/chat/completions`. Do **not** use `AsyncOpenAI` for this leg. `temperature`/`top_p`/`top_k` are **not** valid params on Fable 5 / Opus 4.8. |
| OpenRouter | OpenAI-compatible client | `POST /v1/chat/completions` | OpenAI-compatible path is acceptable. |
| Grok (xAI) | OpenAI-compatible client | `POST /v1/chat/completions` | OpenAI-compatible path is acceptable. |
| GPT-5.5 | OpenAI-compatible client | `POST /v1/chat/completions` | OpenAI-compatible path is acceptable. |

### Corrected model-ID table

Grok's reference contains model-ID errors. These MUST be corrected before any v2 code is written:

| Wrong (reference) | Correct (canonical) |
|-------------------|---------------------|
| `claude-4-sonnet-4.6` | `claude-sonnet-4-6` |
| `claude-fable-5-max` | `claude-fable-5` |
| `claude-opus-4.8` | `claude-opus-4-8` |

---

## 5 — Cost and budget (default-deny, fail-closed)

Cost/escalation routing rules and the Fable budget belong in **`orchestrator/cost_guard.py`** (extended, not forked), with `model_registry.py` dynamic thresholding as the locus for any dynamic thresholds (ClawRouter emulation, §9). The decorator calls the guard before delegating to `_dispatch`.

**Existing guard surface (verified).** Today `CostGuard` is HTTP-only (constructed in `fastapi_app.py:134`; the supervisor never imports it). API surface: `can_spend` (`cost_guard.py:66`), `record_spend` (`:74`), `snapshot` (`:80`), `set_budget` (`:87`). There is **no `gate()` method today** — it is the planned extension named below. The dispatch path has **no** cost-guard wiring today.

| Rule | Binding requirement |
|------|---------------------|
| **`gate(spec)` contract (NEW)** | This ADR adds `gate(spec)` to `cost_guard.py`. It **wraps** `can_spend`/`record_spend` and **MUST RAISE** a typed `BudgetExceededError` / `EscalationDeniedError` on **any deny** OR **any inability-to-evaluate**. It never returns a falsy "deny" signal that a caller could ignore. |
| **Fail-closed, no swallow** | The decorator **MUST NOT** call `_inner` on the cloud leg unless `gate()` returned normally. **Any exception from the cost guard is treated as deny (fail-closed) and never swallowed** — mirroring the affinity pattern (raise, no silent reroute). |
| **Default-deny cloud escalation** | Cloud (paid frontier) escalation is **default-deny**. A call only reaches a cloud provider when `gate()` explicitly permits it (returns normally). |
| **"4x Fable budget" gate fails closed** | When the budget ceiling is hit (or the guard cannot evaluate), `gate()` **raises** → the call is **blocked**. No silent reroute, no degraded best-effort spend. |
| **Keys via Keychain/.env, never config** | Provider API keys come from macOS Keychain or `.env` **only**. Keys are **never** committed to config files (`openclaw.json`, YAML, JSON) and never appear in tracked files. |
| **Thresholds added on first real call** | Fable 5 / Opus 4.8 / GPT-5.5 / Grok thresholds are added to `cost_guard.py` **only when that provider is actually called** — no speculative thresholds for providers not yet wired. |

This ADR extends `cost_guard.py` and introduces the **first** cost-guard wiring into the dispatch path, via the decorator — it does not bolt cost logic onto individual workers.

---

## 6 — Supervisor invariants this design MUST inherit (not loosen)

Because the decorator wraps the supervisor's dispatch seam, it inherits the supervisor contract as it exists in `orchestrator/supervisor.py` today. Symbols below are the **real dispatch-path symbols** (an earlier draft cited names that do not exist in this repo; those have been replaced with verified ones). None of the following may be weakened:

- **Concurrency/depth ceilings — `submit_job`.** `MAX_DEPTH = 1` (`supervisor.py:33`; enforced in `submit_job` at `:276`) and `MAX_THREADS = 25` (`:34`; enforced in `submit_job` at `:282`) are inherited as-is. Workers cannot spawn sub-workers; the `JobSpec.depth` validator (`:99`) rejects `depth != 0`. The decorator adds no path that lets a cached/batched call spawn deeper or exceed the thread ceiling.
- **Hardware affinity is fail-closed.** Affinity is enforced via `check_affinity` / `HardwareAffinityError` (imported from `utils.hardware_policy`, `supervisor.py:29`; the `HardwareAffinityError` branch is handled in `_run_worker` at `:432`, recording a `FAILED` event with `policy: True` and **no silent reroute**). The decorator's cost gate and cache check do not bypass this: any real dispatch still runs the affinity path. The `_MIRROR_BACKENDS` mirror-exclusion lives in `backend_resolver.py:24` (the **CLI path**, caller `agent_launcher.py:611`) — it is **not** on the `_dispatch` path, so the decorator does **not** assume `_MIRROR_BACKENDS` runs on every dispatch. Mirror exclusion on the dispatch path, if needed, is a **to-be-built requirement**, not an inherited one.
- **Checkpoint-before-cancel ordering — `_run_worker`.** `_run_worker` (`supervisor.py:384`) writes the **CANCELLED checkpoint before propagating cancellation** (`:428` comment, `:429` `_append_event(... JobStatus.CANCELLED)`), then re-raises `asyncio.CancelledError`. A cache write is **not** a checkpoint and must not reorder or substitute for this, nor block on cache I/O in a way that delays the checkpoint.
- **Result-event audit stays intact.** The supervisor's event stream (`RUNNING` → `SUCCEEDED`/`FAILED`/`CANCELLED`, emitted in `_run_worker`) is the audit record. A **cache hit still surfaces the normal result event** — a hit is an observable result, not a silent bypass. The decorator exposes no method that clears interrupt/conflicted state without authenticated caller verification.
- **MAESTRO gate classes.** Any new action/endpoint introduced for routing/caching/batching is classified Class 2 (intent log + HITL confirm) / Class 3 (approval token) / Class 4 (cryptographic token + immutable audit) and gated accordingly. Triggering paid cloud escalation is treated as **at least** the same class as the underlying dispatch it decorates — never lower. **A cache hit re-applies the same class gate as a miss** for Class 3/4 paid/sensitive paths: serving a cached result MUST NOT skip a required HITL confirm or approval token. Caching may only short-circuit *gating* for classes where re-serving without re-gating is explicitly safe (Class ≤ 1); §2's `_class_gate_ok(spec)` encodes this.
- **File-system-first payloads.** MCP/CLI worker results remain path-based (`{status, file}`), JSON/quiet mode, allowlist-trimmed schema (consistent with `_run_worker` writing `result.json`, capped at 2 MiB with a truncated marker). The cache stores result metadata consistent with this contract — it does not start inlining large file contents to "warm" the cache.
- **V1 API backward compatibility.** The V1 job API surface and V1's shipped behavior are **not** broken. V2 adds the decorator; it does not remove or alter V1 behavior. `JobSpec` fields stay backward-compatible (`supervisor.py:72`).

---

## 7 — Consequences

**Positive**

- One router, not two: routing/affinity/Win-probe logic stays in exactly one place. No drift, no DRY violation.
- The cache and cost gate attach at a single, well-understood chokepoint (`_dispatch:534`), so the blast radius is one seam, not every worker.
- Cost control becomes real for the dispatch path for the first time (today it has none), and it fails closed.
- L2/L3 boundary stays clean: orama remains stateless; all new state lives in PT.

**Negative / costs**

- New runtime state (the cache) and a new dependency (`anthropic`) enter L2 — exactly why this ADR is the gate.
- The decorator sits on the hot path of every dispatch; its overhead (redaction, key hashing, cache lookup, cost gate) must be cheap and must never block on cache I/O in a way that violates the checkpoint-before-cancel ordering (§6).
- Redaction-before-persist is now a correctness requirement: **a redaction bug becomes a privacy incident.** This is acceptable only because (a) raw prompts are never persisted, (b) input *and output* redaction both run, (c) the key is salted over the redacted form, and (d) a global purge + runtime kill-switch (§3.4) contains any defect without a redeploy.

---

## 8 — Alternatives rejected

- **Parallel `MultiLLMRouter` (a second router).** *Rejected — DRY violation.* `worker_registry` + `model_registry` + `backend_resolver` already route; a parallel router duplicates route order, model pinning, affinity, and Win pre-emption and will drift from them. This is the single most important rejection in this doc.
- **Wrapping individual workers instead of `_dispatch`.** *Rejected.* Spreads cache/cost logic across N workers, multiplies the supervisor-invariant surface (depth/threads/affinity/audit per worker), and loses the single chokepoint. Wrap the one seam.
- **Putting caching/cost-guard logic in orama (L3).** *Rejected — layer violation (per [`ADR-001`](ADR-001-three-repo-adapter-architecture.md)).* orama is stateless methodology; a cache is L2 runtime state. It lives in Perpetua-Tools only. Redis, if used, is a **PT L2** substrate — never orama L3.
- **Using `AsyncOpenAI(base_url="https://api.anthropic.com")` for the Anthropic leg (the reference approach).** *Rejected — wrong API.* Anthropic is `POST /v1/messages` via `anthropic.AsyncAnthropic()`, not chat-completions.
- **Keying the cache on `(messages + model)` only.** *Rejected — collision/serve-wrong-result hazard.* System prompt, tools, `response_format`, and sampling params all change output; omitting them collides distinct requests. The key spans the full canonical request (§3.2).
- **Anchoring cacheability on `temperature == 0`.** *Rejected — inaccurate for the central provider.* `temperature` is removed on Fable 5 / Opus 4.8. Cacheability is gated on verified per-provider determinism (§3.1).
- **Standing up Helicone/Langfuse/Manifest/ClawRouter as services and importing them.** *Rejected — emulation, not importation* (see §9). Each is emulated inside PT primitives, gated by its own follow-on ADR.

---

## 9 — Open questions (Q1..Q4)

The repo idiom: each open question carries a "best guess" line.

- **Q1 — Batch API savings.** Two claims must be kept separate: **(a) fact** — the Anthropic Batches API applies a **flat 50% price reduction** on token usage by design; **(b) hypothesis to measure** — whether *this* deterministic dispatch mix nets ~50% **real** savings given latency tolerance, batch fill, and cache interaction. (a) is not in doubt; (b) is. **Treat (b) as a HYPOTHESIS to MEASURE, not a target.** *Best guess:* batching helps for large, latency-tolerant fan-outs of deterministic calls; measure real savings on a representative job set before committing the batching path to the hot path.
- **Q2 — Eval harness before DeepEval.** What proves a cached/batched result is equivalent to a fresh one? *Best guess:* start with a **minimal output-diff harness** (deterministic-in vs. cached/batched-out) as the first gate; defer DeepEval (semantic/LLM-graded eval) until the diff harness is green and we actually need semantic scoring.
- **Q3 — Group B OSS emulation, one ADR each.** OSS-pattern emulation is **emulation, not importation**, and each tool needs its **own follow-on ADR before any code**: **Langfuse** trace-tree stays methodology in orama and **never** becomes PT runtime state; **Helicone** is a hash-based LRU **inside** PT's `_dispatch` (never a separate service); **Manifest** extends `cost_guard.py` escalation; **ClawRouter** extends `model_registry.py` dynamic thresholding. *Best guess:* land this ADR-002 (cache + cost gate) first, then Helicone-emulation detail, then Manifest, then ClawRouter, then a Langfuse-stays-in-orama note — each as its own ADR-NNN.
- **Q4 — Cost-guard wiring into the dispatch path.** `CostGuard` is HTTP-only today (`fastapi_app.py:134`); the supervisor never imports it. *Best guess:* the decorator constructs/receives a `CostGuard` and is the **only** new place it touches the dispatch path, keeping the HTTP construction site authoritative for budgets and avoiding a second budget source of truth.

---

## 10 — Locked decision (central registry stub)

This ADR locks a new cross-cutting decision. The detail lives here; the pointer should be mirrored into whatever central decision index the repo adopts (no `00-context-and-decisions.md` exists today — link it here when it does).

### D17 — MultiLLMRouter is a caching/batching decorator over `_dispatch`, L2-only (2026-06-15)

**Decision:** `MultiLLMRouter` (greenfield, `perpetua.core.multi_llm_router`) is a caching/batching **decorator** wrapping `OrchestrationSupervisor._dispatch` (`supervisor.py:534`) in Perpetua-Tools (L2) only — never a parallel router, never in orama (L3).

**Rationale:** `worker_registry` / `model_registry` / `backend_resolver` already own routing, model pinning, affinity, and Win pre-emption. A second router violates DRY and will drift. orama is stateless (per [`ADR-001`](ADR-001-three-repo-adapter-architecture.md)); a cache is L2 runtime state.

**Implementation:**
1. Decorator wraps the single dispatch seam; preserves the `JobSpec` contract and `dict` return shape.
2. **Cache:** deterministic-per-provider only (NOT `temperature==0`; that param is removed on Fable 5 / Opus 4.8 and is necessary-but-not-sufficient elsewhere); TTL; **redact (input + output) → canonicalize → salted-hash key → store redacted value**; **key spans the full canonical request** (messages + resolved model + system prompt + tools + tool_choice + response_format + max_tokens + stop + temperature/top_p/top_k/seed where they exist); key-namespaced by model/tenant/session/backend; substrate is in-process LRU by default, any persistent/Redis substrate must be PT-local, tenant-scoped, and encrypt-at-rest-or-secret-free; invalidation by key/model-id/TTL **plus global purge + runtime kill-switch**.
3. **Cost:** extend `orchestrator/cost_guard.py` with a `gate(spec)` that **raises** typed `BudgetExceededError`/`EscalationDeniedError` on any deny or inability-to-evaluate; default-deny cloud escalation; "4x Fable budget" fails closed; **any guard exception = deny, never swallowed**; `_inner` not called on the cloud leg unless `gate()` returns normally; keys via Keychain/.env, never config; thresholds per-provider on first real call.
4. **Anthropic leg** uses `anthropic.AsyncAnthropic()` + `POST /v1/messages` (selected inside `_dispatch`, not the decorator); OpenRouter/Grok/GPT-5.5 may use the OpenAI-compatible path; corrected model ids `claude-fable-5`, `claude-opus-4-8`, `claude-sonnet-4-6`.
5. **Inherits all verified supervisor invariants:** depth/threads (`submit_job:276/282`, `MAX_DEPTH=1`/`MAX_THREADS=25`), affinity fail-closed (`check_affinity`/`HardwareAffinityError`, `_run_worker:432`), checkpoint-before-cancel (`_run_worker:428/429`), result-event audit, MAESTRO classes (**cache hits re-gate Class 3/4**), file-system-first payloads, V1 back-compat.

**v2 implication:** This ADR-002 is the **gate** — it MUST be approved before any v2 routing/caching/batching build starts. Batch-API savings, the eval harness, and each Group B OSS emulation (Langfuse/Helicone/Manifest/ClawRouter) are deferred to measurement and per-tool follow-on ADRs (§9).

---

## 11 — Cross-references

- [`ADR-001-three-repo-adapter-architecture.md`](ADR-001-three-repo-adapter-architecture.md) — three-repo adapter architecture and the L2 (Perpetua-Tools, runtime/stateful) vs. L3 (orama, methodology/stateless) layer boundary this decorator inherits.
- `orchestrator/supervisor.py` — the dispatch seam (`_dispatch:534`) and the verified invariants this decorator inherits: `submit_job:268` (depth `:276` / threads `:282`), `_run_worker:384` (checkpoint-before-cancel `:428/429`), `_prepare_spec_for_inference:722` (dispatch-path call `:616`, Win-leg call `:592`), Win pre-emption block `575–611`, affinity via `check_affinity`/`HardwareAffinityError` (`:29`, `:432`).
- `orchestrator/backend_resolver.py:24` — `_MIRROR_BACKENDS` mirror-exclusion (CLI path; caller `agent_launcher.py:611`), explicitly **not** on the dispatch path.
- `orchestrator/cost_guard.py` — guard to be extended: `can_spend:66`, `record_spend:74`, `snapshot:80`, `set_budget:87` (HTTP-only construction at `fastapi_app.py:134`); `gate()` added by this ADR.
- `orchestrator/model_registry.py:173` — `route_task` (HTTP `/orchestrate` only), and the locus for ClawRouter-style dynamic thresholding (§9).

> **Paths note:** repo-relative in-repo links and GitHub URLs only — never absolute workstation paths (CI `scripts/review/repo_hygiene.py`; CIDF LINT-006).

---

*Generated: 2026-06-15 — Synthesized against the live PT dispatch seam (`orchestrator/supervisor.py:534`) and the verified supervisor/cost-guard symbols cited inline. Provenance note: companion docs referenced in an earlier draft (`docs/v2/14|29|00|27`, `docs/distill-fable-5/`) do not exist in this repo and were removed; the only existing ADR is `ADR-001`, and this doc is `ADR-002` under `docs/adr/`.*
