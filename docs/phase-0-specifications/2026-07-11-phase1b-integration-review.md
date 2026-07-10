# Phase 1b Integration Review — G1/G4/G6/G8 vs. Spec

**Date:** 2026-07-11 · **Reviewer:** Claude Sonnet 5 (direct — agy/gemini-coder
blocked on unauthenticated antigravity OAuth, see coordination log)
**Scope:** the four merged Phase 1b security-gap implementations
(`orchestrator/{provenance,equivocation,distance_bucket,audit_log}.py`)
checked against MULTIAGENT-SWARM-SECURITY-ANALYSIS.md's spec AND against
each other for real cross-module integration, not just individual
correctness (each module's own tests already verify that in isolation).

---

## Per-module: meets its own spec ✅

All four verified independently correct against their G-gap description:

| Module | Gap | Tests | Verified |
|---|---|---|---|
| `provenance.py` | G1 (P5) | 8/8 | Subnet-bucket dedup, wired into `witness_quorum.py` |
| `equivocation.py` | G4 (P13) | 5/5 | Same-provenance contradiction detection, bounded eviction |
| `distance_bucket.py` | G6 (P2) | 14/14 | XOR metric (docstring math fixed pre-merge), k-bucket LRU |
| `audit_log.py` | G8 (P19) | 11/11 | Hash-chain-by-reference, tamper detection |

## Cross-module integration: real gap found ⚠️

**Only `provenance.py` is actually consumed by anything else in the
codebase.** `witness_quorum.py` imports and calls `provenance_bucket()` —
genuine end-to-end wiring. Grepped the entire `orchestrator/` tree for
callers of the other three:

```
equivocation.py    → 0 callers outside its own file/tests
distance_bucket.py → 0 callers outside its own file/tests
audit_log.py       → 0 callers outside its own file/tests
```

**Root cause, not a bug in any of the four modules:** the orchestration
layer they're meant to plug into — `StateTransitionManager`
(`_apply_observation()`, `detector.evaluate()`) — **only exists as
pseudocode** in `DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md`. It has
never been implemented as real Python. There is currently no code path
anywhere in this repo that constructs a `PeerObservation` end-to-end and
runs it through quorum → equivocation → audit logic in sequence — each
piece is a correct, tested, standalone capability waiting for a caller.

This is not a defect in G1/G4/G5/G6/G8 individually — building the STM
pipeline was never their scope. It IS the next real integration task, and
should be tracked explicitly rather than assumed-done because the pieces
exist.

## Where each SHOULD plug in, once StateTransitionManager is implemented

Per DELIVERABLE-2 §5.3's `_apply_observation()` pseudocode and this review:

1. **Ingest** → `equivocation.py`'s `EquivocationLog.record_observation()`
   first (cheapest, catches malicious relays before wasting quorum work)
2. **Quorum gate** → `witness_quorum.py`'s `validate_witness_quorum()`
   (already correctly uses `provenance_bucket()` internally)
3. **Reputation weighting** → G5 (in progress, this session) should feed
   `reputation_weight(observer_id)` into the quorum vote weighting, not
   just a binary pass/fail
4. **Sybil correlation** → `distance_bucket.py`'s `KBucketTable` should be
   consulted alongside provenance bucketing — two SEPARATE Sybil signals
   (network origin vs. ID-space correlation), not currently cross-checked
   against each other even at the design level
5. **State transition committed** → `audit_log.py`'s `AuditLog.append()`
   records the outcome (only after, not before — audit logs decisions,
   not raw observations)

## Recommendation

Do not implement `StateTransitionManager` speculatively in this pass — it's
a genuinely separate, larger task (state machine + hysteresis + the
asymmetric-reachability logic from DELIVERABLE-2 §4) that deserves its own
scoped session, not a rushed bolt-on to this review. Flagging it explicitly
here so "Phase 1b security gaps: done" doesn't quietly imply "integrated:
done" when it isn't yet.

## Related

- [MULTIAGENT-SWARM-SECURITY-ANALYSIS.md](MULTIAGENT-SWARM-SECURITY-ANALYSIS.md) — G1-G16 gap definitions
- [DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md](DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md) §5.3 — the pseudocode these modules should be called from
- `scripts/agent_coordination.py list` — live claim board
