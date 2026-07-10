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
| **A: Keep uint32 + modular comparison** | Add tests | Simple wire format; explicit wrap behavior | Wrap after ~1,362 years at 10s intervals; MAX→0 and 0→MAX cases must be pinned | Phase 1 ✅ |
| **B: Promote to uint64** | 10 min code | Extra safety margin (10^19 years wrap); future-proof | Over-engineered; negligible gain | Phase 1 ✅ |
| **C: Add wrap-detection** | 2h code + tests | Monitor seq delta; flag if >1000 (anomaly detection) | Overhead on hot path; rare event | Phase 1b |

**Recommendation:** **OPTION A** (keep uint32 + modular comparison tests). Wrap is operationally remote, but the monotonic gate must define MAX→0 and 0→MAX behavior explicitly.

**Decision:** ☐ A (keep uint32) ☐ B (promote uint64) ☐ C (add detection) → **User picks one**

---

## M2: Ghost-Peer Test Vector M1 (Witnesses + Proof)

**Problem:** D1 § 4 (TDD test) says:
```text
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

**Problem:** STM is the authority that mutates counters and state. It must validate observation inputs before counter mutation, even if callers also validate earlier.

**Why it matters:**
- Affects error handling strategy
- Caller-side validation can remain an optimization
- STM validation is the final security gate for monotonicity, freshness, replay/deduplication, and valid observation type

**Options:**

| Option | Validation | Error Path | Cost | Maintenance |
|---|---|---|---|---|
| **A: Mandatory STM validation** | STM checks every observation before mutation | Reject/raise with diagnostic | +tests | Authoritative, safe Phase 1 gate |
| **B: Trust caller** | Caller validates only | Caller handles validation | 0 LOC | Rejected for Phase 1; silent state corruption risk |
| **C: Hybrid hook** | Optional pre-validation hook plus mandatory STM checks | Hook can enrich diagnostics | +integration | Phase 1b extension only |

**Recommendation:** **OPTION A** (mandatory STM validation). Caller-side validation may reduce errors earlier, but it cannot replace STM's own checks.

**Decision:** ☑ A (validate in STM) ☐ B (trust caller; rejected for Phase 1) ☐ C (optional hook later)

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
| **1.0 Schema + Confidence** | Schema and immutable field normalization landed; all schema fixture tests M1–M5 pass; mutable inputs copied/frozen | Additional fixture volume beyond blocker set | All blocker vectors pass |
| **1.1 Confidence Wired** | `compute_confidence()` wired into PeerObservation; all Batch 7 multiplicative tests pass; zero-proof never produces non-zero confidence | Threshold tuning and UX labels | 5/5 Batch 7 tests green |
| **1.2 Witness + Hysteresis** | STM integrated; all hysteresis, recovery, validation, witness-quorum, and counter-reset tests pass | Telemetry dashboards and adaptive tuning | Required STM vectors plus E1–E10 green |
| **1.3 Epoch + T7** | Epoch, sequence, nonce, and T7 monotonic apply gate implemented; all E1–E10 edge cases pass, including mid-batch threshold transitions | Longer fuzz/property-test runs | Full blocker edge-case suite green |

**Recommendation:** **Firm acceptance for every blocker gate.**
- Checkpoint 1.0: all schema fixture blockers pass
- Checkpoint 1.1: all Batch 7 confidence regressions pass
- Checkpoint 1.2: all STM validation/hysteresis/quorum vectors pass
- Checkpoint 1.3: all epoch/T7 edge cases E1–E10 pass

Parallel task execution is allowed only for independent implementation work. A checkpoint is not complete until its full blocker-specific gate passes.

**Decision for each checkpoint:** ☑ Firm (all blocker-specific vectors pass)

---

## M5: Discovery Fallback Order & Parallelization

**Problem:** D2 § 3 (Detection SLA) assumes peer discovery is fast, but details deferred. Questions:
- mDNS first, then static seeds, then gossip?
- Serial or parallel?
- Timeout per strategy?

**Why it matters:**
- 30–90s failure-state SLA depends on peer discovered in ~10–20s (leaving rest for observation collection)
- Serial strategy: mDNS 3s + static seeds 5s × N + gossip timeout; unbounded N risks SLA drift
- Parallel strategy: mDNS || seeds = 3–5s (fast path)

**Options:**

| Option | Strategy | Timeout | Parallelization | Time Budget | Architecture |
|---|---|---|---|---|---|
| **A: Serial (simple)** | mDNS → seeds → gossip | 3s + 5s×N + 5s | None | Depends on seed count | Simple; blocking calls |
| **B: Parallel (async)** | mDNS \|\| seeds, winner takes all | 3s (fast path) or 8s (all fail) | 2-way parallel | ~8s max | Async threads/await; cleaner SLA |
| **C: Cascading parallel** | mDNS \|\| seeds → gossip if both fail | 3s (fast) or 8s + 5s (slow) | 2-way then 1-way | ~13s worst case | Hybrid; progressive fallback |

**Recommendation:** **OPTION B** (parallel mDNS + bounded seed probes). Achieves ~3s median and bounded aggregate fallback; SLA-compliant for multiple configured seeds.

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

```text
M1 Sequence bit-width:           [A] Keep uint32 / [B] uint64 / [C] detect wrap
M2 Ghost-peer witnesses:          [A] No witnesses / [B] Witnesses ok, proof=0 zeros score
M3 STM validation:                [A] Validate in STM (mandatory)
M4 Checkpoint 1.0 gate:           [firm] all blocker-specific vectors pass
M4 Checkpoint 1.1 gate:           [firm] all blocker-specific vectors pass
M4 Checkpoint 1.2 gate:           [firm] all blocker-specific vectors pass
M4 Checkpoint 1.3 gate:           [firm] all blocker-specific vectors pass
M5 Discovery strategy:            [A] Serial / [B] Parallel / [C] Cascading
M6 Replay dedup scope:            [A] Global nonce / [B] Epoch-scoped nonce
M6 Cache eviction:                [1] Forever / [2] Rotate per epoch / [3] LRU + watermark
M7 Rate limiting:                 [A] Static Phase 1 / [B] Static + Adaptive Phase 1b / [C] ML v2
```

---

## Rationale Summary

| Item | Recommendation | Urgency | Rationale |
|---|---|---|---|
| **M1** | Option A (uint32 + modular tests) | Low | Wrap horizon is ~1,362 years at 10s intervals; explicit MAX→0 / 0→MAX behavior avoids ambiguity |
| **M2** | Option B (witnesses allowed) | Medium | Flexibility for future enhancements; test vector works either way |
| **M3** | Option A (mandatory STM validation) | High | STM is the authoritative mutation gate; caller validation cannot replace it |
| **M4** | Firm gates for 1.0–1.3 | High | Prevents partial blocker clearance and stale Phase 1 scheduling |
| **M5** | Option B (parallel) | Medium | SLA-compliant; enables async architecture; ~3s median discovery |
| **M6** | Epoch-scoped + rotate | Medium | Memory-safe; sufficient replay protection (20s window) |
| **M7** | Static Phase 1, adaptive Phase 1b | Low | Conservative start; add tuning as feedback emerges |

**Total decision time:** ~30 minutes (format: yes/no/defer per item)  
**Phase 1 impact:** M1–M7 are all Phase 1 optional; no blockers if deferred
