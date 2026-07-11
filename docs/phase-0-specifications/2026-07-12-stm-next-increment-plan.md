<!-- /autoplan restore point: ~/.gstack/projects/diazMelgarejo-Perpetua-Tools/phase-2-stm-concurrency-dedup-autoplan-restore-20260712-044539.md -->

# Plan: STM Next Increment — Threat-Model Re-Check, Production Wiring, P5/P6/P13 Hardening

**Branch:** `phase-2-stm-concurrency-dedup` · **Base:** `main` · **Repo:** Perpetua-Tools
**Status:** Draft plan, run through `/autoplan` 2026-07-12. This is a genuine pre-implementation plan review — unlike the prior `/autoplan` run against PR #205's already-shipped code, this plan covers work that has NOT been written yet.

**Grounding — salvaged from prior review work (not re-derived):**
- 4-voice CEO review of PR #205: `docs/phase-0-specifications/2026-07-12-ceo-review-quad-voices/`
- 5-voice Eng review of PR #205: `docs/phase-0-specifications/2026-07-12-eng-review-voices/`
- Remediation plan (real wiring target + threat-model task scoping): `docs/phase-0-specifications/2026-07-12-stm-remediation-plan.md`
- Gate record: `docs/phase-0-specifications/PATTERN-SYNTHESIS.md` § "GATE on P5/P6/P13"
- Final approval gate for the prior (audit) run: `docs/phase-0-specifications/2026-07-12-autoplan-final-approval-gate.md`

Per `/autoplan`'s rules, dual-voice review already ran at 4-5x depth for the code this plan wires into — that satisfies and exceeds the Phase 1/3 dual-voice requirement. This run reuses those voices as grounding and adds NEW analysis only where prior review didn't cover forward-looking implementation concerns (the wiring diff itself, sequencing, and the two code-level fixes).

---

## Phase 0: Intake

**Scope of this plan (3 work items, explicitly sequenced):**
1. Threat-model premise re-check (research/decision task, no code)
2. Production wiring: `evaluate_observation()` into `backend_health_map()` (`orchestrator/connectivity.py:130`)
3. Two code-quality fixes surfaced by Eng review: bound `_reorder_buffer`'s outer dict; fix the dedup key to include `sequence`

**UI scope detected:** No — 0 matches for view/rendering terms. This is backend security-pipeline wiring with no UI surface.
**DX scope detected:** Borderline — `GET /health` is an "endpoint," and this is internal orchestrator code, not a public SDK/CLI/API released to third-party developers. Judged NOT in DX scope: the audience is this project's own operators, not external developers integrating against a published interface. Phase 3.5 is skipped on that basis, stated explicitly per the "no skip without rationale" rule.

---

## Phase 1: CEO Review (Strategy & Scope)

### Step 0A: Premise challenge

**Premises this plan rests on** (evaluated, not just accepted):
1. *"The threat-model premise re-check should happen before wiring."* — **Valid, already the User Challenge resolution from the prior review's gate.** The prior run's 3-voice-plus convergence and the user's own explicit decision ("Wiring + threat-model re-check, both required") settled this; not re-litigated here, only implemented.
2. *"Wiring into `backend_health_map()` is the correct integration point."* — **Valid, verified independently by the remediation-plan pass** (read `agent_tracker.py` and `heartbeat_monitor.py`, confirmed they're the wrong data model; found the real live reachability path). Not re-derived here — treated as settled fact from a code-reading pass, not a guess.
3. *"The two Eng-review code fixes (reorder-buffer bound, dedup-key fix) are independent of the wiring/threat-model gate and can land regardless of its outcome."* — **This premise is new to this plan and needs stating explicitly**, since it determines sequencing. It holds: both fixes improve `state_transition_manager.py`'s existing, already-merged code regardless of whether anything ever calls `evaluate_observation()` in production — they reduce the DoS/correctness exposure of code that's merged either way.

**No premise here was accepted uncritically — two were already stress-tested by the prior review's User Challenge, one is new and independently defensible.**

### Step 0B: Existing code leverage map

| Sub-problem | Existing code to leverage |
|---|---|
| Threat-model premise re-check | `docs/phase-0-specifications/MULTIAGENT-SWARM-SECURITY-ANALYSIS.md`'s existing topology table (extend, don't replace); `docs/LESSONS.md` for real incident history |
| Wiring `evaluate_observation()` | `orchestrator/connectivity.py:130-143` (`backend_health_map()`, `_probe()`) — extend the existing function, no new module |
| Reorder-buffer outer-dict bound | `orchestrator/state_transition_manager.py:242-248` (`_touch_cache()`) — reuse this exact helper for `_reorder_buffer`'s outer dict, same pattern already applied to `_seen_observations`/`_last_applied_key` |
| Dedup-key fix | `orchestrator/membership.py:404-434` (`PeerObservation.to_json()`/`_to_dict()`) — extend the existing serialization, not a new dedup mechanism |

