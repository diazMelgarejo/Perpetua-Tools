# Execution Plan: P2P Security Patterns + Multi-Agent Swarm Security Analysis
## Deep-Research-Driven Implementation for Perpetua-Tools and orama-system

**Date:** 2026-07-10
**Scope:** 20 P2P patterns (P1-P20) + 16 security gaps (G1-G16) across T1-T7 threats
**Target repos:** Perpetua-Tools (feature/phase-0-blocker-fixes) + orama-system (main)
**Methodology:** deep-research skill (10+ iteration cycles, recursive reflection, evidence-grounded)

---

## Part 1: Discovery Phase — Deep Research Iteration Cycles

### Iteration 1: Gap Severity Validation (CRITICAL gaps first)

This iteration consumes the gap severity ratings, threat model (T1–T7), and pattern coverage analysis from [`MULTIAGENT-SWARM-SECURITY-ANALYSIS.md`](./MULTIAGENT-SWARM-SECURITY-ANALYSIS.md).

**Research question:** Are G1, G3, G4 truly CRITICAL in the current deployment context?

**Investigation targets:**
- G1 (P5 Provenance Dedup): Current witness quorum logic in PT `agent_launcher.py` — how does it count witnesses?
- G3 (P9 Reorder Buffer): Current observation apply order in PT — is monotonic gate sufficient without buffer?
- G4 (P13 Equivocation Detection): Current contradiction logging — does D1's witness disagreement logging catch this?

**Evidence needed:**
```text
1. Read PT agent_launcher.py observation ingestion path
2. Read PT witness quorum aggregation logic
3. Read orama probe_lan_peer.py observation schema (field order, nonce handling)
4. Check if (epoch, sequence, timestamp) triple is actually enforced in apply path
5. Search for existing reorder or buffer logic in PT codebase
```

**Deliverable:** Gap severity re-assessment with code evidence. Some gaps may be downgraded from CRITICAL to HIGH if existing code provides partial defense.

---

### Iteration 2: Pattern Implementation Feasibility
**Research question:** Which P1-P20 patterns are implementable in <1 day vs. require architectural redesign?

**Investigation targets per pattern tier:**

| Tier | Patterns | Feasibility Research |
|------|----------|---------------------|
| Already implemented (P1, P3, P12, P16, P17, P18) | 6 patterns | Verify in code; document; no implementation needed |
| Low effort — schema/extension (P8, P9 partial, P19 partial) | 3 patterns | Field additions, hash-chain wiring |
| Medium effort — new modules (P2, P5, P6, P7, P13) | 5 patterns | ASN lookup, reputation ledger, gossip fan-out, equivocation log |
| High effort — refactoring (P4, P11) | 2 patterns | Multi-path confidence tracking, RAFT-lite |
| Research-only v2 (P10, P14, P15, P20) | 4 patterns | Document rationale; do not implement |

**Evidence needed:**
```text
1. Read PT observation schema (what fields exist today?)
2. Read PT confidence formula implementation
3. Check for existing GeoIP/ASN library dependencies
4. Check for existing reputation/witness tracking data structures
5. Read gossip bus implementation (fan-out logic)
6. Assess if P4 multi-path requires confidence formula refactor or just addition
```

**Deliverable:** Feasibility matrix with per-pattern effort estimates validated against actual code.

---

### Iteration 3: Cross-Repo Implementation Split
**Research question:** Which patterns belong in Perpetua vs. orama?

**Architecture principle:** Perpetua owns state authority (L2); orama owns observation routing (L3)

| Pattern | Primary Repo | Rationale | Integration Point |
|---------|-------------|-----------|-------------------|
| P1 Proof-Anchored Identity | PT | State authority validates signatures | Observation apply path |
| P2 Distance Bucketing | PT | Membership management | Peer table |
| P3 Challenge-Response | orama | L3 probe execution | probe_lan_peer.py |
| P4 Multi-Path Diversity | orama | L3 routes observations | Portal relay endpoint |
| P5 Provenance Dedup | PT | Quorum aggregation | Witness counting |
| P6 Reputation Scoring | PT | State tracking | Witness ledger |
| P7 Async Notification | orama | L3 gossip propagation | GossipBus.emit() |
| P8 Monotonic Sequence | PT | State apply order | Observation schema + apply gate |
| P9 Reorder Buffer | PT | State correctness | Apply path buffer |
| P13 Equivocation Detection | PT | State integrity | Observation comparison |
| P16 Rate Limiting | orama | L3 intake protection | Portal middleware |
| P17 Cost-Ordered Pipeline | orama | L3 validation | Portal middleware |
| P18 Bounded Caches | PT | State memory management | Dedup cache |
| P19 Audit Log | both | Cross-layer forensics | Both repos append to shared log |

