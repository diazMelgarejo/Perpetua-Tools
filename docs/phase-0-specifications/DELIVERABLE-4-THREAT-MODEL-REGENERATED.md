# Deliverable 4 — Threat Model (T1–T7, Regenerated)

**System context:** Distributed peer observation network where relays forward peer state observations carrying `{epoch, timestamp, proof, witness_set}`. Downstream consumers compute a **multiplicative confidence score** — any factor collapsing to ~0 collapses the whole score.

---

## T1 — Malicious Relay (forged / cherry-picked observations)

**Scenario.** A relay is compromised or adversarial. It fabricates observations or selectively drops/reshapes genuine ones, attaching plausible proofs, to drive a victim consumer's confidence in false peer state up or down.

**Current impact.** High. A single relay can unilaterally manufacture a "trusted" observation.

**Phase 0 mitigation — Proof diversity + witness quorum (NEW).**
- **Proof diversity requirement.** An observation is only admissible if supporting proofs originate from **≥ 2 independent proof sources** (distinct signing identities *and* distinct network provenance). `f_proof_diversity → 0` when all proofs trace to one origin, zeroing the confidence product.
- **Witness quorum ≥ 2.** Require at least two independent witnesses to co-sign a peer observation before it contributes to state.
- **Quorum check on aggregation.** Confidence is only emitted when both diversity + witness gates pass; failing either short-circuits to "insufficient evidence."

**Phase 1b enhancement.** Cryptographic path attestation — each relay hop signs a transcript so the full forwarding chain is verifiable end-to-end.

---

## T2 — Stale Peer (expired / superseded state accepted as current)

**Scenario.** An attacker replays a genuine but outdated observation whose state has since changed, causing a consumer to act on stale state.

**Current impact.** Medium-High. Epoch-only checks are beaten by same-epoch replay with old timestamp; timestamp-only checks are beaten by clock skew.

**Phase 0 mitigation — Dual freshness gate.**
- **Compare BOTH epoch AND timestamp.** An observation is fresh only if `epoch ≥ current_known_epoch` **AND** `timestamp` falls within the acceptance window for that epoch. Both must pass.
- **Epoch–timestamp consistency binding.** Reject observations whose timestamp contradicts the claimed epoch's known time bounds.

**Phase 1b enhancement.** Signed epoch checkpoints with bounded validity; per-peer freshness SLAs; drift-corrected timestamps via witness-median time.

---

## T3 — Replay Attack (valid observation re-injected out of original context)

**Scenario.** Attacker captures a valid, correctly-signed observation and re-injects it later to inflate witness counts or resurrect a past state.

**Current impact.** Medium. Replayed copies masquerade as independent corroborations.

**Validity under multiplicative formula:** VALID. Replayed copies collapse to a single distinct `(witness_id, nonce)` and contribute **once** to quorum, not N times.

**Phase 0 mitigation.** Per-observation nonce + monotonic sequence number scoped to `(peer, epoch)`; consumers cache seen `(witness_id, nonce)` tuples and discard duplicates.

**Phase 1b enhancement.** Bloom-filter-backed replay cache with epoch-rotating salt; bind observations to consumer-supplied challenge for pull paths.

---

## T4 — Sybil Witnesses (one adversary, many identities)

**Scenario.** Attacker spins up many pseudonymous witness identities to satisfy witness-quorum requirement alone, defeating "≥ 2 independent witnesses."

**Current impact.** Medium-High. Cheap identities let one entity fabricate a quorum.

**Validity under multiplicative formula:** VALID, tightened by T1's diversity gate. Quorum-by-count is only as strong as identity independence; T1's "distinct signing identity AND distinct network provenance" rule makes T4 fail — co-located Sybils collapse to one provenance.

**Phase 0 mitigation.** Witness independence scoring: dedupe quorum members by network-provenance class (ASN/subnet/origin) before counting.

**Phase 1b enhancement.** Stake- or proof-of-work-gated witness admission; reputation decay for correlated witnesses; graph-based collusion detection.

---

## T5 — Flooding / Denial of Service (observation volume exhaustion)

**Scenario.** Attacker floods relays/consumers with high volumes of observations to exhaust CPU on proof verification, memory on replay/witness caches, or bandwidth.

**Current impact.** Medium. Proof verification is the expensive path; unbounded inbound rate converts cheap sends into expensive verifies (asymmetric DoS).

**Validity under multiplicative formula:** VALID. DoS is availability, not integrity.

