# Phase 0 Fix #3 + Medium Items — Decision Brief

**Date:** 2026-07-10  
**Status:** Decision record; pending user confirmation before implementation follows.
**Proposed decision:** Asymmetric hysteresis (D2 model) — quick to suspect, slow to recover
**Ranked handoff:** [phase0-and-orama-closure-rankings-2026-07-18.md](../../../../references/phase0-and-orama-closure-rankings-2026-07-18.md)

---

## CRITICAL FIX #3: StateTransitionManager Model Reconciliation

### Current State (The Conflict)

Two deliverables specify contradictory state machine hysteresis constants:

| Source | Constant | Value | Semantics |
|--------|----------|-------|-----------|
| **D1** § 2 (schema) | `POLLS_TO_CONFIRM` | **2** | Symmetric: 2 polls in any direction triggers state change |
| **D2** § 5.3 (STM pseudocode) | `PROMOTE_THRESHOLD` | **2** | 2 positive polls → SUSPECT/INACTIVE→ACTIVE |
| **D2** § 5.3 (STM pseudocode) | `DEMOTE_THRESHOLD` | **3** | 3 negative polls → ACTIVE→SUSPECT, then sustained hold → INACTIVE |
| **D2** § 5.3 (STM pseudocode) | `RECOVERY_GRACE` | **1** | One recovery poll resets demotion counter |

### Why This Blocks Phase 1

- Implementation must encode state machine transitions; can't guess which model is canonical
- Test fixtures (TDD Batch 7, edge cases E1–E10) depend on knowing exact thresholds
- Production SLA (30–90s committed failure-state detection) depends on which model and the configured hysteresis/dead-hold windows
- Integration with D1 PeerObservation depends on aligned terminology

### User Decision: ADOPT ASYMMETRIC HYSTERESIS (D2 Model)

**Rationale:** Conservative approach for distributed systems. Quick to suspect (2 polls ≈ 20s) protects against cascading failures. Slow to recover (3 polls ≈ 30s) prevents flapping on transient link glitches.

### Proposed Follow-Up If Confirmed (3 Tasks)

#### Task 3.1: Reconcile D1 § 2 (Schema)

**Current text in D1:**
```text
StateTransitionManager constants:
- POLLS_TO_CONFIRM = 2 (hysteresis)
- PROMOTE_THRESHOLD = 2
- DEMOTE_THRESHOLD = 3
- CONFIRM_DEAD_HOLD = 90s (recover-grace window)
```

**Problem:** D1 uses `POLLS_TO_CONFIRM` terminology (symmetric) but values suggest asymmetric. Confusing for implementers.

**What to do:**
1. Rename `POLLS_TO_CONFIRM` → `PROMOTE_THRESHOLD` throughout D1 § 2 to match D2 terminology
2. Add clarification: "PROMOTE_THRESHOLD = 2 positive polls triggers recovery/promotion to ACTIVE. DEMOTE_THRESHOLD = 3 negative polls triggers demotion from ACTIVE to SUSPECT; CONFIRM_DEAD_HOLD controls confirmed INACTIVE."
3. Update the PeerRecord dataclass example to show both counters (`pending_count_promote`, `pending_count_demote`) tracking independently
4. Verify section 2's "Properties" list includes the active constants: PROMOTE_THRESHOLD, DEMOTE_THRESHOLD, CONFIRM_DEAD_HOLD, plus POLLS_TO_CONFIRM only as a deprecated renamed reference if it still appears.

**File to update:** `DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md` § 2 (Schema) + § 2.2 (StateTransitionManager class definition)

**Verification checklist:**
- [ ] All instances of `POLLS_TO_CONFIRM` replaced with `PROMOTE_THRESHOLD` (except footnote: "formerly POLLS_TO_CONFIRM")
- [ ] Asymmetric semantics explicitly stated
- [ ] PeerRecord example updated to show dual counters
- [ ] Constants table matches D2 exactly

---

#### Task 3.2: Enhance D2 § 5.3 (STM Pseudocode & Logic)