**Evidence needed:**
```text
1. Read PT state machine code (where are observations applied?)
2. Read orama Portal middleware (where are observations received?)
3. Identify shared data structures (fleet_topology.json, peer state)
4. Determine which repo "owns" each data structure
```

**Deliverable:** Per-pattern repo assignment with integration points documented.

---

### Iteration 4: Production Context Validation
**Research question:** What is the actual threat model in the current Mac-Win deployment?

**Context:**
- 2-3 core nodes (Mac L2+L3, Win L1, possibly cloud L1)
- LAN-first communication (192.168.x.x)
- No untrusted transient peers yet (all nodes are operator-controlled)
- Current adversary model: accidental failure, not malicious attack

**Research implications:**
- T4 (Sybil) is theoretical with 2-3 nodes — G1 ASN dedup may be overkill for current deployment
- T6 (Eclipse) requires network-path control — unlikely on LAN
- T7 (Out-of-order) is real: sleep/wake cycles cause delayed observations
- T1 (Malicious relay) is theoretical unless L1 is compromised

**Deliverable:** Context-adjusted priority list. Current deployment needs P3, P7, P8, P9 most; P5, P6, P13 can be prototyped but not urgently deployed.

---

### Iteration 5: SKILL.md Adaptation Design
**Research question:** How does each pattern translate to a SKILL.md-compatible specification?

**SKILL.md constraints:**
- Target <= 200 lines per skill
- Must include: when_to_use, description, frontmatter, rules section
- Must be implementable by AI agent reading the SKILL.md
- No external dependencies beyond stdlib + aioquic + cryptography

**Pattern-to-skill mapping:**

| Skill Name | Patterns | Lines Estimate |
|-----------|----------|---------------|
| `oasn-identity` | P1 (proof-anchored) | ~150 |
| `oasn-membership` | P2, P3, P7 (HyParView + SWIM) | ~200 |
| `oasn-quorum` | P5, P6, P12 (witness + reputation + BFT) | ~180 |
| `oasn-sequence` | P8, P9 (monotonic + reorder buffer) | ~150 |
| `oasn-forensics` | P13, P19 (equivocation + audit log) | ~150 |
| `oasn-defense` | P16, P17, P18 (rate limiting + pipeline + caches) | ~180 |

**Deliverable:** SKILL.md template for each pattern group with frontmatter and rules section.

---

### Iteration 6: Integration with Existing Fleet Mode Work
**Research question:** How do P1-P20 patterns integrate with the 5-phase fleet mode implementation plan?

**Cross-reference:**

| Fleet Mode Phase | Related Patterns | Integration |
|-----------------|-----------------|-------------|
| Phase 1 (FleetMode enum) | P2, P12 | Distance bucketing for peer classification; BFT threshold for mode transitions |
| Phase 2 (Topology endpoint) | P5, P6 | Witness quorum for topology consensus; reputation for peer ranking |
| Phase 3 (Coord pulse) | P7, P8 | Gossip fan-out for pulse propagation; sequence numbers for pulse ordering |
| Phase 4 (Banner) | P3 | Challenge-response for banner status accuracy |
| Phase 5 (Self-healing) | P4, P9, P13 | Multi-path for healing verification; reorder buffer for state recovery; equivocation for split-brain detection |

**Deliverable:** Pattern integration map showing which patterns enhance which fleet mode phases.

---

### Iteration 7: Test Strategy Design
**Research question:** How do we test adversarial patterns without a real adversary?

**Test approach:**
1. **Unit tests** (deterministic): Each pattern's logic in isolation
2. **Fault injection** (controlled chaos): Kill nodes, delay messages, drop packets
3. **Simulation** (scenario-based): Multi-node network in Python asyncio
4. **Property-based tests** (Hypothesis): Invariants that must hold (e.g., "no two honest nodes disagree on final state")

**Test targets per gap:**

| Gap | Test Strategy | Pass Criteria |
|-----|--------------|---------------|
| G1 (Sybil) | Inject 5 fake peers from same IP | Quorum counts 1 witness, not 5 |
| G2 (Eclipse) | Block direct path, use relay only | Confidence drops to "insufficient" |
| G3 (Reorder) | Deliver observations in reverse order | State converges to correct final value |
| G4 (Equivocation) | Send two contradictory signed observations | Both logged, peer flagged |
| G5 (Reputation) | Send 10% false observations | Reputation drops below threshold |