**All 4 sub-problems reuse existing code paths — zero new modules, zero new abstractions.** This is a strong DRY signal (Principle 4) for the whole plan.

### Step 0C: Dream state diagram

```
CURRENT STATE
  StateTransitionManager: fully implemented, tested (35/35), zero production callers.
  PeerObservation: schema exists, ZERO production constructors anywhere in the repo.
  GET /health: raw _probe() dicts, no security pipeline in the loop.
  _reorder_buffer outer dict: unbounded across peer_ids.
  Dedup key: omits `sequence`, can false-positive on DUPLICATE.
       |
       v
THIS PLAN
  GET /health -> backend_health_map() -> constructs PeerObservation -> evaluate_observation()
    -> StateTransitionResult merged into the existing /health response contract.
  _reorder_buffer outer dict: LRU-bounded via _touch_cache(), same as the other two caches.
  Dedup key: includes `sequence`, no more false-DUPLICATE risk.
  Threat-model addendum: explicit go/no-go on whether P5/P6/P13 (Sybil/reputation/equivocation)
    make sense at current single-operator LAN scale, or should descope to allowlist+mTLS.
       |
       v
12-MONTH IDEAL (conditional on the threat-model go/no-go)
  IF "proceed": full P5/P6/P13-hardened peer-observation pipeline live across all
    backend health checks, feeding a durable (not in-memory-only) audit trail with
    real logging/metrics, informing Fleet Mode's eventual multi-tenant design.
  IF "descope": a lean allowlist+mTLS reachability model for the actual LAN topology,
    with the BFT/Sybil/reputation machinery kept as tested-but-dormant code, revisited
    only if/when Fleet Mode genuinely introduces untrusted external tenants.
```

### Step 0C-bis: Implementation alternatives table

| Approach | Effort | Risk | Pros | Cons |
|---|---|---|---|---|
| **A. Wire into `GET /health` (this plan)** | Small (3-5h per remediation plan) | Low — extends an existing, already-probed endpoint | Reuses existing infra; smallest diff; matches remediation plan's independently-verified real call site | `/health` is a polling endpoint, not an event stream — `evaluate_observation()` gets called once per poll interval, not per real-time reachability change |
| **B. New dedicated ingestion endpoint/task for peer observations** | Medium-Large | Medium — new surface, new tests, new failure modes | Decouples pipeline cadence from `/health`'s polling interval | Violates Principle 4 (DRY) — builds a second reachability-reporting path alongside `/health`'s existing one; no stated need for a faster cadence than health-check polling already provides |
| **C. Defer all wiring, only ship the two code fixes** | Smallest | None (code-quality only) | Fully unblocks the P18-parity fix and dedup-key correctness bug immediately, no gate dependency | Doesn't resolve the "zero production callers" finding at all — leaves the CEO review's headline finding unaddressed |

**Recommendation: A**, with C's two fixes shipped in parallel (not sequentially) since they're independent of the wiring decision. B is rejected as scope creep per Principle 4 (DRY) — no evidence a second ingestion path is needed. **Mode selection: SELECTIVE EXPANSION** — implement A, ship C's fixes in the same window, do not expand into B.

### Step 0D — Mode-specific analysis / scope decisions

