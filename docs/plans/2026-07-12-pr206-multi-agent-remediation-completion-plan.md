# PR #206 Multi-Agent Remediation Completion Plan

Date: 2026-07-12  
Repository: `diazMelgarejo/Perpetua-Tools`  
PR: `#206`  
Branch: `2026-07-11-001-salvage-heartbeat-skill-wrapper`  
Base: `main`

## Purpose

Complete the remaining CodeRabbit remediation safely with multiple agents, without stale overwrites, duplicated fixes, or surface-only patches.

At plan creation, the branch was 71 commits ahead of `main`, 0 behind, and changed 74 files. Because the branch is large and still active, every agent must treat the current branch head—not an earlier review comment or cached blob—as the source of truth.

## Governing rules

1. Re-read every owned file from the current PR head before editing.
2. Fix the owning abstraction, not a symptom or individual assertion.
3. One file owner at a time; no overlapping edits across lanes.
4. No force-push, history rewrite, or branch reset.
5. Do not weaken tests, skip CI paths, suppress errors, or add duplicate implementations.
6. Preserve append-only memory and audit records unless an exact lifecycle operation requires a transactional move.
7. Each lane must add or update regression tests for the contract it owns.
8. The integrator must review each lane’s diff before it lands on the PR branch.

## Current remediation status

### Implemented; verify rather than rewrite

- Fresh `agent_register` clears a prior killed state.
- Audit persistence includes original hashes, verifies replay, and is disk-first.
- Post-execution episodic persistence redacts secrets before writing.
- Tracked text files use explicit UTF-8 in the reviewed memory paths.
- Memory search subprocesses use a bounded timeout and fail open.
- Descriptor-based rewrites handle partial `os.write` calls.
- Candidate lifecycle moves roll back the new location when cleanup fails.
- Stale `LESSONS.md` migration cannot override authoritative `lessons.jsonl` rows.
- Review queue refresh logs exceptions while remaining fail-open.
- Equivocation is scoped to the same authenticated observer identity.
- Reorder-buffer conflicts preserve the first buffered observation.
- Rejected buffered entries advance a processed watermark so successors are not stranded.
- GossipBus exposes public connection/event insertion helpers.
- Queue claim row and heartbeat event are committed in one SQLite transaction.
- Coordination claim code no longer accesses `GossipBus._db_path` directly.
- `scripts/agent_coordination_core.py` exists as the retained implementation module.

### Remaining integration risk

- Finalize and verify the `agent_coordination_core` / facade / legacy-entrypoint split.
- Prove direct legacy execution routes heartbeat commands through the corrected facade without circular imports or `NameError`.
- Add missing regression tests for transaction rollback, lock contention, buffered conflict handling, and rejected-buffer successor flushing.
- Complete remaining UTF-8/context-manager cleanup in `show.py` and `skill_loader.py` if still present at current head.
- Apply documentation-only Markdown hygiene comments after runtime code is stable.
- Resolve or explicitly disposition the duplicate memory lesson through the repository lifecycle tooling.
- Run full CI and perform a final CodeRabbit comment audit.

## Multi-agent topology

Use isolated worktrees or branches created from the latest PR head. Agents must not push directly to the shared PR branch. A single integrator cherry-picks or merges verified lane commits.

| Lane | Owner | Exclusive files | Depends on |
|---|---|---|---|
| A — Coordination compatibility | Agent A | `scripts/agent_coordination.py`, `scripts/agent_coordination_core.py`, `scripts/agent_coordination_legacy.py`, coordination tests | none |
| B — SQLite transaction verification | Agent B | `orchestrator/gossip_bus.py`, `tests/test_agent_coordination_queue.py`, new focused GossipBus tests | Lane A API contract only |
| C — STM ordering/security tests | Agent C | `orchestrator/state_transition_manager.py`, `orchestrator/equivocation.py`, `tests/test_state_transition_manager.py`, `tests/test_equivocation.py` | none |
| D — Memory/tool durability | Agent D | `.agent/.blend-preview/**`, memory/tool-specific tests | none |
| E — Documentation hygiene | Agent E | listed `docs/phase-0-specifications/**` Markdown files only | runtime lanes stable |
| F — Integrator/reviewer | Integrator | this plan, PR body, merge resolution, final verification | all lanes |

No lane may edit another lane’s exclusive files without handing ownership back to the integrator.

## Lane A — Coordination compatibility

### Objective

Complete the three-layer contract:

- `agent_coordination_core.py`: retained implementation and parser/dispatch core.
- `agent_coordination.py`: corrected public facade and patched reducers/transaction behavior.
- `agent_coordination_legacy.py`: thin compatibility entrypoint that delegates to the facade when executed directly.

### Required behavior

- Importing any of the three modules must not recurse or partially initialize globals.
- `python scripts/agent_coordination.py --help` succeeds.
- `python scripts/agent_coordination_legacy.py --help` succeeds.
- Legacy heartbeat subcommands route to the facade implementations.
- Existing import callers retain the established public surface.
- No copied second implementation is introduced beyond the retained core.

### Tests

Add subprocess-level tests for:

- direct legacy `--help`;
- legacy heartbeat `list`, `check`, and `dashboard` against a temporary DB;
- import order permutations: facade first, legacy first, core first;
- absence of `NameError` and circular-import failures.

### Done condition

