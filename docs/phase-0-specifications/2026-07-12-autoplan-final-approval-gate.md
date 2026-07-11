# `/autoplan` Final Approval Gate — PR #205 (`phase-2-stm-concurrency-dedup`)

Phase 4 of the full `/autoplan` review pipeline run against PR #205, 2026-07-12. This run was atypical: `/autoplan` is designed for pre-implementation plans, but the user explicitly chose to run it against already-implemented, tested, merged code ("Run full /autoplan anyway"). Everything below accounts for that.

---

## 1. What already exists (not re-litigated here)

- `orchestrator/state_transition_manager.py` — P9 (reorder buffer), P18 (bounded LRU caches), P2 (k-bucket maintenance), ref-counted per-peer locks, and 2 memory-leak fixes. 35/35 unit tests passing. Implemented, tested, and merged to `phase-2-stm-concurrency-dedup` before this review began.
- `docs/phase-0-specifications/2026-07-11-state-transition-manager-integration-plan.md` — the governing design doc, now corrected in two places (see §5).
- `docs/phase-0-specifications/PATTERN-SYNTHESIS.md` — canonical 20-pattern spec, now carries the P5/P6/P13 gate this run produced.

## 2. Not in scope for this gate

- Re-implementing or reverting any of PR #205's shipped code — out of scope; the code stays merged regardless of this gate's outcome.
- The full DELIVERABLE-2 hysteresis machine — explicitly deferred in the original integration plan, untouched here.
- Fleet Mode / multi-tenant swarm design — referenced only as context for the threat-model question, not designed here.

## 3. Premise confirmation (Phase 1 gate)

Confirmed at kickoff: the user explicitly chose to run the full review pipeline against already-shipped code, understanding `/autoplan` is normally a pre-implementation tool. This is a deliberate, informed choice, not an oversight — recorded here to close out that gate formally.

## 4. CEO Review consensus (Phase 1)

Full record: [`2026-07-12-ceo-review-quad-voices/`](2026-07-12-ceo-review-quad-voices/00-README.md) — 4 independent voices (Codex, 2 Claude subagents, +1 accidental-duplicate Claude voice used as a control case).

**Converged on (6/6 dimensions, 3+ voices independently):**
1. `StateTransitionManager.evaluate_observation()` has zero production callers — later shown by the remediation plan to be part of a bigger gap (no code anywhere constructs a `PeerObservation` at all).
2. The BFT/permissionless threat model (Sybil, equivocation, reputation-decay) may not match the actual single-operator LAN deployment.

**User Challenge resolved:** classified as a genuine User Challenge per `/autoplan`'s own rules (converging review voices disagreeing with the stated direction). User's decision: **"Wiring + threat-model re-check, both required"** — PR #205 stays merged/unblocked; further P5/P6/P13 pattern work is gated on both landing first. Recorded in `PATTERN-SYNTHESIS.md` § "GATE on P5/P6/P13."

## 5. Eng Review consensus (Phase 3)

Full record: [`2026-07-12-eng-review-voices/`](2026-07-12-eng-review-voices/00-README.md) — 5 passes across 4 voices (Codex ×2, Kimi K2.6, Claude Sonnet 5, +1 stale Antigravity pass documented and corrected, not discarded).

**Consensus verdict: APPROVE WITH CHANGES.** Two new, concrete, code-level findings beyond the CEO review:
1. `_reorder_buffer`'s outer dict is unbounded across distinct `peer_id`s (found by all 4 non-stale voices) — the same DoS class P18 was meant to close, missed for this one structure.
2. The dedup key (`obs.to_json()`) omits `sequence`/`observer_provenance`, risking false-DUPLICATE rejection of valid observations (found by 3 of 4 voices — Claude's pass missed it, a useful data point on single-voice review reliability).

**Corrections made to the record during this phase:**
- The remediation-plan pass (`aac123e82eb006ede`) found the CEO review's own candidate wiring targets (`agent_tracker.py`/`heartbeat_monitor.py`) were wrong — corrected in both `PATTERN-SYNTHESIS.md` and the integration plan (struck through, not deleted, per this repo's additive-correction convention).
- Antigravity's Eng-review pass was found to describe a pre-PR#205 snapshot of the code (wrong line numbers, claims about missing bounds/reorder-buffer that are already fixed) — documented inline with a full line-by-line staleness table rather than silently dropped.
- One Kimi claim (docstring recommending `threading.Lock`) was checked against the actual docstring and found inverted — flagged, not corrected out.

