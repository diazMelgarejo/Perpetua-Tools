# Quad CEO Review — PR #205 (`phase-2-stm-concurrency-dedup`, commit `60636ad5`)

Four independent CEO/Strategist review voices on the same PR, collected 2026-07-12 during `/autoplan` Phase 1. Kept verbatim, side by side, for human comparison — including two voices with verified-false or corrected claims (kept, not deleted, with inline caveats).

| # | File | Voice | Grounding | Reliability |
|---|------|-------|-----------|-------------|
| 1 | [01-codex.md](01-codex.md) | Codex (GPT-5.5, `codex exec`) | Plan file only, no independent repo exploration | Clean — no corrections needed |
| 2 | [02-claude-worktree-agent.md](02-claude-worktree-agent.md) | Claude subagent, `agentId a51e4d78f51585c6b` (worktree-isolated) | Self-directed: plan file, PATTERN-SYNTHESIS.md, STM source, git history on worktree + main | **Central claim VERIFIED FALSE** ("main already has commit 60636ad5") — worktree was simply stale, not main ahead. Kept with inline `[FALSE, see caveat]` annotations. |
| 3 | [03-claude-resumed-original.md](03-claude-resumed-original.md) | Claude subagent, `agentId aac123e82eb006ede` (resumed original, context-leak incident) | Plan file, PATTERN-SYNTHESIS.md, STM source, monotonic_gate.py, peer_record.py | **One claim corrected**: `monotonic_gate.is_observation_newer()` framed as "a live parallel bypass path" — verified it's real but equally dead code (zero callers), not live. Inline `[CORRECTION, ...]` note + corrected severity table row. |
| 4 | [04-claude-accidental-duplicate.md](04-claude-accidental-duplicate.md) | Claude subagent, `agentId a48271345c02103d6` (spawned by mistake, then given the task via follow-up) | Independent: plan, PATTERN-SYNTHESIS.md, STM source (608 lines), git log, threat model docs, full call-site trace | Clean — fully independent, no corrections needed. Useful as a context-isolation control case (see its header). |

## Convergence (what all 4 independently agree on)

1. **`StateTransitionManager.evaluate_observation()` has zero production callers.** Independently re-verified by grep in Voices 2, 3, 4, and by the orchestrating session directly — 4+ independent confirmations. The manager is constructed in `orchestrator.py:123` but never invoked outside tests.
2. **The BFT/permissionless threat model (Sybil correlation, k-buckets, reputation-decay, equivocation slashing) may not match the actual deployment** — a single operator's own small LAN (1–3 / 2–5 / 10–100 nodes across L3/L2/L1, all self-owned), not an adversarial multi-tenant network. Raised independently by Voices 1, 2 (surviving claim), and 4.
3. Build-vs-adopt risk: a ~2,100 LOC hand-rolled BFT stack vs. mature alternatives (Consul/Serf/SWIM, etcd/raft) was never evaluated. Raised by Voices 1 and 4.

## Disagreements / unique findings

- **Voice 1 (Codex)** proposes the sharpest reframe: shift from "integrate remaining Phase 1b patterns" to "make STM safe under adversarial, high-concurrency, long-running workloads with explicit invariants and rollback boundaries."
- **Voice 2 (worktree)** — despite its false central premise — independently flagged that the plan's own scope boundary was violated the same day it was written (P9/P18/P2 landing directly, contradicting the plan's own "out of scope" line).
- **Voice 3 (resumed original)** is the only voice to trace `monotonic_gate.py` as a structurally separate, equally-dead module — a distinct finding from the STM-specific "zero callers" claim.
- **Voice 4 (accidental duplicate)** is the only voice to flag the in-memory-only persistence of `AuditLog`/`ReputationLedger`/`EquivocationLog`/`KBucketTable` (restart wipes all forensic state) and the near-zero-teeth equivocation penalty (trivial `observer_id` rotation).

## Resolution

Recorded as a **GATE on P5/P6/P13** in `PATTERN-SYNTHESIS.md` (2026-07-12 entry, after "Pattern Extraction Summary"): PR #205 itself stays unblocked and merged as-is; further P5/P6/P13 pattern-hardening work requires BOTH (1) `evaluate_observation()` wired into a real production ingestion path and (2) an explicit threat-model premise re-check scoped to the actual single-operator LAN topology, before it resumes. User decision: "Wiring + threat-model re-check, both required."