**Deliverable:** Test specification with pass/fail criteria for each gap.

---

### Iteration 8: Dependency and Environment Audit
**Research question:** What dependencies are needed, and are they compatible with the Mac-Win environment?

**Dependency list:**

| Package | Mac | Windows | Purpose | Install |
|---------|-----|---------|---------|---------|
| `aioquic` | ✅ | ✅ | QUIC transport | pip |
| `cryptography` | ✅ | ✅ | Ed25519, TLS | pip |
| `maxminddb` | ✅ | ✅ | GeoIP ASN lookup | pip |
| `sortedcontainers` | ✅ | ✅ | SortedDict (reorder buffer) | pip |
| `mmh3` | ✅ | ✅ | MurmurHash (Bloom filter) | pip |

**Total: 5 packages.** Not uniformly "pure Python with compiled extensions" — the five differ in kind:
- `sortedcontainers` — pure Python, no native code, most portable of the five.
- `aioquic`, `cryptography`, `mmh3` — native-extension dependencies (C/Rust builds); wheels are published for macOS and Windows but build-from-source can fail without a working toolchain.
- `maxminddb` — has an *optional* C extension for speed; falls back to a pure-Python reader if the extension isn't available, so it degrades gracefully rather than hard-failing.

macOS/Windows support above reflects published wheel availability, not a portability guarantee for every environment (e.g. unusual Python versions or architectures may need a source build).

**Deliverable:** Dependency manifest with per-package installation verification.

---

### Iteration 9: Performance Budget
**Research question:** What are the performance targets, and can Python meet them?

**Targets from pattern analysis:**

| Operation | Target | Python Feasibility |
|-----------|--------|-------------------|
| Ed25519 sign | 0.6ms | ✅ cryptography library |
| Ed25519 verify | 0.6ms | ✅ cryptography library |
| Kademlia lookup | O(log n) hops | ✅ pure Python |
| HyParView promotion | <1s | ✅ TCP timeout + promote |
| Gossip fan-out | log(n) messages | ✅ UDP send |
| Reorder buffer insert | O(log B), B=10 | ✅ SortedDict |
| Rate limit check | O(1) | ✅ dict lookup |
| ASN lookup | 100ms cold | ✅ MaxMind DB |

**Deliverable:** Performance budget table with validation plan.

---

### Iteration 10: Risk Analysis and Fallback Plan
**Research question:** What could go wrong, and what's the fallback?

| Risk | Probability | Fallback |
|------|------------|----------|
| ASN lookup library incompatible | Low | Use IP prefix /24 dedup instead of ASN |
| SortedDict too slow for reorder | Low | Use plain list (B=10, linear scan is fine) |
| Ed25519 verify too slow for flood | Medium | Batch verification; defer to background task |
| Cross-repo sync failures | Medium | Each pattern is self-contained; missing integration doesn't break existing code |
| SKILL.md too complex for AI | Medium | Layer-by-layer verification; each skill has standalone test |

**Deliverable:** Risk register with per-risk fallback strategy.

---

## Part 2: Execution Phase — Implementation Tracks

### Track A: Perpetua-Tools (State Authority Layer)

**Branch:** `feature/phase-0-blocker-fixes` (or new `feature/pattern-implementation`)

| Session | Task | Patterns | Effort | Output |
|---------|------|----------|--------|--------|
| A1 | Observation schema extension | P8 (sequence_number field) | 2h | Schema v2 with seq field |
| A2 | Reorder buffer implementation | P9 (SortedDict buffer) | 4h | `reorder_buffer.py` + tests |
| A3 | Witness quorum + provenance — **integration only** (`witness_quorum.py` + `provenance.py` already implemented and unit-tested) | P5 | 2h | Wired into STM pipeline step 3 |
| A4 | Reputation ledger — **integration only** (`reputation.py` already implemented and unit-tested) | P6 | 2h | Wired into STM pipeline step 4 |
| A5 | Equivocation detection — **integration only** (`equivocation.py` already implemented and unit-tested) | P13 | 2h | Wired into STM pipeline step 2 |
| A6 | Audit log hash-chain — **integration only** (`audit_log.py` already implemented and unit-tested) | P19 | 2h | Wired into STM pipeline step 6 |
| A7 | Distance bucketing — **integration only** (`distance_bucket.py` already implemented and unit-tested) | P2 | 2h | Wired into STM pipeline step 5 |
| A8 | Cache eviction + Bloom filter | P18 (LRU + Bloom) | 3h | `dedup_cache.py` |
| A9 | Integration + system tests | All PT patterns | 6h | `test_pattern_integration.py` |

