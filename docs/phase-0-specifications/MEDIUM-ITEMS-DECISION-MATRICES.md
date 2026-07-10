# Medium Items (M1–M7) — Formal Decision Matrices

**Date:** 2026-07-10  
**Status:** Ready for user decision (yes/no/defer per item)  
**Purpose:** M1–M7 are Phase 1b candidates. They do NOT block Phase 1 start. This doc formats each item as a decision matrix so you can make rapid yes/no/defer choices.

---

## M1: Heartbeat Sequence Bit-Width Specification

**Problem:** D2 § 2 says `seq: uint32` but doesn't justify. Is 2^32 sufficient for N=2 LAN nodes?

**Why it matters:** 
- Seq overflow → T7 monotonic apply gate might accept reordered observations as "newer" when old
- Example: seq=4294967294, next obs seq=0 (wrapped) — treated as newer = STATE REGRESS

**Decision options:**

| Option | Cost | Benefit | Risk | Phase |
|--------|------|---------|------|-------|
| **A: Keep uint32 (NO change)** | 0 | Simple, no code change | Wrap after 3,170 years; non-issue for practical deployments | Phase 1 ✅ |
| **B: Promote to uint64** | 10 min code | Extra safety margin (10^19 years wrap); future-proof | Over-engineered; negligible gain | Phase 1 ✅ |
| **C: Add wrap-detection** | 2h code + tests | Monitor seq delta; flag if >1000 (anomaly detection) | Overhead on hot path; rare event | Phase 1b |

**Recommendation:** **OPTION A** (keep uint32). Wrap is non-issue; time to v2 will far exceed wrap horizon.

**Decision:** ☐ A (keep uint32) ☐ B (promote uint64) ☐ C (add detection) → **User picks one**

---

## M2: Ghost-Peer Test Vector M1 (Witnesses + Proof)

**Problem:** D1 § 4 (TDD test) says:
```
Scenario: Ghost-peer (proof=0, witnesses=2)
Expected: confidence = 0.00
```

**Ambiguity:** If proof=0, can witness_set be non-empty? Multiplicative formula zeros confidence anyway.

**Why it matters:**
- Test fixture implementation depends on this
- Implementation must decide: do we validate `proof=0 ⟹ witnesses=[]` or allow witnesses even without proof?
- Affects schema validation rules

**Interpretations:**

| Interpretation | Meaning | Fixture Example | Impact |
|---|---|---|---|
| **A: Ghost = proof-less** | proof=0 always; witnesses ignored | `make_ghost_peer(proof=0, witnesses=[])` (ignore param) | Simple validation; proof is necessary condition |
| **B: Ghost = non-provable** | witnesses can exist; proof missing; score zeros anyway | `make_ghost_peer(proof=0, witnesses=[obs_1, obs_2])` (both present) | Flexible; separates proof requirement from witness agreement |

**Recommendation:** **OPTION B** (interpretation 2). Allows future enhancements (e.g., "low-proof, high-witness" states) without schema redesign.

**Decision:** ☐ A (ghost = no witnesses allowed) ☐ B (ghost = witnesses exist but proof=0 zeros score) → **User picks one**

---

## M3: StateTransitionManager Interface Protection Pattern

**Problem:** Should STM validate input or assume caller is trusted?

**Why it matters:**
- Affects error handling strategy
- If caller must validate, integration point is clear
- If STM validates, two code paths to maintain

**Options:**

| Option | Validation | Error Path | Cost | Maintenance |
|---|---|---|---|---|
| **A: Defensive (validate)** | STM checks input | Raise ValueError with diagnostic | +30 LOC + tests | Two paths; more complex |
| **B: Trust (no validation)** | Caller validates | Caller handles validation | 0 LOC | One path; silent bugs if caller fails |
| **C: Hybrid (optional gate)** | Hook function | Caller can enable/disable | +50 LOC | Flexible; config-dependent behavior |

**Recommendation:** **OPTION B** (trust caller). Validation happens once at call site. Simpler for Phase 1; add defensive checks in Phase 1b if bugs emerge.

**Decision:** ☐ A (validate in STM) ☐ B (trust caller) ☐ C (optional hook) → **User picks one**

---

## M4: Checkpoint Gate Criteria (1.0–1.3)

**Problem:** D1 § 6 lists 4 checkpoints but doesn't define acceptance gate. Example:
- "Checkpoint 1.0: Schema Alignment + Confidence" — schema landed? tests passing? both?

**Why it matters:**
- Determines when Phase 1 tasks can start
- Affects parallel vs sequential task scheduling
- Determines definition of "ready for Phase 1"

