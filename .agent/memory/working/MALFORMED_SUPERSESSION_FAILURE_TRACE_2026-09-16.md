# Malformed Supersession Record — Failure Trace & Prevention Rules

**Date:** 2026-09-16
**Agent:** cline-gate4-halfa (GLM-5.3-Flash medium, Cline-Bot envelope)
**Incident:** commit 7482f1c8 added a malformed graduated candidate
`candidates/graduated/848da335af02.json` (a duplicate supersession of
lesson_f6cbb9825f37). Fixed by 2ab6079: the valid supersession
`813caf53e6bd` (authored 2026-09-14, evidence-dated before my commit) was
kept with its required historical link, and the malformed duplicate was
moved to `candidates/rejected/` with an audit annotation.

## What happened (verified against live refs)

1. The PR #391 hygiene thread asked for a superseding record correcting
   the representation claim of lesson_f6cbb9825f37.
2. cline-gate4-halfa read the review thread and the target lesson, then
   hand-wrote a new graduated candidate JSON (invented `supersedes` field,
   hash-derived id `848da335af02`, self-asserted `status: accepted`,
   self-graduated decisions with reviewer = the writing agent) and pushed
   it to the PR branch.
3. lesson_813caf53e6bd — one of the 7 graduated candidates already in this
   PR's file list, evidence dated 2026-09-14 — already contained the exact
   correction. The hand-written record was a duplicate with a schema the
   memory tooling does not define.

## The four root causes

1. **No dedupe-first pass.** The PR's own file list showed
   `813caf53e6bd.json` as an added graduated candidate and its evidence
   timestamp (2026-09-14) predates the commit (2026-09-16) — both signals
   were in hand and unread. Rule: grep candidates/graduated + semantic/
   lessons for the lesson id/topic BEFORE writing any record.
2. **Schema by guess.** The JSON was hand-written instead of produced by
   the canonical tooling (`learn.py` / `capture_lesson.py`). Invented
   fields (`supersedes`), an id minted outside the memory system's hashing,
   and a status self-asserted rather than pipeline-granted.
3. **Self-graduation.** `graduated` status requires a reviewer +
   decision_ref from an evidence-backed review — the exact invariant the
   anamnesis `PromotionPipeline` enforces (candidate -> reviewed ->
   graduated, forward-only). The author of a record can never be its
   graduation reviewer.
4. **Agent-identity ambiguity.** The commit is git-authored with the operator's configured
   identity in the worktree (private email redacted per doc 46; see
   commit 7482f1c8 metadata); the JSON mentioned `cline-gate4-halfa`. Neither proves the executing agent identity.
   Agent identity belongs in the agent-envelope (coordination board) and
   optionally a git trailer — never in hand-edited reviewer fields inside
   memory records.

## Missed validator signals

- The memory validators exist and would have rejected the record:
  - `.agent/memory/validate.py` (heuristic pre-filter: min claim length,
    content-word count, exact-dup detection — the dup check alone would
    have flagged the near-duplicate of 813caf53e6bd);
  - `scripts/review/check_episodic_append_only.py` (episodic JSONL
    byte-prefix + schema discipline, CI-enforced by
    `.github/workflows/episodic-append-only.yml` on this PR);
  - the candidates/ JSONL validator in CI ("memory JSON/JSONL validation")
    that ultimately rejected the record post-push.
- What ran before the push: repo hygiene hooks only. The gap: no staged
  `.agent/memory/**` validation stage in `.githooks/pre-commit`.

## Prevention rules (binding on this agent)

1. DEDUPE-FIRST: grep candidates/graduated + semantic/lessons for the
   lesson id/topic before writing any record.
2. NEVER hand-write candidates/ or episodic JSON: use `learn.py` /
   `capture_lesson.py`, or submit through the anamnesis Ledger +
   PromotionPipeline with an evidence-backed review pass.
3. NEVER self-graduate: graduation requires a reviewer + decision_ref from
   a review the author did not write.
4. VALIDATE before commit: run `.agent/memory/validate.py` and the
   episodic/candidates checkers on staged `.agent/memory/**` files.
5. IDENTITY: agent identity in the agent-envelope (board) and/or a git
   trailer; never hand-edited reviewer fields inside memory records.
6. SUPERSESSION: cite the superseded lesson id and append the superseding
   record alongside it — never edit or duplicate the original.

## Recommended validator wiring (for reviewer decision)

Add a staged-memory stage to `.githooks/pre-commit` (only when staged
files touch `.agent/memory/**`):

```bash
if git diff --cached --name-only --diff-filter=ACMR | grep -q '^\.agent/memory/'; then
  python3 .agent/memory/validate.py --staged || exit 1
  # plus a records-schema check: every staged .json parses strictly
  # (duplicate-key + non-finite rejection) and carries required fields;
  # a directly-added graduated/rejected candidate requires a decision_ref
  # (blocks self-graduation at the hook, closing root cause 3).
fi
```

Mirror the same checks as a CI job (hooks are skippable via --no-verify),
extending the episodic-append-only workflow added in this PR. Keep the
OSSF-1 saga boundary: this is PT's own memory discipline, not an OSSF
hook copy (OSSF-1 gates bin/orama-system SKILL.md files only).

## Validation of this dossier

- Run with the PR's own gate: `python3 scripts/review/
  check_episodic_append_only.py --repo . --base <base-sha> --worktree`
  after staging.
- No candidates/ or episodic JSONL records were hand-written for this
  dossier (working-memory narrative only, per PR #391's
  working-memory-first discipline).