All coordination and heartbeat tests pass, and `git grep` shows heartbeat handlers have one implementation owner in the facade.

## Lane B — Atomic claim transaction

### Objective

Prove the exclusive claim row and append-only claim event are one ACID unit.

### Required tests

1. Successful claim persists exactly one claim row and one heartbeat event.
2. Duplicate claim returns a clean failure and emits no second event.
3. Injected event-insert failure rolls back the claim row.
4. Injected commit failure leaves neither mutation visible.
5. SQLite lock contention follows bounded retries and returns a clean failure.
6. `_release_claim` uses the public GossipBus connection API.
7. Embedding scheduling occurs only after commit.

### Done condition

No state can exist where a claim row is committed without its heartbeat event or vice versa.

## Lane C — STM ordering and authenticated equivocation

### Objective

Prove the deeper ordering/security contracts instead of merely matching current assertions.

### Required tests

- Identical retry for the same `(epoch, sequence)` remains buffered without replacement.
- Conflicting retry for the same key keeps the first observation and records/rejects the conflict.
- A rejected buffered observation does not strand sequence `N+1`.
- A later retryable gap remains explicit and can be retried.
- Same provenance but different observer identities is ordinary disagreement, not equivocation.
- Same observer identity issuing contradictory signed observations is equivocation.
- Reputation penalty applies only to the accountable observer.
- LRU eviction followed by a new observation for the evicted peer is accepted as fresh.
- Sybil same-bucket test asserts the exact expected signal and accepted decision.
- Concurrency tests use a real suspension barrier so same-peer serialization and different-peer overlap are actually exercised.

### Done condition

Ordering watermarks, buffer ownership, rejection semantics, and equivocation attribution are deterministic and covered by tests.

## Lane D — Memory and tool durability

### Objective

Close remaining repeated I/O and retry-safety issues through shared conventions.

### Tasks

- Verify all reviewed tracked-text opens specify `encoding="utf-8"`.
- Replace unmanaged reads with context managers in `show.py` and `skill_loader.py`.
- Ensure `learn.stage()` returns an existing valid deterministic candidate unchanged.
- Verify non-string salience timestamps follow the invalid timestamp path.
- Verify naive timestamps in decay are interpreted as UTC.
- Add tests for short writes, timeout fallback, lifecycle rollback, stale lesson migration, and candidate idempotency.
- Resolve the duplicate PR #205 lesson using the existing `supersedes` lifecycle mechanism; do not hand-delete JSONL history.

### Done condition

All tracked text I/O is explicit and closed, retries are idempotent, and lifecycle operations cannot leave duplicate locations.

## Lane E — Documentation hygiene

Only after runtime lanes are stable:

- Correct heading levels in the listed CEO/engineering review documents.
- Remove leading indentation from Markdown headings.
- Add language identifiers to all flagged fences, normally `text` for diagrams.
- Update stale T3 status wording to completed or clearly historical in every occurrence.
- Make no substantive architectural edits while performing Markdown hygiene.

### Done condition

Repo hygiene reports no heading/fence violations in the changed documentation set.

## Integration order

1. Lane D small I/O/idempotency fixes.
2. Lane C STM/equivocation tests and any required implementation correction.
3. Lane B transaction regression tests.
4. Lane A compatibility split finalization.
5. Lane E documentation hygiene.
6. Integrator resolves only semantic conflicts, never by choosing an entire side blindly.
7. Run complete verification.

If Lane A changes the public coordination import shape, Lane B must rebase or refresh before final test approval.

## Required verification

Run from a fresh checkout of the PR branch:

```bash
python -m pytest tests/test_agent_coordination.py -q
python -m pytest tests/test_agent_coordination_heartbeat.py -q
python -m pytest tests/test_agent_coordination_queue.py -q
python -m pytest tests/test_audit_log.py -q
python -m pytest tests/test_equivocation.py -q
python -m pytest tests/test_state_transition_manager.py -q
python -m pytest tests/test_peer_observation.py -q
python -m pytest -q
```

Then run repository gates:

```bash
python scripts/review/repo_hygiene.py .
bash scripts/git/check_identity.sh
```

Also run direct CLI smoke tests:

```bash
python scripts/agent_coordination.py --help
python scripts/agent_coordination_legacy.py --help
```

## Final CodeRabbit audit

The integrator must build a checklist from review `#4679263817` and mark every comment as one of:

- fixed by commit;
- already fixed by a newer branch commit;
- superseded by a deeper abstraction fix;
- intentionally not applicable, with evidence.

No comment may be closed merely because the referenced line moved.

## Merge gate

PR #206 is ready only when all are true:

- full pytest passes;
- repo hygiene and identity checks pass;
- direct legacy CLI smoke tests pass;
- no private `_db_path` access remains in coordination code;
- no transaction can strand a task claim;
- no buffered successor is stranded after terminal rejection;
- equivocation cannot penalize an unrelated observer;
- audit replay rejects tampered history;
- secret-bearing fields are redacted before persistence;
- CodeRabbit has no unresolved actionable comment, or each remaining thread has an evidence-backed disposition;
- PR body accurately reflects the final expanded scope.

## Agent handoff format

Each agent must report:

```text
Lane:
Branch/worktree:
Starting PR head:
Files changed:
Root cause addressed:
Tests added/updated:
Commands run and results:
Commit SHA:
Known risks or follow-up:
```

The integrator must reject handoffs missing the starting head or test results.