**Gate criteria options (per checkpoint):**

| Checkpoint | Must-Have (blocks Phase 1) | Nice-to-Have (Phase 1b) | Acceptance Metric |
|---|---|---|---|
| **1.0 Schema + Confidence** | Schema compiles; formula exists; M1 test (ghost-peer) passes | All M1–M5 tests passing; code review clean | "Confidence formula implemented + 1/5 tests pass" OR "5/5 tests pass" |
| **1.1 Confidence Wired** | compute_confidence() method exists; Batch 7 regression tests written | All 5 tests passing | "Method exists + tests exist" OR "5/5 tests green" |
| **1.2 Witness + Hysteresis** | StateTransitionManager class exists; promote/demote methods defined | All STM tests passing; edge cases E1–E10 covered | "Methods exist" OR "E1–E5 pass" OR "E1–E10 pass" |
| **1.3 Epoch + T7** | Monotonic apply guard implemented; T7 edge cases defined | E6–E10 tests passing; order-independence verified | "Guard exists" OR "E1–E10 pass" |

**Recommendation:** **Phased acceptance:**
- Checkpoint 1.0: "Schema compiles + formula exists + M1 (ghost-peer) passes" (soft gate → Phase 1 can start)
- Checkpoint 1.1: "Batch 7 regression tests 3/5 passing" (medium gate → Phase 1.1 start)
- Checkpoint 1.2: "STM promote/demote + edge cases E1–E5 pass" (firm gate)
- Checkpoint 1.3: "T7 monotonic gate + E6–E10 pass" (complete gate)

This enables **parallel task execution:** Phase 1.0 tasks start after Checkpoint 1.0 (soft); Phase 1.1 tasks wait for 1.1, etc.

**Decision for each checkpoint:** ☐ Soft (method exists) ☐ Medium (half tests pass) ☐ Firm (all tests pass) → **User picks per checkpoint**

---

## M5: Discovery Fallback Order & Parallelization

**Problem:** D2 § 3 (Detection SLA) assumes peer discovery is fast, but details deferred. Questions:
- mDNS first, then static seeds, then gossip?
- Serial or parallel?
- Timeout per strategy?

**Why it matters:**
- 40–90s SLA depends on peer discovered in ~10–20s (leaving rest for observation collection)
- Serial strategy: mDNS 3s + seeds 5s × N = 8–15s total
- Parallel strategy: mDNS || seeds = 3–5s (fast path)

**Options:**

| Option | Strategy | Timeout | Parallelization | Time Budget | Architecture |
|---|---|---|---|---|---|
| **A: Serial (simple)** | mDNS → seeds → gossip | 3s + 5s×N + 5s | None | ~15s total | Simple; blocking calls |
| **B: Parallel (async)** | mDNS \|\| seeds, winner takes all | 3s (fast path) or 8s (all fail) | 2-way parallel | ~8s max | Async threads/await; cleaner SLA |
| **C: Cascading parallel** | mDNS \|\| seeds → gossip if both fail | 3s (fast) or 8s + 5s (slow) | 2-way then 1-way | ~13s worst case | Hybrid; progressive fallback |

**Recommendation:** **OPTION B** (parallel mDNS + seeds). Achieves 3s median, 8s worst-case; SLA-compliant; enables async architecture.

**Implementation hint:** Use `asyncio.gather()` or `Promise.race()` depending on language. Gossip added only if both fail (rare).

**Decision:** ☐ A (serial, simple) ☐ B (parallel, SLA-compliant) ☐ C (cascading) → **User picks one**

---

## M6: Per-Epoch Replay Dedup Cache Eviction (T3)

**Problem:** T3 (Replay Attack) stores `(witness_id, nonce)` tuples to prevent replay. When epoch advances, what happens to old tuples?

**Why it matters:**
- Unbounded cache = memory DoS vector (attacker sends unique nonces, cache bloats)
- Clearing old tuples when epoch advances saves memory but risks replay in new epoch

**Dedup key scope:**

| Scope | Key Format | Epoch Behavior | Memory | Replay Protection |
|---|---|---|---|---|
| **A: Epoch-independent** | `(witness_id, nonce)` | Nonce globally unique forever | Unbounded | Protects across all epochs; DoS risk |
| **B: Epoch-scoped** | `(witness_id, epoch, nonce)` | Nonce reusable in new epoch | Linear with time | Protects within epoch; reuse ok after epoch change |

**Cache eviction strategies:**