**Phase 0 mitigation — Rate limiting (detailed).**
- **Per-source token bucket.** Sustained `R` obs/s, burst `B`; over-budget observations dropped *before* proof verification.
- **Tiered limits.** Separate buckets for unauthenticated vs. reputable witnesses.
- **Cost-ordered pipeline.** Syntax → rate/quota → dedup → freshness → expensive proof-diversity and signature verification. Malformed/duplicate/stale floods shed early.
- **Bounded caches with eviction.** Replay and witness caches are size-capped with epoch-scoped eviction.
- **Backpressure.** When buckets saturate, emit "degraded/insufficient-evidence" signal rather than blocking.

**Phase 1b enhancement.** Adaptive rate limits driven by system load and per-source reputation; proof-of-work puzzles from sources whose recent traffic was mostly rejected.

---

## T6 — Confidence Inflation / Eclipse (starving a consumer of honest observations)

**Scenario.** Attacker surrounds a target consumer (eclipse) or floods it with low-quality-but-admissible observations so the honest minority is drowned out.

**Current impact.** Medium-High. Even with per-observation gates, *aggregate* bias is possible if all intake paths are attacker-controlled.

**Validity under multiplicative formula:** VALID — **this is the key defense.** Because the score is a **product of bounded factors**, extra low-quality observations cannot push confidence past the ceiling set by the weakest factor. Quantity alone does not inflate confidence — attacker must raise *every* factor simultaneously, which T1/T2/T4 gates independently block.

**Phase 0 mitigation.** Require intake-path diversity (observations from ≥ 2 disjoint network paths); cap marginal contribution of same-origin observations; keep score product-based.

**Phase 1b enhancement.** Path-diverse peer sampling; anchor witnesses (known-good reference observers); anomaly detection on honest/attacker ratio to trip fail-safe when intake diversity collapses.

---

## T7 — Out-of-Order Observations (**NEW**)

**Scenario.** Observations for the same peer arrive in an order different from generation order — due to multi-path relay latency, per-relay buffering, or deliberate attacker reordering. Example: newer `O2 (epoch 5, t=100)` arrives, then older `O1 (epoch 4, t=90)` arrives late. A consumer applying observations in arrival order lets the late `O1` overwrite state established by `O2`, regressing the peer to an older epoch.

**Current impact.** Medium-High. Per-observation freshness gate (T2) does **not** fully close this: T2 rejects observations stale *relative to current known state at ingest*, but out-of-order arrival can pass T2 at evaluation time, then later be dropped as "duplicate epoch" or clobber newer state. Result: non-deterministic, order-dependent peer state.

**Phase 0 mitigation — Monotonic apply gate.**
- **Peer state advances only under strict ordering key** `(epoch, sequence, timestamp)` (sequence is canonical causality, timestamp is advisory only; accept ±30s clock skew within an epoch); incoming observation is applied **only if** its key is `>` the last-applied key. Late-arriving older observations are acknowledged (T3 dedup) but **cannot regress** state — recorded, not applied.
- **Reorder buffer with watermark.** Hold observations in short bounded window keyed on `(epoch, timestamp)`; release in canonical order once watermark passes. Transient multi-path skew is absorbed, not acted on.
- **Idempotent, order-independent aggregation.** Confidence for an epoch computed from *set* of admissible observations, not arrival-order mutation — two consumers with same observation set converge regardless of order.
- **Composes with T2:** T2 decides *admissibility* (fresh vs. stale); T7 decides *apply order* (monotonic, non-regressing) — both gates run.

**Phase 1b enhancement.** Vector-clock / Lamport-timestamped observations so causal order is explicit; consumer-side conflict resolution flagging genuine epoch forks for quorum arbitration instead of last-writer-wins; adaptive reorder-window sizing driven by measured per-path latency.

---

## Summary Matrix

| ID | Threat | Key Phase 0 gate | Multiplicative-formula status |
|----|--------|------------------|-------------------------------|
| T1 | Malicious relay | Proof diversity (≥2) + witness quorum ≥2 | Gate feeds `f_proof_diversity`, `f_witness_quorum` |
| T2 | Stale peer | Dual freshness: **epoch AND timestamp** + consistency binding | Feeds `f_recency` × `f_epoch_agreement` jointly |
| T3 | Replay | Nonce + `(peer,epoch)` dedup cache | VALID — distinct-witness count, no inflation |
| T4 | Sybil witnesses | Provenance-deduped independence scoring | VALID — tightened by T1 diversity gate |
| T5 | Flooding / DoS | Per-source token buckets, cost-ordered pipeline, bounded caches, backpressure | VALID — availability layer protecting integrity gates |
| T6 | Inflation / eclipse | Intake-path diversity + product-based cap | VALID — product shape caps at weakest factor |
| T7 | **Out-of-order (NEW)** | Monotonic `(epoch,timestamp,seq)` apply gate + reorder buffer + set-based aggregation | VALID — order-independent convergence |

---

*End of Deliverable 4. All threats T1–T7 mitigated. Ready for Phase 1 implementation.*
