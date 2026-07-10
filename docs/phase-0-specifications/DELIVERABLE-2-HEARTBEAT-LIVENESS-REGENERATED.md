# Deliverable 2 — Heartbeat & Failure Detector (Regenerated)

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

```
HEARTBEAT_INTERVAL   = 10s ± 2s   (uniform jitter, per-tick)
HEARTBEAT_DEADLINE   = 30s        (miss window → SUSPECT signal)
SUSPICION_TIMEOUT    = 90s        (SUSPECT → DEAD signal)
```

**Ordering invariant:**
```
HEARTBEAT_INTERVAL_max  <  HEARTBEAT_DEADLINE  <  SUSPICION_TIMEOUT
        12s             <        30s           <        90s
```

### 2.1 Jitter (±2s) — Why and How

**Problem:** Synchronized heartbeats (peers booting together) cause lock-step bursts, periodic congestion spikes, correlated packet loss, and false-SUSPECT storms (thundering herd).

**Solution:** Each peer picks its next interval independently, per tick, from uniform distribution:

```
next_interval = HEARTBEAT_INTERVAL_BASE + uniform(-JITTER, +JITTER)
              = 10s + uniform(-2s, +2s)   →  [8s, 12s]
```

**Rules:**
- **Re-roll every tick**, not once at startup (prevents phase-locking)
- **Jitter the send, never the deadline** — `HEARTBEAT_DEADLINE` and `SUSPICION_TIMEOUT` are fixed detection windows
- **Deadline budgets for max jitter** — `HEARTBEAT_DEADLINE=30s` tolerates 2 full 12s intervals plus slack

---

## 3. Detection SLA — Ideal vs. Real-World LAN

> **Corrected framing:** The advertised \"30s detection\" is an **ideal-conditions floor**, not a field expectation. On production LAN: **60–90s realistic.**

| Condition | Detection time (SUSPECT) | Confirmed DEAD |
|---|---|---|
| **Ideal** (zero loss, no jitter, immediate deadline) | ~30s | ~90s |
| **Real-world LAN** (jitter, transient loss, GC pauses, hysteresis debounce) | **40–90s** | **90–120s** |

**Why the field number is higher:**
1. Send jitter — peer may have just sent at 12s edge
2. Hysteresis debounce — `StateTransitionManager` requires signal persistence before committing transition
3. Retry/grace probes — SUSPECT peer is actively re-probed before escalation
4. Clock/scheduler skew — timer wheels add seconds under load

**Publish the 40–90s band as the SLA.** Reserve \"30s\" only for lab statements, clearly labeled.

---

## 4. Asymmetric Reachability Fix (2-peer special case)

### 4.1 The bug

On a 2-node system, a naive detector marks peer B `ACTIVE` on receiving B's heartbeat. **The link can be asymmetric** — B→A packets arrive, but A→B packets do not (NAT, firewall, half-open TCP, port fault). A concludes \"B is fine,\" B concludes \"A is dead\" — split-brain with **no quorum to break the tie.**

### 4.2 The fix — require BOTH directions for ACTIVE

For N=2, a peer is `ACTIVE` **only when bidirectional reachability is proven:**

```
peer is ACTIVE  <=>  (A received heartbeat from B within DEADLINE)
                AND  (A has evidence B received A's heartbeat within DEADLINE)
```

**Evidence B received A's heartbeat:** piggybacked acknowledgement inside B's own heartbeat — a watermark \"last-seen-seq-from-A.\" No extra packets.\n\n- A's heartbeat includes `seq_A` (monotonic)\n- B's heartbeat echoes `ack_of_A = highest seq_A B has seen`\n- A treats B as **reverse-reachable** iff `ack_of_A >= (seq_A sent within DEADLINE)`\n\nBoth directions confirmed within `HEARTBEAT_DEADLINE` → `HEALTHY`. Either stale → `SUSPECT`.\n\n### 4.3 Directional signal semantics\n\n| A receives B's HB | B acks A's HB | Signal A emits about B |\n|:---:|:---:|:---:|\n| yes | yes | `HEALTHY` |\n| yes | no (stale ack) | `SUSPECT` — *asymmetric: forward-only* |\n| no | (n/a) | `SUSPECT` → `DEAD` — *forward path lost* |\n\nThe `forward-only` sub-reason signals network fault (reverse link broken), not peer crash — different remediation.\n\n**Scope:** This AND-gate is enforced for **N=2** (no quorum). For N≥3, quorum among majority already protects; AND-gate is optional and can be relaxed to reduce false SUSPECTs.\n\n---\n\n## 5. State Machine & StateTransitionManager Integration\n\nThe Failure Detector produces **raw signals**. The `StateTransitionManager` (STM) applies **hysteresis** and owns the authoritative `ACTIVE → SUSPECT → INACTIVE` machine. This split is the critical-blocker fix: previously the detector flipped state directly, causing flapping on marginal links.\n\n### 5.1 States (authoritative, owned by STM)\n\n```\nACTIVE    — bidirectional liveness confirmed, healthy\nSUSPECT   — liveness lost but not yet confirmed dead (grace/probe window)\nINACTIVE  — confirmed dead; peer removed from active routing\n```\n\n### 5.2 Hysteresis parameters (STM-owned)\n\n```\nPROMOTE_THRESHOLD   = 2   consecutive HEALTHY signals to re-enter ACTIVE\nDEMOTE_THRESHOLD    = 3   consecutive non-HEALTHY signals to leave ACTIVE\nCONFIRM_DEAD_HOLD   = SUSPICION_TIMEOUT (90s) continuous SUSPECT to reach INACTIVE\nRECOVERY_GRACE      = 1   HEALTHY signal in SUSPECT immediately cancels escalation\n```\n\n### 5.3 Detector → STM signal pipeline\n\n```pseudo\nfunction detector.evaluate(peer, now):\n    fwd_ok = (now - peer.last_recv_ts) <= HEARTBEAT_DEADLINE\n    rev_ok = peer.last_ack_seq >= peer.oldest_unacked_seq_within(DEADLINE)\n\n    if peer.cluster_size == 2:\n        signal = HEALTHY if (fwd_ok and rev_ok) else SUSPECT\n    else:\n        signal = HEALTHY if fwd_ok else SUSPECT\n\n    if peer.transport_closed:\n        signal = DEAD\n\n    STM.on_signal(peer, signal, now)\n```\n\n---\n\n## 6. Rationale Summary\n\n- **Jitter (±2s):** Breaks synchronized heartbeat bursts → no thundering-herd false-SUSPECT storms. Re-rolled per tick prevents phase re-locking.\n- **SLA reframe (40–90s):** The nominal 30s is an ideal-lab floor; real detection is dominated by jitter, hysteresis debounce, and grace re-probes.\n- **Bidirectional AND-gate (N=2):** Prevents split-brain from one-way link faults where no quorum exists. Reverse reachability proven via piggybacked ack — zero extra packets.\n- **STM + hysteresis:** Detector no longer flips state directly. Run-length thresholds (promote=2, demote=3) plus 90s dead-hold damp flapping on marginal links.\n- **N=2 dead-hold guard:** A lone `DEAD`/RST never fast-kills the only peer — the 90s hold forces corroboration instead of premature partition.\n\n---\n\n*End of Deliverable 2. Ready for Checkpoint 1.1 integration.*