- Reorder-buffer bound + dedup-key fix are **in blast radius** (same file, same module, <1 day CC effort each) — **auto-approved (Principle 2, boil lakes)**.
- Wiring into `/health` touches `orchestrator/connectivity.py` and potentially `orchestrator/fastapi_app.py` or `src/perpetua_tools/orchestrator.py` (the flagged two-app ambiguity) — **in blast radius, borderline on file count depending on which app owns the STM instance → TASTE DECISION**, resolved: proceed with A regardless of which app it lands in (Principle 5, explicit-over-clever: pick the shipped-code owner once identified, don't redesign around the ambiguity).
- Threat-model re-check itself: **no code touched, zero blast radius** — auto-approved trivially.

### Step 0E: Temporal interrogation

- **Hour 1:** Threat-model premise re-check starts — read `MULTIAGENT-SWARM-SECURITY-ANALYSIS.md`, grep `docs/LESSONS.md` for incident history.
- **Hour 2-4:** Addendum written, go/no-go verdict reached.
- **Hour 5 (if "proceed"):** Resolve the two-FastAPI-app ambiguity; identify the real STM-owning app.
- **Hour 6+:** Wire `evaluate_observation()` into `backend_health_map()`; write 2-3 integration tests asserting an audit-log entry on `/health` hits.
- **In parallel, any hour:** Land the reorder-buffer bound and dedup-key fixes — no dependency on the above.

### Step 0.5: Dual Voices — salvaged, not re-run

Per the grounding note above, this plan reuses the prior 4-voice CEO review and 5-voice Eng review rather than dispatching a fresh dual-voice pass, since both already analyzed the exact code this plan wires into, at greater depth (4-5 independent voices vs. the standard 2). Consensus extracted below.

```
CEO DUAL VOICES — CONSENSUS TABLE (salvaged from 4-voice quad-review):
═══════════════════════════════════════════════════════════════
  Dimension                              Consensus
  ──────────────────────────────────────  ─────────
  1. Premises valid?                      CONFIRMED (3/4 voices independently found zero-caller gap)
  2. Right problem to solve?              DISAGREE→RESOLVED (User Challenge, user decided both-required)
  3. Scope calibration correct?           CONFIRMED (wiring-target guess was wrong, corrected by remediation plan)
  4. Alternatives sufficiently explored?  CONFIRMED (build-vs-adopt raised by 2 voices, out of scope for this plan)
  5. Competitive/market risks covered?    N/A — internal security pipeline, not applicable
  6. 6-month trajectory sound?            CONFIRMED (in-memory-only audit trail flagged as a real gap by all voices)
═══════════════════════════════════════════════════════════════
5/6 CONFIRMED, 1 N/A, 0 open disagreements — no new User Challenge required for this plan.
```

Sections 1-10 of the CEO methodology were already run at full depth in the prior review (see the quad-voices folder for the complete section-by-section analysis) — not repeated verbatim here to avoid redundant token spend; referenced by pointer per the salvage instruction.

**Mandatory outputs (Phase 1):**
- "NOT in scope": Fleet Mode design, DELIVERABLE-2 hysteresis machine, approach B (new ingestion endpoint) — all explicitly deferred, not silently dropped.
- "What already exists": see Step 0B leverage map above.
- Error & Rescue Registry: N/A for this forward-looking plan (no execution has happened yet to have errors from) — carried over from the audit run's registry (`2026-07-12-autoplan-final-approval-gate.md` § 7) as historical context, not repeated.
- Failure Modes Registry: see Phase 3 below (Eng review owns this for code-level failure modes).
- Dream state delta: see Step 0C.
- Completion Summary: this plan is APPROVED to proceed to implementation pending the Phase 4 gate below.

**PHASE 1 COMPLETE.** 5/6 CEO dimensions confirmed via salvaged consensus, 1 N/A. No new premise gate or User Challenge — the prior run's gate already covers this plan's core direction. Passing to Phase 2.

---

## Phase 2: Design Review — SKIPPED

No UI scope detected in Phase 0 (0 matches for view/rendering terms). This plan touches only `orchestrator/connectivity.py` and `orchestrator/state_transition_manager.py` — no rendered surface. Skip is stated with rationale per the "no skip without stating what was checked" rule, not silent.

---

## Phase 3: Eng Review + Dual Voices

### Step 0: Scope challenge

Read `orchestrator/connectivity.py:1-150` and `orchestrator/state_transition_manager.py` (full file, already read in the prior Eng review — not re-read verbatim here). Confirmed: `backend_health_map()` currently returns raw `_probe()` dicts with no security-pipeline involvement; `state_transition_manager.py`'s `_reorder_buffer` (line 240) and dedup key (`obs.to_json()`, line 294 via `membership.py:404-434`) are exactly as characterized by the salvaged Eng review — no drift since that review ran (same commit).

### Step 0.5: Dual Voices — salvaged, not re-run

```
ENG DUAL VOICES — CONSENSUS TABLE (salvaged from 5-voice Eng review, 4 non-stale voices):
═══════════════════════════════════════════════════════════════
  Dimension                              Consensus
  ──────────────────────────────────────  ─────────
  1. Architecture sound?                  CONFIRMED (per-peer lock design is sound; not currently load-bearing but not a bug)
  2. Test coverage sufficient?            DISAGREE→RESOLVED (gap identified: outer reorder-buffer bound untested — this plan's Task 3 closes it)
  3. Performance risks addressed?         DISAGREE→RESOLVED (unbounded outer dict — this plan's Task 3 fixes it)
  4. Security threats covered?            CONFIRMED (dedup-key gap — this plan's Task 4 fixes it; 3/4 voices found it independently)
  5. Error paths handled?                 CONFIRMED (no exception handling around dependency calls — noted, not in this plan's scope, tracked as follow-up)
  6. Deployment risk manageable?          CONFIRMED (zero logging/metrics — noted, not in this plan's scope, tracked as follow-up)
═══════════════════════════════════════════════════════════════
4/6 CONFIRMED, 2 DISAGREE→RESOLVED by this plan's own scope (the fixes ARE the resolution).
```

### Section 1: Architecture — wiring diagram

```
BEFORE (current, merged):

  GET /health ──▶ backend_health_map() ──▶ _probe() ──▶ {"ok": bool, "status_code": ..., "url": ...}
                                                              (raw dict, no security pipeline)

AFTER (this plan, Task 2):

  GET /health ──▶ backend_health_map()
                       │
                       ├──▶ _probe() ──▶ raw result
                       │
                       └──▶ PeerObservation(peer_id=<backend>, observer_id=<local>,
                                            epoch=..., sequence=<local monotonic counter>, ...)
                                │
                                └──▶ state_transition_manager.evaluate_observation(obs, old_status=...)
                                          │
                                          ├──▶ StateTransitionResult (accepted, decision_type, audit_entry, flushed)
                                          │
                                          └──▶ merged into the existing /health response contract
                                               (backward-compatible — existing consumers unaffected)

Coupling: backend_health_map() gains one new dependency (a shared StateTransitionManager
instance). Scaling: no change — same polling cadence as today. Security: every /health
poll now produces an audited, quorum-gated decision instead of a raw unaudited dict.
```

### Section 2: Code quality

- **Task 3 (reorder-buffer bound):** apply the exact `_touch_cache()` pattern already used for `_seen_observations`/`_last_applied_key` to `_reorder_buffer`'s outer dict. No new abstraction — literal reuse of an existing, tested helper (Principle 4, DRY; Principle 5, explicit-over-clever — the simplest fix is to reuse the pattern already proven correct twice in the same file).
- **Task 4 (dedup-key fix):** extend `PeerObservation.to_json()`/`_to_dict()` (`membership.py:404-434`) to include `sequence` (and consider `observer_provenance`, per Kimi's lower-confidence flag) in the serialized digest. Smallest possible fix — one field addition, not a new dedup mechanism.

### Section 3: Test Review — test diagram

| Codepath (new/changed) | Test type | Exists? | Gap |
|---|---|---|---|
| `backend_health_map()` constructs a `PeerObservation` per probe result | Unit | No — new | **Add**: assert a `PeerObservation` is built with correct `peer_id`/`epoch`/`sequence` fields per backend |
| `evaluate_observation()` called from `/health`, result merged into response | Integration | No — new | **Add**: hit `GET /health`, assert an `audit_log` entry was appended (per remediation plan §1) |
| `.flushed` results from a buffered-then-flushed observation surfaced in `/health` response | Integration | No — new | **Add**: simulate a buffered gap via 2 rapid polls, assert `flushed` appears in the 2nd response |
| `_reorder_buffer` outer dict bounded across many distinct `peer_id`s | Unit | No — gap identified by Eng review | **Add**: seed `reorder_buffer_max`-many distinct peers each with an abandoned gap, assert the outer dict itself is bounded (mirrors `test_seen_observations_and_last_applied_key_are_lru_bounded`) |
| Dedup key disambiguates observations differing only in `sequence` | Unit | No — the existing tests explicitly work around this bug (`tests/test_state_transition_manager.py:311-314` per both Codex runs) | **Add**: a test asserting two same-payload-different-sequence observations are NOT both flagged as DUPLICATE |

**Test plan artifact:** this table constitutes the test plan for this increment — no separate file needed given the small scope (5 test additions across 2 files).

### Section 4: Performance

No new N+1 queries or caching concerns — `backend_health_map()`'s cadence is unchanged (still one poll per `/health` call), and `evaluate_observation()`'s cost is O(witness_count) per the existing implementation, unaffected by this plan's changes.

**Mandatory outputs (Phase 3):**
- "NOT in scope": approach B (new ingestion endpoint), full logging/metrics overhaul, durability fix for `AuditLog`/`ReputationLedger` (tracked as follow-up, not in this increment).
- "What already exists": Step 0B leverage map.
- Architecture diagram: Section 1 above.
- Test diagram: Section 3 above.
- Failure modes registry: see below.
- Completion Summary: APPROVE, proceed to Phase 4.

**Failure Modes Registry (for this plan's own changes, not the whole module):**

| Failure mode | Likelihood | Mitigation in this plan |
|---|---|---|
| Wiring introduces a regression in `/health`'s existing response contract | Low | Integration test asserts backward-compatible response shape |
| `evaluate_observation()` raises on a probe result it doesn't expect | Medium | Not explicitly handled in this plan's scope — flagged as follow-up (Eng review's "no try/except around dependency calls" finding); recommend a try/except wrapper around the new call site specifically, scoped to this wiring, as an in-plan addition |
| Reorder-buffer fix introduces a subtle eviction-order bug | Low | Reuses `_touch_cache()` verbatim — same code path already tested twice |
| Dedup-key fix breaks an existing test that relies on the current (buggy) serialization | Medium | Existing tests that "work around" the bug (per Codex's citation) will need updating — flagged explicitly, not silent |

**PHASE 3 COMPLETE.** 4/6 Eng dimensions confirmed, 2 resolved by this plan's own scope. Skipping Phase 3.5 (DX) per Phase 0's rationale. Passing to Phase 4.

---

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale |
|---|-------|----------|-----------------|-----------|-----------|
| 1 | CEO | Reuse salvaged 4-voice review instead of fresh dual-voice dispatch | Mechanical | P6 (bias toward action) | Prior review already exceeds the dual-voice requirement at greater depth on the exact same code |
| 2 | CEO | Reject Approach B (new ingestion endpoint) | Mechanical | P4 (DRY) | No stated need for a faster cadence than `/health` polling already provides |
| 3 | CEO | Approve Approach A (wire into `/health`) + ship Task 3/4 fixes in parallel | Taste → resolved | P3 (pragmatic) | Smaller diff, reuses existing infra, both fixes are independent of the wiring gate |
| 4 | CEO | Defer the exact FastAPI-app ownership question to implementation time | Taste → resolved | P5 (explicit over clever) | Don't redesign around an ambiguity that a single grep will resolve once implementation starts |
| 5 | Eng | Add a try/except around the new `evaluate_observation()` call site specifically | Mechanical | P1 (completeness) | Addresses a concrete failure mode this plan itself introduces, small and scoped |
| 6 | Eng | Flag (not fix) existing tests that "work around" the dedup-key bug | Mechanical | P5 (explicit over clever) | Silently changing test behavior without flagging it would hide a real semantic shift |

---

## Phase 4: Final Approval Gate

### Plan Summary
Wire `StateTransitionManager.evaluate_observation()` into the real, already-identified `GET /health` reachability path, and ship two independent code-quality fixes (bounded reorder-buffer, corrected dedup key) — gated on a cheap threat-model premise re-check happening first, per the prior run's already-resolved User Challenge.

### Decisions Made: 6 total (2 mechanical auto-decided outright, 2 taste decisions resolved, 2 mechanical from Eng review)

### User Challenges
None — the one applicable User Challenge (threat-model premise vs. wiring priority) was already resolved by explicit user decision in the prior `/autoplan` run. Not re-litigated.

### Your Choices (taste decisions, already resolved per the 6 principles — flagged for visibility)
**Choice 1: Wiring approach** (from CEO phase) — Chose A (wire into `/health`) over B (new ingestion endpoint) per DRY. B remains available if a future need for faster-than-poll-cadence reachability reporting emerges — not likely soon.
**Choice 2: FastAPI-app ownership** (from CEO phase) — Deferred to implementation time rather than resolved here; whichever app is confirmed to be the deployed one owns the STM instance.

### Auto-Decided: 4 decisions — see Decision Audit Trail above

### Review Scores
- CEO: 5/6 confirmed (salvaged from 4-voice quad-review), 1 N/A
- CEO Voices: source = salvaged (4 voices, exceeds standard dual-voice depth)
- Design: skipped, no UI scope
- Eng: 4/6 confirmed (salvaged from 5-voice review), 2 resolved by this plan's own scope
- Eng Voices: source = salvaged (5 voices across 4 models, exceeds standard dual-voice depth)
- DX: skipped, not developer-facing scope

### Cross-Phase Themes
**Theme: in-memory-only durability** — flagged in both the original CEO review and Eng review (AuditLog/ReputationLedger/EquivocationLog never persisted). Not fixed by this plan (out of scope, tracked as follow-up in the Failure Modes table) — high-confidence signal that it's the next thing after this increment.

### Deferred to follow-up (not this increment)
- Structured logging/metrics for terminal decisions (both reviews flagged, neither is blocking).
- Durability fix for in-memory-only security state.
- Approach B (dedicated ingestion endpoint) — only if a real need for sub-poll-interval reachability reporting emerges.
- Full try/except coverage around all STM dependency calls (this plan only wraps the one new call site it introduces).

### Implementation Tasks (aggregated)

- [x] **T1 (P1, human: ~half day / CC: ~2-4h) — Threat-model premise re-check** — **DONE 2026-07-12, verdict: DESCOPE.** Addendum appended to `MULTIAGENT-SWARM-SECURITY-ANALYSIS.md`: zero real witnesses in the current code, trust boundary is 2 machines/1 operator (quorum defends against nothing a compromise of the primary machine doesn't already defeat), and a full `docs/LESSONS.md` incident-history grep found zero adversarial incidents ever (100% self-inflicted operational flakiness — DHCP moves, GPU/process crashes, timeouts). Gate updated in `PATTERN-SYNTHESIS.md`.
  - Surfaced by: CEO phase (User Challenge resolution) + remediation plan §2
  - Files: `docs/phase-0-specifications/MULTIAGENT-SWARM-SECURITY-ANALYSIS.md`
- [ ] **T2 (P3, human: ~small / CC: ~1h) — Bound `_reorder_buffer`'s outer dict** — Apply `_touch_cache()` to the outer `peer_id → OrderedDict` map, matching the existing pattern. **Still unblocked, still recommended** — this is a real DoS gap independent of the threat-model verdict (protects against out-of-order/memory growth that occurs with zero adversaries too).
  - Surfaced by: Eng phase, 4/4 non-stale voices
  - Files: `orchestrator/state_transition_manager.py`, `tests/test_state_transition_manager.py`
- [ ] **T3 (P2, human: ~small / CC: ~1h) — Fix dedup key to include `sequence`** — Extend `PeerObservation.to_json()`/`_to_dict()`, update the tests that currently work around the bug. **Still unblocked, still recommended** — same reasoning as T2, a correctness bug independent of the threat model. **In progress live via the coordination board** — claimed by `codex-claude-partner` as `STM-Next-02-dedup-key-sequence-provenance-fix`.
  - Surfaced by: Eng phase, 3/4 voices (Claude Sonnet's pass missed it)
  - Files: `orchestrator/membership.py`, `tests/test_state_transition_manager.py`
- [~] **T4 (P1, human: ~half day / CC: ~3-5h, depends on T1's go/no-go) — Wire `evaluate_observation()` into `backend_health_map()`** — **SUPERSEDED by the DESCOPE verdict.** Do not wire the full P5/P6/P13-gated pipeline as originally scoped. Per the addendum's recommended alternative: a lean reachability/liveness model (retry + the already-shipped monotonic epoch/sequence gate) may still be worth adding to `backend_health_map()`, but NOT via `evaluate_observation()`'s witness-quorum/reputation/equivocation gates, which have nothing to operate on at current scale. If this lean alternative is wanted, it should be scoped as a new, smaller task — not this one as originally written.
  - Surfaced by: remediation plan §1, CEO phase gate
  - Files: `orchestrator/connectivity.py`
- [~] **T5 (P2, human: ~small / CC: ~1-2h, depends on T4) — Resolve the two-FastAPI-app ambiguity** — **Moot for now** — only matters if/when T4-equivalent wiring is revived (Fleet Mode introducing real external tenants). Not needed for the descope path.
  - Surfaced by: remediation plan §1
  - Files: `orchestrator/fastapi_app.py`, `src/perpetua_tools/orchestrator.py`
- [~] **T6 (P2, human: ~small / CC: ~2-3h, depends on T4) — Consume `.flushed` in the `/health` response, add integration tests** — **Moot for now**, same reasoning as T5.
  - Surfaced by: Eng phase test-coverage section
  - Files: `orchestrator/connectivity.py`, `tests/` (integration)

**Sequencing (updated 2026-07-12): T1 done, verdict DESCOPE. T2/T3 remain live — land these regardless (independent DoS/correctness fixes). T4/T5/T6 superseded/moot — do not implement as originally scoped; revisit only if Fleet Mode changes the actual trust boundary (real external tenants, not just more self-owned nodes).**