**Total Track A:** ~25 hours (~3–4 sessions) — was ~36h when A3–A7 assumed module implementation from scratch; all five modules (P2/P5/P6/P13/P19) are already implemented and unit-tested, so those rows now reflect integration-only effort (10h total, not 21h) matching the concrete milestone below.

> A3–A7's integration work is tracked as the concrete milestone [`2026-07-11-state-transition-manager-integration-plan.md`](./2026-07-11-state-transition-manager-integration-plan.md), which wires the already-implemented P2/P5/P6/P13/P19 modules into a single `PeerObservation` security-decision pipeline (StateTransitionManager). The per-row effort above is this milestone's per-module share, not a separate duplicate implementation task.

---

### Track B: orama-system (Observation Routing Layer)

**Branch:** `feature/pattern-implementation` (from main)

| Session | Task | Patterns | Effort | Output |
|---------|------|----------|--------|--------|
| B1 | Challenge-response in probe | P3 (nonce binding in heartbeat) | 3h | `probe_lan_peer.py` v2 |
| B2 | Gossip log(N) fan-out | P7 (ceil(log(N))) | 3h | `gossip_bus.py` fan-out fix |
| B3 | Rate limiting middleware | P16 (token bucket per source) | 4h | Portal middleware |
| B4 | Cost-ordered pipeline | P17 (syntax→rate→dedup→fresh→proof) | 4h | Portal middleware |
| B5 | Multi-path probe diversity | P4 (direct + relay confidence tracks) | 6h | `multi_path_probe.py` |
| B6 | Integration + system tests | All orama patterns | 6h | `test_pattern_integration.py` |

**Total Track B:** ~26 hours (~4 sessions)

---

### Track C: SKILL.md Production (Parallel)

| Session | Task | Patterns | Effort | Output |
|---------|------|----------|--------|--------|
| C1 | Identity + membership skills | P1, P2, P3, P7 | 4h | 2 SKILL.md files |
| C2 | Quorum + sequence skills | P5, P6, P8, P9, P12 | 4h | 2 SKILL.md files |
| C3 | Forensics + defense skills | P13, P16, P17, P18, P19 | 4h | 2 SKILL.md files |
| C4 | Integration skill (meta) | All | 2h | 1 orchestrator SKILL.md |

**Total Track C:** ~14 hours (~2 sessions)

---

### Track D: Fleet Mode Integration (Parallel to A+B)

| Session | Task | Fleet Phase | Pattern Integration | Effort |
|---------|------|------------|---------------------|--------|
| D1 | FleetMode enum + classify | Phase 1 | P2 (bucketing for peer class), P12 (BFT threshold) | 5h |
| D2 | Topology endpoint + relay | Phase 2 | P5 (quorum for topology), P6 (reputation ranking) | 7.5h |
| D3 | Coord pulse extension | Phase 3 | P7 (gossip fan-out), P8 (sequence for pulse ordering) | 5h |
| D4 | Banner + --fleet-status | Phase 4 | P3 (challenge-response for accuracy) | 2h |
| D5 | Self-healing + split-brain | Phase 5 | P4 (multi-path), P9 (reorder), P13 (equivocation) | 6h |

**Total Track D:** ~25.5 hours (~4 sessions, after A1-A3 and B1-B2 complete)

---

## Part 3: Deliverables and Acceptance Criteria

### Deliverables by Track

| Track | Primary Deliverables | Acceptance Criteria |
|-------|---------------------|---------------------|
| A (PT) | 8 Python modules + tests | All unit tests pass; adversarial tests for G1-G4 pass |
| B (orama) | 6 Python modules + Portal middleware | All unit tests pass; rate limiting verified under load |
| C (SKILL) | 7 SKILL.md files | Each <= 200 lines; each has standalone test; AI-agent implementable |
| D (Fleet) | Fleet modes operational | FLEET→PAIR→SOLO transitions in <1 pulse; all 10 success criteria met |

### Cross-Cutting Deliverables