**Current state:** D2 has pseudocode outline but lacks detail on:
- Exact state transitions (all 9 possible edge cases)
- Recovery logic (what resets counters? when?)
- Out-of-order observation handling (do observations increment counters or replace them?)
- Race conditions (what if PROMOTE_THRESHOLD is hit while DEMOTE_THRESHOLD is pending?)

**What to do:**

1. **Write full `_apply_observation()` pseudocode** (~40–50 lines):
   - Input: `(peer_id, epoch, timestamp, observation_type)` where observation_type ∈ {REACHABLE, UNREACHABLE}
   - Output: state change trigger or no-op
   - Validation and logic:
     ```text
     validate peer_id, epoch, sequence, nonce, timestamp freshness, and observation_type
     reject duplicate (peer_id, epoch, sequence, nonce) before counter mutation
     reject non-monotonic observations before counter mutation

     if observation_type == REACHABLE:
       increment pending_count_promote
       reset pending_count_demote to 0  # reset recovery grace
       if pending_count_promote >= PROMOTE_THRESHOLD:
         trigger state_change(SUSPECT → ACTIVE)
         reset pending_count_promote to 0
     else (UNREACHABLE):
       increment pending_count_demote
       reset pending_count_promote to 0  # reset recovery grace
       if pending_count_demote >= DEMOTE_THRESHOLD:
         trigger state_change(ACTIVE → SUSPECT)
         reset pending_count_demote to 0
         set confirm_dead_timestamp = now()  # start CONFIRM_DEAD_HOLD window
     ```

2. **Clarify recovery logic** (~10–20 lines):
   - If peer is INACTIVE and one REACHABLE observation arrives within CONFIRM_DEAD_HOLD window: state stays INACTIVE (wait for multiple observations)
   - If peer is INACTIVE and one REACHABLE observation arrives AFTER CONFIRM_DEAD_HOLD expires: state → ACTIVE (recovery window opened; treat as fresh peer)
   - This prevents oscillation between INACTIVE and ACTIVE

3. **Document edge cases (E1–E10 from task list)** with exact expected behavior:
   - E1: Empty observation batch → no state change
   - E2: Out-of-order observations (newer, then older) → older observation ignored (monotonic apply gate from T7)
   - E3: Multiple observations in one batch (e.g., 3 REACHABLE + 1 UNREACHABLE) → apply in sequence; threshold checks run after each observation
   - E4: Threshold hit mid-batch (e.g., after 2nd of 3 REACHABLE) → state changes immediately; 3rd observation is applied to NEW state
   - E5: Flapping (REACHABLE, UNREACHABLE, REACHABLE within 1 second) → counters reset twice; no state change if neither threshold hit
   - E6: Clock skew (observation timestamp in future by >deadline) → state doesn't change (freshness gate from T2 rejects it)
   - E7: Conflicting timestamps (same epoch, same peer, same seq, different nonce) → keep deterministic winner by `(epoch, sequence, timestamp, nonce)` ordering; record conflict for T3 replay telemetry
   - E8: Sybil witnesses (5 observers all reporting UNREACHABLE for same peer at same epoch) → only observations that satisfy D4 proof diversity + witness quorum can increment the demotion counter
   - E9: Recovery after CONFIRM_DEAD_HOLD expiry → transition peer to ACTIVE, reset counters, then apply the arriving UNREACHABLE to the new state so `pending_count_demote=1` and all other counters are 0
   - E10: Bootstrap (peer appears for first time) → state = ACTIVE initially; first UNREACHABLE increments demote counter; no change until DEMOTE_THRESHOLD

4. **Pseudocode signature & contract**:
   ```python
   _apply_observation(observation: PeerObservation) -> StateChange | None:
       """
       Apply one observation and decide if state change is triggered.
       
       Args:
           observation: Complete observation record containing peer_id, epoch,
                        sequence, nonce, timestamp, observer_id, and type.
       
       Returns:
           StateChange(from_state, to_state, reason) if threshold crossed, else None
       
       Guarantees:
           - State never regresses (monotonic apply gate)
           - Replay/dedup and freshness checks run before counter mutation
           - Counters reset on opposite observation
           - One observation affects at most one counter increment
       """
   ```

