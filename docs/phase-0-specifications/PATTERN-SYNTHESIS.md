# P2P Security Pattern Synthesis — 20 Battle-Tested Patterns for OpenClaw Swarm Orchestration

**Navigation:** ← [task list](PHASE-0-TASK-LIST.md) · informs: [D1 PeerObservation](DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md) · [D4 threat model](DELIVERABLE-4-THREAT-MODEL-REGENERATED.md) · → feeds: [Phase 1 scope](PHASE-1-SCOPE-DRAFT.md) (P19/P20 Phase 1b enhancements)

**Research scope:** BitTorrent/DHT (Kademlia), Gossip protocols (SWIM, Hyparview), Distributed consensus (RAFT, BFT), Proof-of-Work blockchains (Bitcoin), Zero-Trust security (mTLS).

**Validation:** Each pattern has been battle-tested in production systems with millions of nodes or terabytes of data. Patterns are ranked by relevance to Phase 0 threat model (T1–T7).

---

## Layer 1: Peer Discovery & Identity Binding

### P1. Proof-Anchored Identity (Source: Kademlia DHT, Bitcoin)
**Principle:** Every peer claim carries a cryptographic proof; identity is unforgeable.  
**Mechanism:** Peers publish a (peer_id, endpoint, signature) tuple where signature proves the peer controls the private key associated with peer_id. Relayed claims must carry the **original peer's signature**, not the relay's re-signature.  
**Threat defended:** T1 (Malicious relay fabricating observations), T4 (Sybil witness creation).  
**Cost:** One Ed25519 signature per observation (0.6ms on modern CPU); 64-byte signature overhead.  
**Swarm application:** Every peer_observation must be signed by the *observing peer*, not the relay. Relays forward the original signature as immutable proof. Prevents relay mutation attacks.  
**PT implementation status:** ✅ Implemented (D1: `relay_proof` + signature requirement).  
**Phase 1b enhancement:** Threshold signatures from N peers for multi-authority state (e.g., "LM Studio went offline" requires 2+ independent witness signatures).

---

