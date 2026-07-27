# Security Trace

This page connects Phase 0 concepts to the security posture of Perpetua-Tools
and the companion orama-system repository.

## Threat Trace

| Threat/control | Phase 0 source | Policy surface |
| --- | --- | --- |
| T1 malicious relay | [`DELIVERABLE-4-THREAT-MODEL-REGENERATED.md`](../DELIVERABLE-4-THREAT-MODEL-REGENERATED.md) | Authenticated control plane, redacted artifacts, trusted endpoints |
| T2 stale peer | [`DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md`](../DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md) | Heartbeat/liveness and recovery path requirements |
| T3 replay attack | [`DELIVERABLE-4-THREAT-MODEL-REGENERATED.md`](../DELIVERABLE-4-THREAT-MODEL-REGENERATED.md) | Replay/dedup and monotonic state-transition gates |
| T4 Sybil witnesses | [`PATTERN-SYNTHESIS.md`](../PATTERN-SYNTHESIS.md) | Threat-model premise check before multi-site/adversarial mesh claims |
| T5 flooding/DoS | [`MEDIUM-ITEMS-DECISION-MATRICES.md`](../MEDIUM-ITEMS-DECISION-MATRICES.md) | Bounded queues, caches, buffers, and rate limits |
| T6 confidence inflation/eclipse | [`DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md`](../DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md) | Confidence scoring plus witness diversity |
| T7 out-of-order observations | [`2026-07-11-PHASE-2-BLOCKERS.md`](../2026-07-11-PHASE-2-BLOCKERS.md) | Reorder buffer and monotonic application semantics |

## Policy Links

- PT security policy: [`../../../SECURITY.md`](../../../SECURITY.md)
- PT forward plans: [`../../next/README.md`](../../next/README.md)
- Orama companion policy:
  [`orama-system/SECURITY.md`](https://github.com/diazMelgarejo/orama-system/blob/main/SECURITY.md)

## Security Meaning

The Phase 0 documents do not require every distributed-systems pattern to ship
immediately. They require every security claim to name its evidence, boundary,
and deployment premise. For v1, the safe path is a small trusted-operator mesh
with loopback-first defaults, authenticated LAN exposure, redaction, bounded
buffers, and explicit operator recovery. For v2, multi-site and adversarial
mesh behavior must be gated by the same evidence graph rather than assumed.
