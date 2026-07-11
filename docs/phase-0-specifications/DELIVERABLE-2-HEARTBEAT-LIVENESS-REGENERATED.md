# Deliverable 2 — Heartbeat & Failure Detector (Regenerated)

**Navigation:** ← [task list](PHASE-0-TASK-LIST.md) · depends on: [D1 PeerObservation](DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md) (STM's `_apply_observation()` consumes `PeerObservation` fields directly) · constrained by: [D4 threat model](DELIVERABLE-4-THREAT-MODEL-REGENERATED.md) (T2, T3, T7) · → feeds: [Phase 1 scope](PHASE-1-SCOPE-DRAFT.md) · related plan (separate repo): [orama-system self-healing-mesh-degradation-modes](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-07-08-self-healing-mesh-degradation-modes.md) § 6.2 Heartbeat-based liveness

**Status:** Regenerated with all blocker fixes (SLA reframe, asymmetric-reachability, StateTransitionManager integration, jitter-aware timeout hierarchy).
**Layer:** Liveness / membership. Feeds the StateTransitionManager, which owns authoritative peer state.

---

## 1. Purpose & Scope

The Heartbeat + Failure Detector answers: *is this peer still alive and reachable right now?* It does **not** own peer state — it emits liveness **signals** (`HEALTHY`, `SUSPECT`, `DEAD`) that the `StateTransitionManager` consumes, debounces via hysteresis, and turns into authoritative state transitions.

| Component | Owns | Does NOT own |
|---|---|---|
| **Failure Detector** | Timing, probe I/O, per-peer liveness signal | Final state, quorum, hysteresis |
| **StateTransitionManager** | Authoritative state, transitions, hysteresis, events | Raw probe timing |

---

## 2. Timeout Hierarchy (jitter-aware)

```text
HEARTBEAT_INTERVAL   = 10s ± 2s   (uniform jitter, per-tick)
HEARTBEAT_DEADLINE   = 30s        (miss window → SUSPECT signal)
SUSPICION_TIMEOUT    = 90s        (SUSPECT → DEAD signal)
```

**Ordering invariant:**
```text
HEARTBEAT_INTERVAL_max  <  HEARTBEAT_DEADLINE  <  SUSPICION_TIMEOUT
        12s             <        30s           <        90s
```

### 2.1 Jitter (±2s) — Why and How

**Problem:** Synchronized heartbeats (peers booting together) cause lock-step bursts, periodic congestion spikes, correlated packet loss, and false-SUSPECT storms (thundering herd).

**Solution:** Each peer picks its next interval independently, per tick, from uniform distribution:

```text
next_interval = HEARTBEAT_INTERVAL_BASE + uniform(-JITTER, +JITTER)
              = 10s + uniform(-2s, +2s)   →  [8s, 12s]
```

**Rules:**
- **Re-roll every tick**, not once at startup (prevents phase-locking)
- **Jitter the send, never the deadline** — `HEARTBEAT_DEADLINE` and `SUSPICION_TIMEOUT` are fixed detection windows
- **Deadline budgets for max jitter** — `HEARTBEAT_DEADLINE=30s` tolerates 2 full 12s intervals plus slack

---

## 3. Detection SLA — Ideal vs. Real-World LAN

> **Corrected framing:** The advertised "30s detection" is an **ideal-conditions floor** for a raw SUSPECT signal, not the confirmed-dead transition. Production failure-state detection is **30–90s** depending on jitter, scheduler delay, and STM debounce.

| Condition | Raw SUSPECT signal, measured from last valid heartbeat | Committed failure state, measured from failure | Confirmed INACTIVE/DEAD, measured from sustained SUSPECT |
|---|---|---|
| **Ideal** (zero loss, no jitter, immediate deadline) | ~30s | ~30–40s | ~120s total from failure |
| **Real-world LAN** (jitter, transient loss, GC pauses, hysteresis debounce) | **30–60s** | **30–90s** | **120–180s** total from failure |

**Why the field number is higher:**
1. Send jitter — peer may have just sent at 12s edge
2. Hysteresis debounce — `StateTransitionManager` requires signal persistence before committing transition
3. Retry/grace probes — SUSPECT peer is actively re-probed before escalation
4. Clock/scheduler skew — timer wheels add seconds under load

**Publish the 30–90s band as the failure-state SLA.** Reserve "30s" only for raw detector/lab statements, clearly labeled. Confirmed INACTIVE/DEAD includes the additional 90-second continuous-SUSPECT hold.

---

## 4. Asymmetric Reachability Fix (2-peer special case)

### 4.1 The bug

On a 2-node system, a naive detector marks peer B `ACTIVE` on receiving B's heartbeat. **The link can be asymmetric** — B→A packets arrive, but A→B packets do not (NAT, firewall, half-open TCP, port fault). A concludes "B is fine," B concludes "A is dead" — split-brain with **no quorum to break the tie.**

### 4.2 The fix — require BOTH directions for ACTIVE

For N=2, a peer is `ACTIVE` **only when bidirectional reachability is proven:**

```text
peer is ACTIVE  <=>  (A received heartbeat from B within DEADLINE)
                AND  (A has evidence B received A's heartbeat within DEADLINE)
```

**Evidence B received A's heartbeat:** piggybacked acknowledgement inside B's own heartbeat — a watermark "last-seen-seq-from-A." No extra packets.

- A's heartbeat includes `seq_A` (monotonic)
- B's heartbeat echoes `ack_of_A = highest seq_A B has seen`
- A treats B as **reverse-reachable** iff `ack_of_A >= (seq_A sent within DEADLINE)`

Both directions confirmed within `HEARTBEAT_DEADLINE` → `HEALTHY`. Either stale → `SUSPECT`.

### 4.3 Directional signal semantics

| A receives B's HB | B acks A's HB | Signal A emits about B |
|:---:|:---:|:---:|
| yes | yes | `HEALTHY` |
| yes | no (stale ack) | `SUSPECT` — *asymmetric: forward-only* |
| no | (n/a) | `SUSPECT` → `DEAD` — *forward path lost* |

The `forward-only` sub-reason signals network fault (reverse link broken), not peer crash — different remediation.

**Scope:** This AND-gate is enforced for **N=2** (no quorum). For N≥3, quorum among majority already protects; AND-gate is optional and can be relaxed to reduce false SUSPECTs.

---

## 5. State Machine & StateTransitionManager Integration

The Failure Detector produces **raw signals**. The `StateTransitionManager` (STM) applies **hysteresis** and owns the authoritative `ACTIVE → SUSPECT → INACTIVE` machine. This split is the critical-blocker fix: previously the detector flipped state directly, causing flapping on marginal links.

### 5.1 States (authoritative, owned by STM)

```text
ACTIVE    — bidirectional liveness confirmed, healthy
SUSPECT   — liveness lost but not yet confirmed dead (grace/probe window)
INACTIVE  — confirmed dead; peer removed from active routing
```

### 5.2 Hysteresis parameters (STM-owned)

```text
PROMOTE_THRESHOLD   = 2   consecutive HEALTHY signals to re-enter ACTIVE
DEMOTE_THRESHOLD    = 3   consecutive non-HEALTHY signals to leave ACTIVE
CONFIRM_DEAD_HOLD   = SUSPICION_TIMEOUT (90s) continuous SUSPECT to reach INACTIVE
RECOVERY_GRACE      = 1   HEALTHY signal in SUSPECT immediately cancels escalation
```

### 5.3 Detector → STM signal pipeline and StateTransitionManager integration

**Reverse-ack freshness (`rev_ok`) — explicit, not sequence-number-only.**
A sequence number alone cannot express *when* an ack was observed: `last_ack_seq`
only ever increases, so a high value received long ago would otherwise keep
`rev_ok` true forever after the reverse link actually dies. Two independent
timestamps are required, not one:

- **send timestamp** — when *we* sent the heartbeat the peer is acking
- **observation timestamp** — when *we* received that ack (distinct from the
  ack's own content; a stale ack replayed late must not look fresh)

```pseudo
function peer.newest_sent_seq_within(DEADLINE, now):
    """Highest sequence number among heartbeats WE sent whose send-timestamp
    is within DEADLINE of now. Returns None if no such heartbeat exists
    (empty history, peer just joined, or our own send loop stalled) — this
    is the qualifying-sequence-selection rule for delayed/reordered/empty
    histories: only sends still inside the deadline window qualify, and
    reordering doesn't matter because we always take the max, not the first."""
    candidates = [s for s in peer.sent_log if (now - s.sent_ts) <= DEADLINE]
    return max(c.seq for c in candidates) if candidates else None

function detector.evaluate(peer, now):
    fwd_ok = (now - peer.last_recv_ts) <= HEARTBEAT_DEADLINE

    qualifying_seq = peer.newest_sent_seq_within(HEARTBEAT_DEADLINE, now)
    if qualifying_seq is None:
        # No qualifying heartbeat sent within the deadline -> nothing to
        # verify reverse-reachability against. Explicit reverse-unreachable,
        # never silently ACTIVE-by-default.
        rev_ok = False
    else:
        rev_ok = (
            peer.last_ack_seq >= qualifying_seq
            and (now - peer.last_ack_observed_ts) <= HEARTBEAT_DEADLINE
        )
        # An ack that references an old qualifying_seq but was itself observed
        # outside the freshness window is stale and rejected here — it cannot
        # drive rev_ok True.

    if peer.cluster_size == 2:
        signal = HEALTHY if (fwd_ok and rev_ok) else SUSPECT
    else:
        signal = HEALTHY if fwd_ok else SUSPECT

    if peer.transport_closed:
        signal = DEAD

    STM.on_signal(peer, signal, now)
```

**StateTransitionManager `_apply_observation()` pseudocode:**

```pseudo
function StateTransitionManager._apply_observation(observation: PeerObservation) -> StateChange | None:
    """
    Apply one peer observation and decide if state change is triggered.

    Args:
        observation: Complete observation record containing peer_id, epoch, sequence, nonce,
                     timestamp, observer_id, and observation_type (REACHABLE or UNREACHABLE).

    Returns:
        StateChange(from_state, to_state, reason) if threshold crossed and transition valid, else None.

    Guarantees:
        - State never regresses (monotonic apply gate enforced)
        - Replay/dedup and timestamp freshness checks run BEFORE counter mutation
        - Counters reset on opposite observation type
        - One observation affects at most one counter increment
        - Recovery hold semantics: INACTIVE + CONFIRM_DEAD_HOLD elapsed → eligible for ACTIVE
    """

    # ========== Validation gates (run before any counter mutation) ==========

    # Validate input. E1 (empty batch or null observation -> rejected before
    # validation, no state change) requires this null check to run BEFORE any
    # attribute access on observation -- accessing observation.peer_id first
    # would raise AttributeError on a None observation instead of the
    # intended ValueError rejection.
    if observation is None:
        raise ValueError("Invalid observation: observation is None")
    if observation.peer_id is None or observation.observation_type not in {REACHABLE, UNREACHABLE}:
        raise ValueError(f"Invalid observation: peer_id={observation.peer_id}, type={observation.observation_type}")

    # Fetch or initialize peer record
    peer = self.peers.get(observation.peer_id)
    if peer is None:
        peer = PeerRecord(peer_id=observation.peer_id, state=ACTIVE)
        self.peers[observation.peer_id] = peer

    # Reject duplicate observations (T3 — replay defense)
    dedup_key = (observation.observer_id, observation.epoch, observation.nonce)
    if dedup_key in self.seen_observations:
        return None  # Acknowledged but not applied

    # Reject non-monotonic observations (T7 — out-of-order defense)
    observe_ordering_key = (observation.epoch, observation.sequence, observation.timestamp, observation.nonce)
    if hasattr(peer, 'last_applied_key') and peer.last_applied_key >= observe_ordering_key:
        return None  # Late arrival; acknowledged but not applied

    # Reject stale timestamp (T2 — freshness gate)
    now = time.time()
    if observation.timestamp > now + 30.0:  # Future by >30s (clock skew tolerance)
        raise ValueError(f"Observation timestamp in future: {observation.timestamp}")

    # ========== Record this observation as seen (for dedup) ==========
    self.seen_observations.add(dedup_key)

    # ========== Apply observation and mutate counters ==========

    if observation.observation_type == REACHABLE:
        # REACHABLE: increment promote counter, reset demote counter
        peer.pending_count_promote += 1
        peer.pending_count_demote = 0

        # Check if promotion threshold crossed
        if peer.pending_count_promote >= PROMOTE_THRESHOLD:
            if peer.state == SUSPECT:
                # Transition from SUSPECT → ACTIVE
                peer.state = ACTIVE
                peer.pending_count_promote = 0
                peer.confirm_dead_timestamp = None  # Clear hold window
                peer.last_transition_ts = now
                state_change = StateChange(from_state=SUSPECT, to_state=ACTIVE, reason="promotion_threshold")
                return state_change
            elif peer.state == INACTIVE:
                # Recovery candidate: check CONFIRM_DEAD_HOLD window
                if peer.confirm_dead_timestamp and (now - peer.confirm_dead_timestamp) >= 90.0:
                    # Hold window expired; peer is recovery-eligible
                    peer.state = ACTIVE
                    peer.pending_count_promote = 0
                    peer.pending_count_demote = 0
                    peer.confirm_dead_timestamp = None
                    peer.last_transition_ts = now
                    state_change = StateChange(from_state=INACTIVE, to_state=ACTIVE, reason="recovery_window_elapsed")
                    return state_change
                else:
                    # Still in hold window; don't transition yet
                    return None

    else:  # UNREACHABLE
        # UNREACHABLE: increment demote counter, reset promote counter
        peer.pending_count_demote += 1
        peer.pending_count_promote = 0

        # Check if demotion threshold crossed
        if peer.pending_count_demote >= DEMOTE_THRESHOLD:
            if peer.state == ACTIVE:
                # Transition from ACTIVE → SUSPECT
                peer.state = SUSPECT
                peer.pending_count_demote = 0
                peer.confirm_dead_timestamp = now  # Start hold window for eventual INACTIVE
                peer.last_transition_ts = now
                state_change = StateChange(from_state=ACTIVE, to_state=SUSPECT, reason="demotion_threshold")
                return state_change
            elif peer.state == SUSPECT:
                # Already SUSPECT; continue hold window
                if not peer.confirm_dead_timestamp:
                    peer.confirm_dead_timestamp = now
                # Check if hold window has elapsed
                if (now - peer.confirm_dead_timestamp) >= 90.0:
                    # Sustained SUSPECT for CONFIRM_DEAD_HOLD → escalate to INACTIVE
                    peer.state = INACTIVE
                    peer.pending_count_demote = 0
                    peer.last_transition_ts = now
                    state_change = StateChange(from_state=SUSPECT, to_state=INACTIVE, reason="confirm_dead_hold_elapsed")
                    return state_change

    # ========== Record last applied observation key ==========
    peer.last_applied_key = observe_ordering_key

    # No state change triggered
    return None
```

**Recovery logic (detailed):**

When a peer is INACTIVE and a REACHABLE observation arrives:
- **If within CONFIRM_DEAD_HOLD window (< 90s since SUSPECT → INACTIVE):** Observation is applied, but peer remains INACTIVE. The recovery counter is incremented, but a single REACHABLE is insufficient to re-enter ACTIVE while the hold window is active. This prevents oscillation between INACTIVE and ACTIVE on marginal links.
- **If CONFIRM_DEAD_HOLD window expires (≥ 90s since SUSPECT → INACTIVE):** The next REACHABLE observation triggers recovery. Peer transitions to ACTIVE, all counters reset, and the hold window is cleared. The peer is treated as newly reachable.
- **If UNREACHABLE arrives during hold:** Hold window continues; peer remains INACTIVE. Counter is incremented but the peer does not degrade further.

**Edge case handling (E1–E10):**

| Case | Scenario | Expected Behavior |
|------|----------|---|
| **E1** | Empty observation batch or null observation | No state change; observation rejected before validation |
| **E2** | Out-of-order observations (newer epoch 5, then older epoch 4) | Older observation ignored (monotonic apply gate rejects based on `(epoch, seq, timestamp)` ordering); no state regression |
| **E3** | Multiple observations in one batch (3 REACHABLE + 1 UNREACHABLE) | Applied in sequence; threshold checks run after each; if threshold crossed mid-batch, state changes immediately; remaining observations applied to NEW state |
| **E4** | Threshold hit mid-batch (e.g., 2nd REACHABLE of 3 triggers PROMOTE_THRESHOLD=2) | State changes after 2nd; 3rd observation is applied to new state (SUSPECT becomes ACTIVE); counters reset |
| **E5** | Flapping (REACHABLE, UNREACHABLE, REACHABLE within 1s) | Counters reset twice; no state change if thresholds not hit (pending_count_promote max = 1, pending_count_demote max = 1) |
| **E6** | Clock skew (observation timestamp > now + 30s) | Observation rejected at validation gate; `ValueError` raised; not applied |
| **E7** | Conflicting timestamps (same epoch, peer, seq, different nonce) | Dedup key `(observer_id, epoch, nonce)` ensures one canonical observation per observer per epoch per nonce; deterministic winner by `(epoch, seq, timestamp, nonce)` tuple ordering |
| **E8** | Sybil witnesses (5 observers, same peer, same epoch, all UNREACHABLE) | Each observation has distinct `(observer_id, nonce)`, so only one per observer per nonce is counted; dedup gate applies; state transitions driven by STM counter thresholds (proof diversity is D1/D4 concern) |
| **E9** | Recovery after CONFIRM_DEAD_HOLD expiry (peer INACTIVE for 91s, then REACHABLE arrives) | Transition INACTIVE → ACTIVE; reset all counters to 0; apply the arriving UNREACHABLE if it immediately follows, incrementing pending_count_demote = 1 with peer in new ACTIVE state |
| **E10** | Bootstrap (peer appears for first time) | Peer initialized to ACTIVE state; first UNREACHABLE increments pending_count_demote = 1; no state change until pending_count_demote >= 3 |

**Threat model alignment (see Deliverable 4 for full threat analysis):**

The asymmetric hysteresis design (PROMOTE_THRESHOLD=2, DEMOTE_THRESHOLD=3, CONFIRM_DEAD_HOLD=90s) directly supports Phase 0 threat mitigations specified in D4:

- **T2 (Stale Peer):** The CONFIRM_DEAD_HOLD window prevents a replay of an old "SUSPECT" observation from prematurely marking a peer INACTIVE. The 90s hold requires sustained evidence before state regression.
- **T5 (Flooding/DoS):** The cost-ordered pipeline (dedup before expensive validation) combined with STM's counter-based debounce prevents high-volume observation floods from causing state flapping or resource exhaustion.
- **T6 (Eclipse/Confidence Inflation):** Multiplicative confidence gates (D1 § 3.2) feed state transitions; the STM's hysteresis thresholds add a second, independent damping layer. Quantity of low-quality observations cannot force state change if confidence remains below thresholds.
- **T7 (Out-of-Order Observations):** The monotonic apply gate in `_apply_observation()` enforces the `(epoch, sequence, timestamp)` ordering key, ensuring late-arriving older observations cannot regress peer state despite observation reordering.

### 5.4 STM transition table

| Current state | HEALTHY signal | SUSPECT signal | DEAD signal |
|---|---|---|---|
| `ACTIVE` | Reset demotion counter; remain `ACTIVE` | Increment demotion counter; transition to `SUSPECT` when `DEMOTE_THRESHOLD` is reached | Enter `SUSPECT`; start or continue `CONFIRM_DEAD_HOLD`, do not fast-kill on one signal |
| `SUSPECT` | Increment promotion counter; transition to `ACTIVE` when `PROMOTE_THRESHOLD` is reached; one healthy signal cancels escalation via `RECOVERY_GRACE` | Reset promotion counter; remain `SUSPECT`; continue hold timer | Remain `SUSPECT`; transition to `INACTIVE` only after continuous hold reaches `CONFIRM_DEAD_HOLD` |
| `INACTIVE` | Treat as recovery candidate; require `PROMOTE_THRESHOLD` fresh HEALTHY signals before `ACTIVE` | Remain `INACTIVE` | Remain `INACTIVE` |

`DEAD` is therefore an input signal, not an immediate state mutation. STM is the only component allowed to commit `SUSPECT → INACTIVE`, and it does so only after the hold window and validation gates pass.

---

## 6. Rationale Summary

- **Jitter (±2s):** Breaks synchronized heartbeat bursts → no thundering-herd false-SUSPECT storms. Re-rolled per tick prevents phase re-locking.
- **SLA reframe (30–90s):** The nominal 30s is an ideal raw-signal floor; committed failure-state detection is bounded by jitter, hysteresis debounce, and grace re-probes.
- **Bidirectional AND-gate (N=2):** Prevents split-brain from one-way link faults where no quorum exists. Reverse reachability proven via piggybacked ack — zero extra packets.
- **STM + hysteresis:** Detector no longer flips state directly. Run-length thresholds (promote=2, demote=3) plus 90s dead-hold damp flapping on marginal links.
- **N=2 dead-hold guard:** A lone `DEAD`/RST never fast-kills the only peer — the 90s hold forces corroboration instead of premature partition.

---

*End of Deliverable 2. Ready for Checkpoint 1.1 integration.*