| Deliverable | Location | Evidence |
|-------------|----------|----------|
| Pattern implementation status update | `PATTERN-SYNTHESIS.md` v2 | Updated status column (✅/⚠️/❌) |
| Gap closure report | `MULTIAGENT-SWARM-SECURITY-ANALYSIS.md` v2 | G1-G16 status updated |
| Threat matrix v2 | Same document | T1-T7 × P1-P20 with ✅ for implemented |
| Integration test report | `tests/test_pattern_integration.py` | All tests green |
| Fleet mode operational runbook | `docs/operational/fleet-modes.md` | Kill/restart procedures, expected transitions |

---

## Part 4: Timeline and Dependencies

```
Week 1: Discovery + Foundation
  Day 1-2: Iterations 1-3 (gap validation, feasibility, repo split)
  Day 3:   Iteration 4 (production context validation)
  Day 4:   A1 (schema extension) + B1 (challenge-response)
  Day 5:   A2 (reorder buffer) + B2 (gossip fan-out)

Week 2: Core Implementation
  Day 1-2: A3 (witness quorum) + A4 (reputation)
  Day 3:   A5 (equivocation) + B3 (rate limiting)
  Day 4:   A6 (audit log) + B4 (cost pipeline)
  Day 5:   A7 (bucketing) + B5 (multi-path)

Week 3: Integration + Fleet
  Day 1:   A8 (cache) + A9 (integration tests)
  Day 2:   B6 (integration tests)
  Day 3:   D1 (FleetMode) + D2 (topology endpoint)
  Day 4:   D3 (coord pulse) + D4 (banner)
  Day 5:   D5 (self-healing) + E2E tests

Week 4: SKILL.md + Validation
  Day 1-2: C1-C3 (SKILL.md production)
  Day 3:   C4 (orchestrator skill) + integration
  Day 4:   Documentation updates (v2 reports)
  Day 5:   Final validation + PR creation
```

**Critical path:** A1→A2→A3→A5→A9→D1→D3→D5 (PT state authority must be solid before fleet modes)
**Parallel tracks:** B1-B6 can run concurrently with A1-A9. C1-C4 can run after A3 and B3 complete.

---

## Part 5: Decision Points

| Decision | When | Options | Default |
|----------|------|---------|---------|
| ASN lookup: MaxMind vs. IP2Location vs. /24 prefix | After Iteration 2 | MaxMind (free) / IP2Location (paid) / /24 (no dep) | MaxMind free tier |
| Reorder buffer: SortedDict vs. plain list | After A2 prototype | SortedDict (O(log B)) / list (O(B), B=10) | SortedDict |
| Rate limit: static vs. adaptive | After B3 | Static (simple) / adaptive (complex, better) | Static first, adaptive in Phase 1b |
| Multi-path: separate confidence tracks vs. unified | After B5 prototype | Separate (more accurate) / unified (simpler) | Separate tracks |
| Fleet mode persistence: re-classify vs. cache | After D1 | Re-classify on startup (simple) / cache to disk (faster) | Re-classify (plan default) |

---

## Related Integration Milestones

- [`MULTIAGENT-SWARM-SECURITY-ANALYSIS.md`](./MULTIAGENT-SWARM-SECURITY-ANALYSIS.md) — P2P threat model mapping (T1–T7), gap severity analysis (G1–G16), and the security foundation that defines which gaps this execution plan closes.
- [`2026-07-11-state-transition-manager-integration-plan.md`](./2026-07-11-state-transition-manager-integration-plan.md) — Concrete Perpetua-Tools milestone that wires the already-implemented P2/P5/P6/P13/P19 modules into a single `PeerObservation` security-decision pipeline. Compresses Track A3–A7 into a 2–3 day integration pass and unblocks Track D (Fleet Mode Integration).
- **Canonical orama-system cross-reference (progressive disclosure — read on demand):** `orama-system/docs/v2/03-safety-v2.5.md` § "Related implementation patterns (Perpetua-Tools)" — MAESTRO/SWARM's v2.5 enforcement design maps directly onto this plan's P1–P20 catalog and the G1–G16 gaps it closes. Before executing further tracks against these patterns, also read `orama-system/docs/v2/45-single-operator-lan-threat-model-descope.md` (D23) — P5/P6/P13 (witness quorum, reputation-decay, equivocation) were descoped for the current single-operator-LAN deployment after a premise check found no adversary for them to defend against; re-run that check before resuming Track A/D work on those specific patterns.

---

*End of Execution Plan. Ready for discovery phase (Iteration 1) to begin upon confirmation.*