**File to update:** `DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md` § 5.3 (STM Integration)

**Verification checklist:**
- [ ] `_apply_observation()` pseudocode complete (40–50 lines, includes all branches)
- [ ] Recovery logic documented with exact CONFIRM_DEAD_HOLD window semantics
- [ ] All edge cases E1–E10 listed with expected behavior
- [ ] Pseudocode signature includes input types + return type + docstring
- [ ] Constants (PROMOTE_THRESHOLD=2, DEMOTE_THRESHOLD=3, CONFIRM_DEAD_HOLD=90s) referenced in pseudocode

---

#### Task 3.3: Preserve D4 Threat Claims; Add Cross-Reference Only If Needed

**Current state:** D4 § Summary Matrix lists all threats and intentionally keeps the multiplicative-formula claims as the target design basis for later implementation.

**What to do:**

1. Do **not** weaken or rewrite D4's multiplicative-formula claims.
2. If a cross-reference is needed, add only a short pointer from the STM docs back to D4, not a new threat-model claim.
3. Treat implementation catch-up work as Phase 1/Phase 1b scope, not as a reason to dilute the D4 target-state language.

**File to update:** None for claim changes. Optional cross-reference belongs in D2 § 5.3, not in D4.

**Verification checklist:**
- [ ] No substantive D4 claim changes
- [ ] Any STM cross-reference preserves D4 as target-state guidance
- [ ] Consistent terminology (PROMOTE_THRESHOLD, not POLLS_TO_CONFIRM)

---

### Task 3 Dependencies & Sequence

**Order:** 3.1 (schema) → 3.2 (pseudocode) → 3.3 (D4 preservation/cross-reference check)

**Why:** D1 provides the contract (constants + data structures); D2 implements the logic; D4 validates the threat coverage.

**Re-review gate:** After all three tasks complete, re-run the Checkpoint 1.0 Cline review focusing only on STM sections. If Cline approves, move to Phase 1 scoping.

---

## MEDIUM ITEMS (Phase 1b Candidates)

These do NOT block Phase 1 start. They are design decisions that can be deferred + tracked in backlog.

### M1: Heartbeat Sequence Bit-Width Specification

**What:** D2 § 2 says `seq: uint32` but doesn't justify the choice. Is 2^32 sufficient for N=2 nodes?

**Why it matters:** 
- If seq overflows and wraps, T7 monotonic apply gate might accept a reordered observation as "newer" when it's actually old
- Example: seq=4294967294, next observation seq=0 (wrapped) — if treated as "newer", could regress state

**Decision needed:**
1. **Keep uint32 and document wrap behavior:** Heartbeat sends seq every 10s; uint32 wraps after 2^32 heartbeats ≈ 1,362 years. Wrap is non-issue for practical systems, but modular comparison must be explicit and tested at `MAX_UINT32 → 0` and `0 → MAX_UINT32`. → Phase 1: document + test wrap semantics.
2. **Promote to uint64:** Extra safety margin if deployment lifetime > 50 years. → Phase 1: minimal code change.
3. **Add wrap-around detection:** Monitor seq delta; flag if delta jumps >1000 (potential wrap). → Phase 1b enhancement.

**User decision needed:** Which of 1, 2, or 3?

**File impacted:** D2 § 2 (Timeout Hierarchy, field definition)

**Downstream:** TDD test case: write observation with seq=4294967294, then seq=0, verify monotonic gate rejects the wrapped one as old.

---

### M2: TDD Batch 7 Test Vector M1 (Ghost-Peer with Witnesses)

**What:** D1 § 4 (TDD Batch 7) test vector M1 reads:
```text
Scenario: Ghost-peer (proof=0, witnesses=2)
Expected: confidence = 0.00
```

**Ambiguity:** If proof=0, can witness_set be non-empty? The multiplicative formula has witness_multiplier ∈ [0.50, 1.00], but proof_score=0 zeros the whole product. So why specify witnesses=2?