| Strategy | Keep Window | Memory Bound | Replay Horizon | Complexity |
|---|---|---|---|---|
| **1: Keep forever** | All | Unbounded | ∞ | Low; one hash set |
| **2: Rotate per epoch** | Last 2 epochs | ~2× per epoch | ~20s (2×10s) | Medium; two sets + rotation |
| **3: LRU with watermark** | Last 90s | Bounded by time | 90s | Medium; LRU + eviction timer |

**Recommendation:** **Scope B + Strategy 2** (epoch-scoped key, rotate per epoch). Trade-off: replay protection good (within 20s window), memory bounded, simpler than LRU.

**Decision:** 
- Scope: ☐ A (global nonce) ☐ B (epoch-scoped nonce) 
- Eviction: ☐ 1 (keep forever) ☐ 2 (rotate per epoch) ☐ 3 (LRU + watermark)
→ **User picks one from each**

---

## M7: Rate Limiting Adaptive Tuning (T5 — DoS Flooding)

**Problem:** D4 § T5 specifies static token bucket parameters (R obs/s sustained, B burst), but real systems need adaptation. Should rate limits adjust based on load?

**Why it matters:**
- Static limits are conservative; unnecessary drop of legitimate observations when system has headroom
- Adaptive limits maximize throughput while protecting against floods

**Options:**

| Option | Rate Behavior | Burst Behavior | Complexity | Throughput | Phase |
|---|---|---|---|---|---|
| **A: Static (simple)** | R = 100 obs/s (constant) | B = 200 (constant) | Low; no tuning | 100 obs/s sustained | Phase 1 ✅ |
| **B: Adaptive (reactive)** | R ∈ [50, 200] obs/s; increase if queue<10 for 30s; decrease if queue>100 for 5s | B = 2×R (dynamic) | Medium; feedback loop + bounds | 100–200 obs/s; higher peak | Phase 1b |
| **C: ML-based (advanced)** | ML model predicts optimal R based on load history | Learned burst pattern | High; model training + inference | Optimal (data-driven) | v2 research |

**Recommendation:** **Phase 1 = Option A** (static R=100, B=200); **Phase 1b = add Option B** (adaptive tuning heuristics). ML-based deferred to v2.

**Decision:** ☐ A (static Phase 1 only) ☐ B (static Phase 1, adaptive Phase 1b) ☐ C (ML research v2) → **User picks one**

---

## Summary: Decision Checklist

**Quick format for user input:**

```
M1 Sequence bit-width:           [A] Keep uint32 / [B] uint64 / [C] detect wrap
M2 Ghost-peer witnesses:          [A] No witnesses / [B] Witnesses ok, proof=0 zeros score
M3 STM validation:                [A] Validate in STM / [B] Trust caller / [C] Optional hook
M4 Checkpoint 1.0 gate:           [soft/medium/firm] (schema compiles + 1 test / 3/5 tests / 5/5 tests)
M4 Checkpoint 1.1 gate:           [soft/medium/firm]
M4 Checkpoint 1.2 gate:           [soft/medium/firm]
M4 Checkpoint 1.3 gate:           [soft/medium/firm]
M5 Discovery strategy:            [A] Serial / [B] Parallel / [C] Cascading
M6 Replay dedup scope:            [A] Global nonce / [B] Epoch-scoped nonce
M6 Cache eviction:                [1] Forever / [2] Rotate per epoch / [3] LRU + watermark
M7 Rate limiting:                 [A] Static Phase 1 / [B] Static + Adaptive Phase 1b / [C] ML v2
```

---

## Rationale Summary

| Item | Recommendation | Urgency | Rationale |
|---|---|---|---|
| **M1** | Option A (uint32) | Low | Wrap horizon (3000 years) far exceeds product lifetime; no code needed |
| **M2** | Option B (witnesses allowed) | Medium | Flexibility for future enhancements; test vector works either way |
| **M3** | Option B (trust) | Low | Simpler Phase 1; add defenses Phase 1b if needed |
| **M4** | Soft gates (1.0); firm gates (1.3) | High | Enables parallel Phase 1 tasks; blocks escalation on incomplete work |
| **M5** | Option B (parallel) | Medium | SLA-compliant; enables async architecture; ~3s median discovery |
| **M6** | Epoch-scoped + rotate | Medium | Memory-safe; sufficient replay protection (20s window) |
| **M7** | Static Phase 1, adaptive Phase 1b | Low | Conservative start; add tuning as feedback emerges |

**Total decision time:** ~30 minutes (format: yes/no/defer per item)  
**Phase 1 impact:** M1–M7 are all Phase 1 optional; no blockers if deferred

