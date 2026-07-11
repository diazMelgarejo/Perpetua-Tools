# Eng Review Synthesis — PR #205 (`phase-2-stm-concurrency-dedup`)

`/autoplan` Phase 3 (Eng review), 5 review passes across 4 model voices, 2026-07-12. Companion to the CEO quad-review at `../2026-07-12-ceo-review-quad-voices/`.

| # | File | Voice | Verdict | Reliability |
|---|------|-------|---------|-------------|
| 1 | [01-codex-run1.md](01-codex-run1.md) | Codex GPT-5.5, run 1 | **BLOCK** | Clean |
| 2 | [02-codex-run2.md](02-codex-run2.md) | Codex GPT-5.5, run 2 (stdin closed) | APPROVE WITH CHANGES | Clean |
| 3 | [03-kimi.md](03-kimi.md) | Kimi K2.6 (native CLI) | APPROVE WITH CHANGES | Clean except one flagged misread |
| 4 | [04-claude-sonnet.md](04-claude-sonnet.md) | Claude Sonnet 5 (medium depth) | APPROVE WITH CHANGES | Clean |
| 5 | [05-antigravity.md](05-antigravity.md) | Antigravity (Gemini), run independently by the user in parallel | APPROVE WITH CHANGES | **Grounded in a stale pre-PR#205 snapshot — see caveat in file** |

**Voice 5 note:** Antigravity's review was run independently by the user (not dispatched by this session) and discovered afterward sitting in the shared scratch directory. Its core findings (unbounded caches, no reorder buffer) describe the code as it existed *before* this PR's P9/P18/P2 hardening landed — its cited line numbers (167-169) don't match the current 609-line file, and the current code already has the `_RefCountedLock`/`OrderedDict`+`_touch_cache()`/full reorder-buffer implementation it claims is missing. Kept for the record with the staleness documented inline rather than discarded — its two findings that don't depend on the stale premise (docstring overstates production status, zero observability) independently corroborate voices 1-4.

## Convergent findings (3-4 of 4 passes agree)

1. **Outer `_reorder_buffer` dict is unbounded across distinct `peer_id`s** (all 4). The per-peer inner `OrderedDict` is correctly capped at `reorder_buffer_max` and well-tested, but the outer `peer_id → buffer` dict has no LRU/eviction treatment — the same unbounded-memory-DoS class P18 was supposed to close, just missed for this one structure. **This is the single most actionable new finding from Eng review** — a real gap, not a strategy question, independently found by every voice.
2. **Zero production callers / docstring overstates production status** (all 4, corroborating the CEO-review finding independently via `grep`).
3. **The per-peer `asyncio.Lock` is not currently load-bearing** — `_evaluate_locked()` has no `await` in its critical section, so asyncio's cooperative scheduling already prevents interleaving with or without the lock (Claude empirically verified this by swapping in a no-op lock and re-running the concurrency test with an identical result). Not a bug, but means the one test claiming to prove lock-safety doesn't actually exercise contention (Claude, Kimi, both Codex runs).
4. **Zero logging/metrics/observability** in the module (all 4).
5. **`AuditLog` is in-memory only, no persistence** — restart wipes the entire forensic trail (Claude, Kimi explicit; both Codex runs via "observability is audit-only").
6. **`InvalidObservationError` is declared but never raised** — dead code (all 4).
7. **Dead `else` branch** in `_apply_observation`'s `new_status` assignment — unreachable since only `APPROVED`/`SYBIL_FLAGGED` reach that point (all 4).

## Near-consensus finding Claude missed

**Dedup key (`obs.to_json()`) omits `sequence` and `observer_provenance`** — two observations differing only in sequence number can collide and get falsely rejected as `DUPLICATE` before the monotonic/stale gate even runs. Found independently by **both Codex runs** (High confidence, citing `state_transition_manager.py:294-296` + `membership.py:404-434`) and **Kimi** (Low confidence, same citation). **Claude Sonnet's review does not mention this at all** — a real 3-out-of-4 gap in Claude's pass worth noting when weighing single-voice reviews going forward. This is a genuine correctness bug, not just a DoS/hardening gap, and should be prioritized alongside finding 1.

## Kimi-specific claim to disregard

Kimi's review states "the docstring says synchronous callers should use `threading.Lock`." Checked against the actual docstring (`state_transition_manager.py:183-192`): it says the opposite — `asyncio.Lock` is the correct primitive and explains why alternatives (including `threading.Lock`) were rejected. Likely a misread, not a real finding. Kept verbatim in `03-kimi.md` with this correction noted inline, consistent with how the CEO quad-review handled other voices' incorrect claims (never silently edited out).

## Verdict variance within the same model

Codex's two runs found essentially the same technical issues (finding 1, the dedup-key bug, the dead-lock-test issue, zero observability) yet landed on different verdicts — **BLOCK** on run 1, **APPROVE WITH CHANGES** on run 2. This is worth flagging as a general caution: a single model's verdict label can swing across runs even when its underlying evidence is stable — weight the cited findings over the verdict label when only one voice is available, and prefer running more than one pass when a verdict is going to gate a real decision.

## Consensus verdict

**APPROVE WITH CHANGES** (3 of 4 passes explicitly, and Codex's own second pass revised its harsher BLOCK down to the same conclusion on reflection). Two concrete fixes are now clearly warranted before or shortly after any real caller wiring lands (see `../2026-07-12-stm-remediation-plan.md` for the wiring/threat-model gate this sits behind):

1. **Bound `_reorder_buffer`'s outer dict** the same way `_peer_locks`/`_seen_observations` are bounded (LRU or ref-counted eviction) — closes a real DoS gap in what P18 was supposed to fully cover.
2. **Fix the dedup key to include `sequence`** (or otherwise disambiguate causally-distinct observations) — closes a real correctness bug that can silently drop valid data as a false duplicate.

Both are additive to, not blocking, the already-recorded P5/P6/P13 gate (production wiring + threat-model premise re-check) — these are implementation-quality fixes independent of whether/how the pipeline gets wired in.