**Possible interpretations:**
1. **Ghost-peer = proof-less** (proof=0 regardless of witnesses); witnesses are ignored in scoring. Test vector should read `witnesses=[]` (empty).
2. **Ghost-peer = non-provable** (any peer without sufficient proof sources); witnesses can exist but don't rescue the score. Test vector is correct as-is; it tests that witnesses don't inflate score when proof is missing.

**Why it matters:**
- TDD test implementation depends on this; confusion leads to wrong test fixtures
- Implementation checks: do we validate that proof=0 implies witnesses=[], or do we allow witnesses even without proof?

**User decision needed:** Is interpretation 1 or 2 correct? (Recommended: 2 — allows separating the proof requirement from witness agreement.)

**File impacted:** D1 § 4 (TDD Test Specs, test case M1)

**Downstream:** Implement fixture builder: `make_ghost_peer(proof=0, witnesses=2)` — how should this be constructed? Does it create a PeerObservation with witness_set=[obs_1, obs_2] + proof_score=0?

---

### M3: StateTransitionManager Interface Protection Pattern

**What:** Should StateTransitionManager validate input or assume caller is trusted?

**Options:**
1. **Defensive (Phase 1):** Add mandatory input validation inside `_apply_observation()`:
   - Reject null peer_id, invalid epoch (negative, decreasing), invalid observation_type
   - Raise ValueError with diagnostic message; let caller handle
   - Pros: Catches bugs early; implementer can't accidentally pass garbage
   - Cons: +30 lines of validation code; validation is trusting caller didn't already validate

2. **Trust (rejected for Phase 1):** No validation; assume caller already validated input
   - Rejected because STM is the authority that mutates counters and state; it must not accept invalid, replayed, stale, or non-monotonic observations.

3. **Hybrid (Phase 1b):** Validation in a separate gate function; STM calls it via hook
   - Caller can enable/disable validation (e.g., `_apply_observation(obs, validate=True)`)
   - Pros: Flexible; can disable in production for speed
   - Cons: API surface grows; two code paths to maintain

**Recommendation:** Option 1 (mandatory STM validation) is the Phase 1 choice. The STM validates monotonicity, timestamp freshness, replay/dedup keys, and observation type before any counter mutation.

**Why it matters:**
- Affects error handling in Phase 1 implementation
- If caller doesn't know which exceptions to expect, integration is harder

**File impacted:** D2 § 5.3 pseudocode (add validation section or remove it explicitly)

---

### M4: Checkpoint Dependencies & Gate Criteria

**What:** D1 § 6 lists four checkpoints (1.0–1.3) but doesn't define gate criteria. Example:
- "Checkpoint 1.0: Schema Alignment + Confidence" — does this mean all fields landed, or all tests passing?
- Can Phase 1 start with schema landed but tests not yet written?

**Why it matters:**
- Determines when Phase 1 tasks can be scheduled
- If Checkpoint 1.1 is "Confidence Wired + Test Regression", do ALL Batch 7 tests need to pass, or just one?

**Decisions needed (one per checkpoint):**

| Checkpoint | Must-have acceptance gate | Deferrable only after gate passes |
|---|---|---|
| **1.0** | Schema and immutable field normalization landed; all schema fixture tests M1–M5 pass; mutable inputs copied/frozen. | Additional fixture volume beyond the blocker set. |
| **1.1** | `compute_confidence()` wired into PeerObservation; all Batch 7 multiplicative tests pass; no zero-proof case can produce non-zero confidence. | Threshold tuning and UX labels. |
| **1.2** | StateTransitionManager integrated; all hysteresis, recovery, validation, witness-quorum, and counter-reset tests pass. | Telemetry dashboards and adaptive tuning. |
| **1.3** | Epoch, sequence, nonce, and T7 monotonic apply gate implemented; all edge cases E1–E10 pass, including batch mid-threshold transitions. | Longer fuzz/property-test runs beyond the required blocker vectors. |