## 6. Aggregated task list (post-gate, sequenced)

Per the remediation plan (`2026-07-12-stm-remediation-plan.md`) and the Eng-review synthesis:

| # | Task | Depends on | Effort | Source |
|---|------|-----------|--------|--------|
| 1 | Threat-model premise re-check (3 concrete questions: real witnesses? real trust boundary? real observed failure mode?) | Nothing — no code dependency | 2-4h | Remediation plan §2 |
| 2 | Go/no-go decision: proceed with P5/P6/P13 wiring as scoped, or descope to allowlist+mTLS | Task 1's verdict | 0h (decision only) | Remediation plan §3 |
| 3 | Wire `evaluate_observation()` into `backend_health_map()` (`orchestrator/connectivity.py:130`) | Task 2 = proceed | 3-5h | Remediation plan §1 |
| 4 | Resolve the two-FastAPI-app ambiguity (`fastapi_app.py` vs `src/perpetua_tools/orchestrator.py`) | Task 2 = proceed | 1-2h | Remediation plan §1 |
| 5 | Consume `.flushed` in the `/health` response, add integration tests | Task 3 | 2-3h | Remediation plan §1 |
| 6 | Bound `_reorder_buffer`'s outer dict (LRU/ref-counted eviction, matching `_peer_locks`/`_seen_observations`) | Independent — can land any time | Small | Eng review finding 1 |
| 7 | Fix dedup key to include `sequence` (or otherwise disambiguate causally-distinct observations) | Independent — can land any time | Small | Eng review finding 2 |
| 8 | Add structured logging/metrics for terminal decisions and buffer/cache sizes | Independent | Medium | Both reviews, multiple voices |
| 9 | Address durability gap: `AuditLog`/`ReputationLedger`/`EquivocationLog`/`KBucketTable` are in-memory only | Depends on Task 2 outcome (moot if descoping) | Medium-Large | Both reviews |

**Recommended order:** Task 1 first and alone. Tasks 6-7 (code-quality/DoS fixes) can land independently of the wiring gate at any time — they improve the module regardless of whether/when it gets wired in. Tasks 3-5, 9 wait on Task 2's verdict.

## 7. Error & Rescue Registry (this session)

Failures encountered and how they were caught/recovered, kept for institutional memory (also crystallized as lessons — see §9):

1. **Agent-tool vs SendMessage confusion** (×2) — spawned new agents instead of resuming intended ones. Caught by user, corrected via SendMessage each time; one accidental spawn became a useful control case.
2. **Worktree-isolated subagent staleness** — a CEO-review voice confidently claimed a false git-branch state (verified false via `git merge-base --is-ancestor`). Kept in the record with inline `[FALSE, see caveat]` annotations rather than silently corrected out.
3. **Kimi routing dead-end** — `openclaw agent --model openrouter/moonshotai/kimi-k2.6` failed (model not allowed for agent `main`). User pointed to the native `~/.kimi-code/bin/kimi` CLI, which worked. Also hit `-p`/`--yolo` flag incompatibility on the first native attempt.
4. **Codex apparent stall** — 33 minutes near-zero CPU vs. ~4 min for comparable voices. Force-killed, but it had just finished writing output before the kill landed — recovered intact rather than lost. A retry with `< /dev/null` (ruling out stdin-inheritance blocking) completed cleanly as a second data point.
5. **No hard ceiling on the original Codex dispatch** — a real gap; fixed retroactively by codifying a 15-minute default hard-ceiling pattern into the canonical `shell-hygiene` skill, not just applied ad hoc.
6. **Antigravity stale review** — an independently-run parallel review (not dispatched by this session) turned out to describe pre-PR#205 code. Caught by line-number cross-referencing against the actual file; documented with a full staleness table rather than discarded or silently trusted.