### P2. Distance-Metric-Based Bucketing (Source: Kademlia DHT)
**Principle:** Organize peer routing into distance-based buckets; contact distribution correlates with probability of reaching them.  
**Mechanism:** Use XOR distance in peer ID space; partition peers into k-buckets (default k=20). Each bucket is ordered by last-seen time; new contacts go to the back. When bucket fills, evict the least-recently-seen peer after a liveness check (ping). This ensures high-confidence peers are reachable (checked actively) while low-confidence peers are backup-only.  
**Threat defended:** T4 (Sybil attack — many Sybils cluster in same address space, visible as same bucket), T5 (DoS — high-reachability peers are pinged first, low-confidence peers are sampled last).  
**Cost:** O(log N) lookup for peer discovery; O(1) per-bucket maintenance.  
**Swarm application:** OpenClaw swarms of ~3–100 nodes could use distance-based "active" vs. "passive" peer tables: Mac-primary observers in the active table (pinged frequently), transient or distant relays in passive table. Bucketing makes Sybil concentration visible: all Sybils from one attacker will have nearby IDs, failing diversity checks.  
**PT implementation status:** ⚠️ Partial (D1 confidence model doesn't explicitly use distance; membership is flat active/passive).  
**Phase 1b enhancement:** Introduce peer distance metric (Hamming distance in peer_id space); stratify active view by distance to catch Sybils with correlated IDs.

---

### P3. Challenge-Response Liveness Verification (Source: SWIM gossip protocol)
**Principle:** Before admitting a peer to the active view, verify it can respond to a direct challenge (e.g., echo challenge within RTT).  
**Mechanism:** Observer sends `challenge_nonce` to peer; peer must respond with signed `(challenge_nonce, observer_id, timestamp)` within expected latency window (e.g., 1–2 RTT). Stale or missing responses downgrade peer to passive view pending recovery.  
**Threat defended:** T1 (relay can't forge the response; target peer must be reachable), T2 (stale peer — no response means not currently online).  
**Cost:** One RTT per liveness check (~10–100ms LAN); amortized over probe interval (e.g., every 30s).  
**Swarm application:** PT's heartbeat mechanism already does this (D2). Enhance by embedding nonce in every heartbeat; require relay-forwarded heartbeats to **never** change the nonce, making forgery detectable.  
**PT implementation status:** ✅ Implemented (D2: heartbeat + probe_latency measurement).  
**Phase 1b enhancement:** Signed nonce binding per heartbeat; detect relay mutation by comparing witness nonce hashes.

---

### P4. Multi-Path Probe Diversity (Source: HyParView, modern Ethereum)
**Principle:** Always probe a peer via ≥2 disjoint network paths; compare responses for consistency.  
**Mechanism:** Maintain both a direct connection and a relay path to each active peer. If direct probe and relay probe return contradictory state, confidence drops to "insufficient evidence" and peer moves to passive pending resolution.  
**Threat defended:** T6 (Eclipse/inflation — attacker can't control all paths simultaneously), T1 (malicious relay detectable if it forges state inconsistent with direct probe).  
**Cost:** Extra probe messages per peer (~50% overhead on probe count); extra latency for relay path (~10–50ms depending on network).  
**Swarm application:** In OpenClaw's 3-layer (AlphaClaw L1, Perpetua-Tools L2, orama-system L3) hierarchy, ensure every critical peer state is observed via at least two independent paths: direct L1→L2 heartbeat AND gossip relayed through L3. Contradiction triggers quorum arbitration.  
**PT implementation status:** ⚠️ Partial (D1 models direct + relay observations, but no explicit multi-path contradiction logic).  
**Phase 1b enhancement:** Implement path-diversity scorer; maintain separate confidence tracks for direct vs. gossip path; require both to agree before state transition.

---

## Layer 2: Membership & Witness Quorum

### P5. Witness Quorum with Provenance Deduplication (Source: PBFT, HotStuff)
**Principle:** Require f+1 distinct witnesses (where f is Byzantine fault tolerance threshold) to agree on state; deduplicate by **network provenance** (ASN, subnet, data-center) not just peer_id.  
**Mechanism:** Each witness carries (peer_id, ip_address, asn). When aggregating witness votes, deduplicate by ASN first: if 10 witnesses all originate from ASN 65000, count as **one logical witness** for quorum purposes. This breaks Sybil attacks where one entity spins up many identities on the same network.  
**Threat defended:** T4 (Sybil witnesses — attacker can't easily acquire diverse ASN/subnet), T1 (quorum forging requires control of multiple network segments, detectable by ASN clustering).  
**Cost:** WHOIS/GeoIP lookup per witness (~100ms cold, cached after); on-memory ASN dedup table (hundreds of bytes).  
**Swarm application:** OpenClaw swarm observing "LM Studio at 192.168.254.104 is online" requires ≥2 witnesses from different ASN/subnets. On a LAN, substitute "different physical machine" dedup key; on WAN, use ASN/datacenters.  
**PT implementation status:** ⚠️ Partial (D1 mentions "distinct network provenance" in T4 mitigation but doesn't formalize ASN/subnet dedup).  
**Phase 1b enhancement:** Implement peer GeoIP lookup on startup; maintain ASN-indexed witness table; reject observations where >50% of witnesses share ASN.

---

### P6. Reputation-Decay Witness Scoring (Source: Bitcoin, Ethereum peer scoring)
**Principle:** Each witness carries a reputation score that decays over time; new witnesses start at low score; correct predictions boost score; incorrect predictions drop it.  
**Mechanism:** Witness reputation `rep(w) = (correct_predictions - 5 × incorrect_predictions)` clamped to [0, 10]. Each observation from witness w is weighted by `rep(w) / 10` in quorum vote. Score updates daily; witnesses with rep < 0 are dropped from active witness set.  
**Threat defended:** T1 (malicious relay detectable — if relay forges N observations and >50% prove false, rep drops to negative, relay drops from quorum), T4 (Sybil witnesses — each starts at rep 0, must earn trust by being correct).  
**Cost:** Per-witness reputation maintenance (~64 bytes per witness); prediction accuracy tracking (negligible post-observation).  
**Swarm application:** Track per-witness prediction accuracy: does this witness's state observations agree with subsequent ground truth (e.g., actual heartbeat response)? Witnesses with <70% accuracy drift to passive view; >95% accuracy get boosted to priority.  
**PT implementation status:** ❌ Missing (D1 has no per-witness reputation model).  
**Phase 1b enhancement:** Implement witness reputation ledger; compute daily rolling accuracy; integrate into multiplicative confidence formula.

---

### P7. Asynchronous Member Notification (Source: SWIM gossip protocol)
**Principle:** Broadcast membership changes (ALIVE, SUSPECT, DEAD) asynchronously via randomized gossip fan-out; no quorum required for notification itself.  
**Mechanism:** When a peer's state changes (ACTIVE → SUSPECT), immediately gossip to `log(N)` random peers (e.g., 3 peers for N=8). Each peer forwards to another random set. This ensures O(log N) latency for event propagation even without quorum consensus; quorum gates apply only to state *acceptance*.  
**Threat defended:** T5 (DoS — gossip is push-based and doesn't require expensive consensus), T6 (partition resilience — isolated partition still receives gossip, can recover when partition heals).  
**Cost:** `log(N)` outgoing gossip messages per state change; O(log N) propagation latency; can be rate-limited to prevent cascade.  
**Swarm application:** When a critical peer (LM Studio, orchestrator) goes SUSPECT, notify all observers via gossip to drive fast failure detection. Quorum (P5) gates whether to mark INACTIVE; gossip ensures timely notification even if quorum membership is uncertain.  
**PT implementation status:** ⚠️ Partial (D1 describes relay forwarding, but not explicit `log(N)` gossip fan-out; more like broadcast relay).  
**Phase 1b enhancement:** Implement explicit gossip fan-out: each relay targets `ceil(log(N))` peers, avoiding re-forwarding to direct sender.

---

## Layer 3: State Synchronization & Consensus

### P8. Monotonic Sequence Numbering (Source: RAFT log replication, TCP sequence numbers)
**Principle:** Every state update carries a strictly increasing sequence number scoped to `(peer_id, epoch)`; consumers only apply updates with strictly higher sequence numbers.  
**Mechanism:** Peer maintains `seq_counter[peer_id][epoch]` initialized to 0. Every observation of that peer in that epoch increments counter; relay must not alter sequence. Consumer maintains `last_applied_seq[peer_id][epoch]`; only applies observation if its sequence > last applied sequence. Observation with duplicate or lower sequence is logged but not applied.  
**Threat defended:** T3 (Replay — duplicate sequence rejected), T7 (Out-of-order — monotonic sequence ensures apply order is causally consistent regardless of arrival order).  
**Cost:** 8 bytes per (peer, epoch) pair; comparison at apply time (negligible).  
**Swarm application:** Every peer observation carries `(peer_id, epoch, sequence_number)`. Reordered observations are held in a small reorder buffer and released in canonical sequence order, ensuring deterministic state machine across all observers.  
**PT implementation status:** ⚠️ Partial (D1 mentions nonce for T3 dedup, but sequence number for causal ordering is not formalized).  
**Phase 1b enhancement:** Explicitly encode `sequence_number` in observation schema; implement reorder buffer sorted by sequence; guarantee all consumers converge on same state given same observation set.

---

### P9. Epoch-Scoped Reorder Buffer (Source: TCP receive window, RAFT snapshotting)
**Principle:** Hold out-of-order observations in a bounded buffer sorted by `(epoch, sequence)` until watermark passes; release in canonical order.  
**Mechanism:** Maintain `reorder_buffer[peer_id] = SortedDict(key=(epoch,sequence))` capped at size 10. Incoming observation is added to buffer. Watermark = highest sequence yet *applied*. Release observations from buffer if their sequence ≤ watermark + 1 and epoch matches watermark epoch. This absorbs transient reordering (multi-path latency skew ~tens of ms) without regressing state.  
**Threat defended:** T7 (Out-of-order — watermark-based release ensures monotonic state progression), T5 (bounded buffer prevents DoS memory exhaustion).  
**Cost:** O(log B) insertion into reorder buffer (B ≈ 10); O(1) per-observation release check.  
**Swarm application:** When gossip relays carry observations with skewed timestamps (L2 relay slower than L1 direct), reorder buffer smooths the ingestion. Observations wait briefly; once watermark is established, old observations are discarded and only new ones are applied.  
**PT implementation status:** ❌ Missing (D1 mentions T7 monotonic apply gate, but no bounded reorder buffer is specified).  
**Phase 1b enhancement:** Implement per-peer reorder buffer; set max size to 5–10 observations; on buffer full, emit "reorder failure" alert for manual investigation.

---

### P10. Cryptographic Merkle Commit (Source: Bitcoin, Ethereum, PBFT snapshots)
**Principle:** Compute a Merkle root of all current peer state; sign it; require consumers to periodically verify root matches their local state hash.  
**Mechanism:** Every epoch, orchestrator computes `root = merkle_tree_root({peer_id: (epoch, status, timestamp)})` and signs it. Each observer maintains their own computed root. Mismatch triggers "state divergence alert" → manual inspection or state sync.  
**Threat defended:** T6 (Eclipse attack detectable — isolated observer's root will diverge from quorum root), data corruption in memory or logs.  
**Cost:** O(N log N) Merkle tree computation per epoch (e.g., 100 nodes → ~700 hash ops); negligible on modern CPU. Signature verification ~0.6ms per observer.  
**Swarm application:** At end of each observation epoch, orchestrator computes Merkle root of all peer states; signs and broadcasts. Each observer computes their own root; divergence is logged. Enables periodic audit of observation consistency.  
**PT implementation status:** ❌ Missing (no Merkle commitment in current D1 design).  
**Phase 1b enhancement:** Implement optional periodic Merkle audits; log divergence events; trigger state sync on persistent divergence.

---

### P11. Atomic Multi-Writer Consensus (Source: RAFT leader election, Paxos propose-accept-learn)
**Principle:** When multiple observers propose conflicting state updates (e.g., peer status), use quorum-consensus to pick one.  
**Mechanism:** Each observer proposing a state change sends `(peer_id, new_status, epoch, signature)` to a quorum. Quorum leader collects proposals for same (peer_id, epoch) pair; picks the one with highest ballot number or earliest timestamp (tiebreaker). Leader emits consensus decision to all observers; acceptance is acknowledged. Non-accepted proposals are retried.  
**Threat defended:** T1 (relay conflicts detectable via consensus), T7 (out-of-order updates resolved by quorum pick).  
**Cost:** Extra round-trip for consensus (50–200ms depending on network); reduces write latency by requiring quorum ack instead of immediate local apply.  
**Swarm application:** Critical state changes (e.g., marking LM Studio INACTIVE, or changing orchestrator leadership) require quorum consensus. Less critical updates (latency measurements) can apply immediately.  
**PT implementation status:** ⚠️ Partial (D1 has witness quorum, but no explicit multi-writer ballot / leader-based consensus).  
**Phase 1b enhancement:** Implement RAFT-lite leader election for critical state changes; quorum-driven final state machine.

---

## Layer 4: Byzantine Fault Tolerance & Adversarial Defense

### P12. Byzantine Fault Tolerance Threshold (f < N/3 or f < (N-1)/2)
**Principle:** System remains safe if ≤ f nodes are Byzantine (arbitrary faults); choice of threshold determines liveness.  
**Mechanism:** In asynchronous network (no bounds on message delays), safety requires f < N/3 (so 2f+1 honest nodes form quorum). In synchronous/partially-synchronous network, f < N/2 suffices. Quorum decisions require ≥ 2f+1 acks; any f Byzantine nodes can't block or forge consensus.  
**Threat defended:** All T1–T6 when f < (N-1)/2. T4 (Sybil) when combined with P5 (provenance dedup).  
**Cost:** Latency scales as number of rounds × quorum size. Asynchronous (N ≥ 3f+1) requires ≥3 rounds for consensus; synchronous (N ≥ 2f+1) requires ≥2 rounds.  
**Swarm application:** OpenClaw with ~3–10 core nodes and ~20–100 transient peers. Core = N=3–10; set f=1 (2f+1=3, 3f+1=4). Can tolerate 1 malicious core, 1 clock-skewed relay. Transient peers are low-trust; only core peers participate in critical quorum.  
**PT implementation status:** ✅ Designed (D4 implies f < N/3 via witness-quorum logic; not explicitly stated).  
**Phase 1b enhancement:** Formalize N_core and f_core; document minimum cluster size for consensus safety.

---

### P13. Equivocation Detection (Source: PBFT, Ethereum slashing, Bitcoin double-sign detection)
**Principle:** If a peer issues two conflicting signed statements for the same (epoch, view), it is *provably malicious* and can be slashed.  
**Mechanism:** Collect all signed observations from each peer. For each peer p and epoch e, check: do any two observations have contradictory status fields? If yes, log both signatures as proof of Byzantine behavior. This peer is immediately expelled from quorum; its reputation score is reset to minimum.  
**Threat defended:** T1 (relay lies detectable — if relay fabricates contradictory observations and signs both, both signatures become evidence of malice).  
**Cost:** Pairwise comparison of observations per peer per epoch (O(N) in number of unique observations).  
**Swarm application:** If AlphaClaw claims "LM Studio is REACHABLE" in one heartbeat and "LM Studio is UNREACHABLE" in the next (same epoch), both are signed. Contradiction is proof; AlphaClaw is demoted to low-trust witness pending investigation.  
**PT implementation status:** ⚠️ Partial (D1 tracks witness disagreement, but doesn't explicitly log equivocations as provable malice).  
**Phase 1b enhancement:** Maintain equivocation ledger; log peer_id + epoch + conflicting signatures; trigger automatic quorum expulsion.

---

### P14. Accusation & Slashing Protocol (Source: Ethereum 2.0, Cosmos)
**Principle:** Honest observers can formally accuse a Byzantine node and force it to post collateral (stake) or be evicted.  
**Mechanism:** Honest observer detects malice (e.g., equivocation, provably false observation after ground-truth revealed). Observer creates `Accusation{accused_peer_id, evidence_signatures[], epoch}`, broadcasts to quorum. Quorum votes: if ≥2f+1 votes accuse, accused peer is slashed (reputation → 0, evicted from active set). Slashing is irreversible per epoch.  
**Threat defended:** T1, T4 (malicious peers learn attacking is costly; rational actors avoid malice).  
**Cost:** Broadcast overhead per accusation (~1KB per accusation); quorum vote latency.  
**Swarm application:** If a relay is caught forwarding forged observations (detected via contradiction with direct probe), honest observers file accusation. After quorum vote, relay is demoted from active to passive, blocking its future observations.  
**PT implementation status:** ❌ Missing (no slashing mechanism in Phase 0).  
**Phase 1b enhancement:** Implement accusation protocol; define slashing rules (rep → 0, eviction for 1 epoch, re-admission requires manual approval).

---

### P15. Threshold Homomorphic Encryption for State Privacy (Source: Distributed key management, Shamir secret sharing)
**Principle:** Observations containing sensitive state (e.g., peer credentials, model weights) are encrypted under a threshold key; any 2 of 3 key-holders can decrypt, but no single holder can.  
**Mechanism:** Orchestrator generates private key K; shares it Shamir-secret-shared into K1, K2, K3 held by 3 trusted nodes. Observation is encrypted under K. To decrypt, any 2 of the 3 key-holders pool their shares; combined shares recover K, allowing decryption. No single key-holder can decrypt alone.  
**Threat defended:** T1 (relay can't decrypt encrypted observation even if forged), data exfiltration if any single observer is compromised.  
**Cost:** Encryption ~10µs per observation (AES-256-GCM); Shamir share aggregation ~100µs (once per epoch, amortized).  
**Swarm application:** Model weights, credentials, or loss metrics observed by AlphaClaw can be encrypted. Only quorum of core peers (N ≥ 3, f < N/3) can decrypt for auditing.  
**PT implementation status:** ❌ Missing (not in scope for Phase 0; research-only for v2).  
**Phase 1b enhancement:** Prototype threshold encryption for audit logs; evaluate CPU overhead on Win RTX3080 (target <5ms per 100 observations).

---

## Layer 5: Denial-of-Service & Rate Limiting

### P16. Token-Bucket Per-Source Rate Limiting (Source: TCP congestion control, Memcached, Redis)
**Principle:** Each observation source (relay, observer) has a token bucket; sustained rate R tokens/sec, burst B tokens. Observations cost tokens; when empty, observations are dropped before expensive processing.  
**Mechanism:** For each source_id, maintain bucket = {tokens, last_refill_time}. On inbound observation, check tokens ≥ cost. If yes, decrement and process; if no, drop. Periodically (every 100ms), refill: `tokens = min(B, tokens + R * time_delta)`. Cost scaling: malformed=0.1 token, duplicate=0.5, unverified=1.0, expensive-proof=3.0.  
**Threat defended:** T5 (DoS via flooding — bucket empties, requests dropped).  
**Cost:** O(1) per observation; per-source bucket is ~100 bytes; minimal CPU.  
**Swarm application:** Relays are rate-limited to 100 obs/sec sustained, 1000 obs/sec burst. Observers are rate-limited to 50 obs/sec sustained, 200 obs/sec burst. Transient peers capped lower (~10 obs/sec).  
**PT implementation status:** ✅ Designed (D4 mentions per-source token buckets).  
**Phase 1b enhancement:** Implement adaptive rate limits driven by system load (CPU, memory); boost limit for high-reputation witnesses.

---

### P17. Cost-Ordered Validation Pipeline (Source: Bitcoin transaction mempool, Kafka broker)
**Principle:** Validate observations in order of increasing CPU cost; drop cheap-to-verify failures early before expensive proof verification.  
**Mechanism:** For each observation:
1. **Syntax check** (1µs) — field types, ranges, lengths. Fail → drop (cost 0.01 token).
2. **Rate check** (0.1µs) — token bucket. Fail → drop, backpressure.
3. **Dedup check** (1µs) — cache lookup of (peer_id, nonce). Fail → drop (cost 0.5 token).
4. **Freshness check** (0.1µs) — epoch/timestamp comparison. Fail → drop (cost 0.5 token).
5. **Signature verification** (100µs) — expensive. Fail → drop (cost 3 tokens). **Only reached if 1–4 pass.**

**Threat defended:** T5 (DoS attacks exhausted on checks 1–4, never reach expensive verification).  
**Cost:** ~1ms per observation worst-case; median 0.1ms (fails early).  
**Swarm application:** PT observation ingestion uses cost-ordered pipeline: syntax → rate → dedup → freshness → proof verification. Malformed or replayed spam is shed before proof validation.  
**PT implementation status:** ✅ Designed (D4 describes pipeline; detailed implementation pending).  
**Phase 1b enhancement:** Instrument pipeline; log drop reason and cost per source; feed into reputation system.

---

### P18. Bounded-TTL Caches with Epoch Rotation (Source: Memcached, Redis eviction, Bloom filters)
**Principle:** Replay and witness caches are bounded; entries expire by TTL or epoch boundary; eviction follows LRU + age.  
**Mechanism:** Replay cache: `{(witness_id, nonce): [timestamp, epoch]}` ⊂ {}. Size capped at 10K entries. On insert, if size > 10K, evict oldest entry by timestamp. On query, if entry age > 1 epoch or entry epoch < current_epoch - 1, remove. Witness cache similar, but keyed on `witness_id`; evict if reputation score < 0 or age > 24h.  
**Threat defended:** T3 (Replay — old replays evicted), T5 (memory DoS — bounded caches), T4 (Sybil — old Sybil identities evicted).  
**Cost:** Cache maintenance ~1µs per operation; memory bounded (replay ~10MB, witness ~5MB).  
**Swarm application:** PT's dedup caches use epoch-scoped eviction: at epoch boundary, drop all entries from previous epoch. Reduces memory churn, ensures replay cache is never stale.  
**PT implementation status:** ✅ Designed (D1/D4 mention bounded caches; implementation pending).  
**Phase 1b enhancement:** Implement with Bloom filter as first pass (10KB, 1µs lookup) before hash table (avoid hash table misses).

---

## Layer 6: Observability & Audit Trails

### P19. Immutable Append-Only Audit Log (Source: Bitcoin blockchain, Ethereum logs, PostgreSQL write-ahead logs)
**Principle:** Every state change is logged to an immutable audit trail; log is cryptographically chained so tampering is detectable.  
**Mechanism:** Each log entry is `{sequence_number, timestamp, peer_id, old_status, new_status, witnesses, previous_hash, signature}`. Hash chain by **reference, not magnitude**: `entry[i].hash = SHA256(entry[i].previous_hash || entry[i])`, where `entry[i].previous_hash = entry[i-1].hash` (a cryptographic hash is uniformly distributed and has no meaningful numeric ordering — requiring `hash > previous_hash` would randomly reject ~50% of legitimate entries and provides zero tamper-evidence, since an attacker could simply re-hash with a different nonce until the magnitude condition happens to hold). Hash is signed by orchestrator. On audit, verify chain integrity by walking the chain: recompute each `entry[i].hash` from its content and confirm `entry[i].previous_hash == entry[i-1].hash`, then verify the signature independently.  
**Threat defended:** T1 (audit trail proves relay's actions), data corruption, forensic analysis of malice.  
**Cost:** Hash + sign per state change (~100µs), chain verification ~1µs per entry. Storage ~200 bytes per entry.  
**Swarm application:** PT maintains observation audit log: every state change (peer ACTIVE→SUSPECT), every witness vote, every accusation. Log is signed and committed to persistent storage. Enables post-incident forensics.  
**PT implementation status:** ⚠️ Partial (D1/D4 assume logging exists; audit log format not specified).  
**Phase 1b enhancement:** Implement hash-chained audit log; persistent storage (RocksDB or SQLite); periodic batch signing (per epoch).

---

### P20. Merkle-Proof Observability (Source: Ethereum light clients, certificate transparency logs)
**Principle:** For any past state change, a lightweight observer can request a cryptographic proof that the state change was included in the canonical log.  
**Mechanism:** Every epoch, orchestrator publishes `merkle_root = merkle_tree_root([state_change_1, ..., state_change_N])`. Each state change has a Merkle proof: `[sibling_hash_left, sibling_hash_right, ...]` allowing any observer to recompute root and verify the change was included. Proof size is O(log N).  
**Threat defended:** Censorship (observer can prove their observation was rejected from quorum), revisionism (observer can prove past state via immutable Merkle root + proof).  
**Cost:** Proof generation O(log N) per state change (~7 hashes for N=100); proof size ~224 bytes (7 × 32-byte hashes).  
**Swarm application:** After each epoch, PT publishes Merkle root of all observations. Any observer can request proof that their observation was included or why it was rejected. Enables transparent dispute resolution.  
**PT implementation status:** ❌ Missing (not in scope for Phase 0; research-only).  
**Phase 1b enhancement:** Prototype Merkle-proof observability; publish epoch root + inclusion proofs for disputed observations.

---

## Summary Table: 20 Patterns

| ID | Name | Source | Threat(s) | PT status | Effort (Phase 1b) |
|----|------|--------|-----------|-----------|-------------------|
| P1 | Proof-Anchored Identity | Kademlia, Bitcoin | T1, T4 | ✅ | Low — extend to threshold sigs |
| P2 | Distance-Metric Bucketing | Kademlia DHT | T4, T5 | ⚠️ | Medium — implement distance metric |
| P3 | Challenge-Response Liveness | SWIM | T1, T2 | ✅ | Low — formalize nonce binding |
| P4 | Multi-Path Probe Diversity | HyParView, Eth | T6, T1 | ⚠️ | High — refactor confidence tracking |
| P5 | Witness Quorum + Provenance Dedup | PBFT, HotStuff | T4, T1 | ⚠️ | Medium — integrate ASN lookup |
| P6 | Reputation-Decay Witness Scoring | Bitcoin, Eth | T1, T4 | ❌ | Medium — implement reputation ledger |
| P7 | Asynchronous Member Notification | SWIM | T5, T6 | ⚠️ | Medium — formalize log(N) gossip fan-out |
| P8 | Monotonic Sequence Numbering | RAFT, TCP | T3, T7 | ⚠️ | Low — add seq field to schema |
| P9 | Epoch-Scoped Reorder Buffer | TCP, RAFT | T7, T5 | ❌ | Medium — implement sorted buffer |
| P10 | Cryptographic Merkle Commit | Bitcoin, Eth | T6, data corruption | ❌ | Medium — optional periodic audits |
| P11 | Atomic Multi-Writer Consensus | RAFT, Paxos | T1, T7 | ⚠️ | High — implement leader election |
| P12 | BFT Threshold (f < N/3) | HotStuff, PBFT | T1–T6 | ✅ | Low — document formal bound |
| P13 | Equivocation Detection | PBFT, Eth2 | T1 | ⚠️ | Medium — log contradictions |
| P14 | Accusation & Slashing Protocol | Eth2, Cosmos | T1, T4 | ❌ | High — multi-phase protocol |
| P15 | Threshold Homomorphic Encryption | Shamir shares | T1, data exfil | ❌ | Very High — crypto research-only v2 |
| P16 | Token-Bucket Rate Limiting | TCP, Memcached | T5 | ✅ | Low — implement adaptive limits |
| P17 | Cost-Ordered Validation Pipeline | Bitcoin mempool | T5 | ✅ | Low — instrument existing pipeline |
| P18 | Bounded-TTL Caches, Epoch Rotation | Memcached, Redis | T3, T5, T4 | ✅ | Low — add Bloom filter layer |
| P19 | Immutable Append-Only Audit Log | Blockchain, WAL | T1, forensics | ⚠️ | Medium — implement hash-chain |
| P20 | Merkle-Proof Observability | Eth, CT logs | Censorship, revisionism | ❌ | High — optional v2 feature |

---

## Pattern Extraction Summary

**Highest-impact patterns for Phase 1b (2–4 weeks):**
- P1, P3, P8, P16, P17 (already scoped or low effort)
- P5, P6, P9 (medium effort, high impact on T4/T7)

**Patterns to defer to v2 (architectural research):**
- P15 (threshold crypto), P20 (Merkle observability), P11 (full consensus)

**Validation:** All 20 patterns extracted from production systems (BitTorrent DHT serves ~25M peers, SWIM proven in Cassandra/Riak with 1000+ node clusters, RAFT in etcd/Consul, Bitcoin in production 15+ years, BFT protocols in Ethereum/Cosmos).