**Recommendation:** Partial thresholds are not acceptable for blocker gates. Phase 1 should proceed only after each checkpoint's blocker-specific test vectors and listed edge cases pass.

**File impacted:** D1 § 6 (Integration Checkpoints)

**Downstream:** Phase 1 task scoping depends on this; determines whether tasks are sequential or parallel.

---

### M5: Discovery Fallback Order & Parallelization

**What:** D2 § 3 (Detection SLA) assumes peer discovery is fast, but details are deferred. Questions:
- Should discovery try mDNS first (local only), then static seeds (fallback)?
- Should discovery run mDNS and static seeds in parallel, or serial?
- If mDNS succeeds, do we wait for static seeds?
- Timeout for each strategy?

**Why it matters:**
- 30–90s failure-state SLA depends on peer being discovered within ~10–20s (leaving rest for observation collection)
- If discovery is serial + mDNS timeout is 30s, SLA is at risk
- If discovery is parallel, requires thread pool / async; adds complexity

**User decision needed:**

1. **Strategy order:**
   - Primary: mDNS `.local` discovery (fast, requires mdns-sd library, 3s timeout default)
   - Fallback: all static seed IPs from config (slower, reliable, 5s per seed when probed serially)
   - Tertiary: peer gossip (ask other observed peers where they know this peer)

2. **Parallelization:**
   - Option A (Serial): Try mDNS, if fail try each configured seed, if fail try gossip. Total: 3s + (5s × number of seeds) + gossip timeout.
   - Option B (Parallel): Start mDNS + bounded static-seed probes simultaneously, wait for first success (fast path ~3s), continue with gossip if both fail.

3. **Recommendation:** Option B with async—mDNS + seeds run in parallel. Time budget: 3s for fast path, 8s fallback. Gossip added only if both fail.

**File impacted:** D2 § 3 (Detection SLA section); add new subsection "Discovery Strategy"

**Downstream:** Phase 1 implementation needs discovery module; this decision shapes its architecture.

---

### M6: Per-Epoch Dedup Cache Eviction (T3 — Replay Defense)

**What:** T3 (Replay Attack) mitigation stores `(witness_id, nonce)` tuples to prevent replay. But when epoch advances, should old tuples be cleared?

**Scenarios:**
- Scenario A: Peer sent observation in epoch 5 with nonce=X. Epoch advances to 6. Can same nonce=X be used again? (Answer: yes, epoch is part of the dedup key: `(witness_id, epoch, nonce)`)
- Scenario B: Dedup cache grows unbounded (one entry per unique nonce ever seen). Memory leak? (Answer: yes, if not pruned)

**Why it matters:**
- Unbounded cache is a memory DoS vector (attacker sends many unique nonces, cache bloats)
- Clearing old tuples when epoch advances saves memory but risks accepting old nonces in new epoch

**User decision needed:**

1. **Dedup key scoping:**
   - Option A: `(witness_id, nonce)` (epoch-independent) — nonce must be globally unique across all epochs
   - Option B: `(witness_id, epoch, nonce)` (epoch-scoped) — nonce can be reused in different epochs

2. **Cache eviction:**
   - Option A (Keep all): Store forever. Protects against replay across epochs. Memory unbounded.
   - Option B (Rotate per epoch): Keep only last 2 epochs of tuples; evict older. Protects against replay within ~20 seconds (2 epochs × 10s). Memory ~2X per epoch.
   - Option C (LRU with watermark): Evict entries older than 90s (CONFIRM_DEAD_HOLD). Memory bounded, but allows new epoch to reuse old nonce if 90s have passed.

3. **Recommendation:** Option B (epoch-scoped key, rotate per epoch). Trade-off: replay protection good enough (within 20s window), memory bounded, simpler implementation.

**File impacted:** D4 § T3 (Replay Attack mitigation subsection)

**Downstream:** Phase 1 implementation of replay dedup; affects hash set design.

---

### M7: Rate Limiting Adaptive Tuning (T5 — DoS Flooding)

**What:** D4 § T5 specifies static token bucket parameters (`R` obs/s sustained, `B` burst), but real systems need adaptation. Should rate limits adjust based on system load?