## 8. Failure Modes Registry (for the reviewed code itself, if wired in)

Consolidated from both review phases — the concrete ways this pipeline could fail in production, per §5-6 above:
- Silent memory growth via `_reorder_buffer`'s outer dict (peer-churn or gap-flood attack) — no logging/metrics would surface it before OOM.
- False-duplicate rejection of valid observations differing only in `sequence` — silent data loss, not a crash.
- Zero durable audit trail — any incident investigated after a restart has nothing to reconstruct from.
- Zero operational visibility — equivocation/Sybil-flag/rejection events are invisible outside the in-memory audit object.
- Structurally: witness-quorum/reputation/equivocation gates may have no real second witness to operate on at current LAN scale (per the threat-model premise question), meaning wiring could ship "working" code against a pipeline that can't yet do anything useful.

## 9. Dream state delta / lessons crystallized

7 lessons graduated into `.agent/memory` this session (`python3 .agent/tools/learn.py`, not hand-edited):
- Agent()-vs-SendMessage resume pitfall
- Worktree-isolated subagent staleness verification
- Production-caller verification discipline (grep before trusting a docstring)
- Threat-model premise re-check for single-operator LAN topology
- Verbatim multi-voice review preservation (never silently correct/discard a voice)
- Kimi CLI invocation path (native `kimi -p`, not openclaw agent override)
- 15-minute hard-ceiling default for backgrounded external CLI/agent dispatches

Also landed in canonical, cross-session skills (not just this repo's memory): `orama-system`'s `kimi-agent/SKILL.md` (review-voice usage), `gstack/SKILL.md` (triple-voice review pattern cross-link), and `shell-hygiene/SKILL.md` (hard-ceiling default) — so future sessions inherit these without re-deriving them.

## 10. Final Approval Gate Decision

**PR #205: unaffected, stays merged/unblocked.** No CRITICAL or BLOCK-severity finding applies to the code as already shipped — every BLOCK-leaning verdict (Codex run 1) was reconciled against a second independent pass reaching APPROVE WITH CHANGES on the same evidence, and no finding from either phase describes a correctness break in what's currently merged.

**Next increment of work: GATED**, per §6 above — task 1 (threat-model premise re-check) first, then a go/no-go decision before any P5/P6/P13 wiring proceeds. Tasks 6-7 (bounded reorder-buffer, dedup-key fix) are unblocked and can land independently at any time.

**Pipeline status: /autoplan complete.** Phase 0 (intake) → Phase 0.5 (Codex preflight) → Phase 1 (CEO review, quad voices, User Challenge resolved) → Phase 3 (Eng review, 5 passes) → Phase 4 (this gate) — all phases closed out. (Phase 2, design review, was not run — no design-system-facing surface in this PR; not applicable, not skipped in error.)

---

## Completion Summary

Ran the full `/autoplan` pipeline against an already-shipped PR at the user's explicit request. Produced two independently-verified findings (zero production callers for the whole peer-observation pipeline; unbounded reorder-buffer outer dict) that survive 4-5 independent review voices each, corrected two wrong claims mid-pipeline (a stale wiring-target guess, a stale Antigravity review) rather than letting them stand, and converted the whole exercise into 7 durable lessons plus 3 canonical-skill updates so the next multi-agent review fan-out starts from a stronger baseline. PR #205 ships as-is; the next increment of security-pattern work has a clear, sequenced, gated task list waiting on one cheap non-code decision.