**Scenarios:**
- Scenario A: Queue length = 0 for 60s. Increase `R` to accept more observations? (Rare, but it signals headroom.)
- Scenario B: Queue length = 100 for 10s. Decrease `R` to shed load? (Urgent, but aggressive adjustment might starve legitimate observers.)

**Why it matters:**
- Static limits are conservative; can unnecessarily drop legitimate observations when system has headroom
- Adaptive limits maximize throughput while protecting against floods

**User decision needed:**

1. **Static (Phase 1):** Keep `R` and `B` constant. Example: `R=100 obs/s, B=200 burst`. Simple, predictable.

2. **Adaptive (Phase 1b):** Adjust `R` based on queue length:
   - If queue_length < 10 for 30s: `R += 10` (increase by 10%)
   - If queue_length > 100 for 5s: `R -= 20` (decrease by 20%)
   - Bounds: `50 <= R <= 200` obs/s

3. **Recommendation:** Phase 1 = static (R=100, B=200); Phase 1b = add adaptive tuning heuristics.

**File impacted:** D4 § T5 (Flooding / DoS mitigation); add note "static limits in Phase 0; adaptive enhancement in Phase 1b"

**Downstream:** Phase 1 rate limiter implementation; Phase 1b monitoring + feedback loop.

---

## Summary: What Decision-Maker Needs to Know

### For Fix #3 (Proposed, pending confirmation)
- **Asymmetric hysteresis (D2 model) is the recommended choice.** This means:
  - Positive observations promote/recover peers toward ACTIVE after `PROMOTE_THRESHOLD=2`
  - Negative observations demote peers toward SUSPECT after `DEMOTE_THRESHOLD=3`, then confirmed INACTIVE only after the dead-hold window
  - Consequence: Better resilience to cascading failures; worse UX during transient link glitches
  - Production impact: committed failure-state SLA remains 30–90s; confirmed INACTIVE includes the additional hold window

### For Medium Items (Phase 1b—OPTIONAL)
- **M1 (Sequence bit-width):** Recommend keep uint32 with explicit modular comparison and MAX→0 / 0→MAX tests; wrap occurs after ~1,362 years at 10s intervals.
- **M2 (Ghost-peer witnesses):** Recommend interpretation 2; allows separating proof requirement from witness agreement. More flexible for future enhancements.
- **M3 (STM validation):** Mandatory defensive validation inside `_apply_observation()` before any counter mutation.
- **M4 (Checkpoint gates):** All blocker-specific vectors and edge cases must pass; partial thresholds do not clear a checkpoint.
- **M5 (Discovery):** Recommend parallel mDNS + static seeds; SLA-compliant at ~5s median. Enables async implementation.
- **M6 (Replay cache):** Recommend epoch-scoped dedup + 2-epoch rotation. Memory-safe, sufficient protection.
- **M7 (Rate limit):** Recommend static for Phase 1; adaptive tuning in Phase 1b. Phased approach, lower risk.

### Timeline Impact
- **Fix #3 tasks (3.1–3.3):** ~2–3 hours to complete + re-review. Blocks Phase 1 scoping.
- **Medium items (M1–M7):** Estimated ~0.5 hour each to decide + document. Do NOT block Phase 1 start; track in Phase 1b backlog.

---

## Next Steps (User Decision + Execution)

### Immediate (Today)
- [ ] Confirm Fix #3 approach (asymmetric hysteresis) — **pending user confirmation**
- [ ] Assign tasks 3.1, 3.2, 3.3 to implementer (estimate 2–3 hours)
- [ ] Decide on Medium items M1–M7 (time-box to 30 minutes decision)
- [ ] Re-review D1/D2/D4 via Cline review agent

### After Fix #3 Complete
- [ ] Checkpoint 1.0 gate re-review (Cline, focusing on STM sections)
- [ ] Phase 1 task scoping (based on checkpoint gate criteria from M4)

### Phase 1b Backlog
- [ ] Implement decisions from M1–M7 after the user confirms them
