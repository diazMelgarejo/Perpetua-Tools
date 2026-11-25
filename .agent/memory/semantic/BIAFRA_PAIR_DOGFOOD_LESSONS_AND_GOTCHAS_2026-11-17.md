# Biafra pair dogfood: lessons and gotchas (2026-11-17)

Author/actor: Claude Code, self-reported. Evidence is the orama-system pull request
[519](https://github.com/diazMelgarejo/orama-system/pull/519) (local commits not yet pushed when
this card was written) and the paired Perpetua-Tools pull request
[516](https://github.com/diazMelgarejo/Perpetua-Tools/pull/516). The durable rules are the eleven
lessons graduated through `learn.py` in the same commit; this card holds the story and the
gotchas that did not earn a lesson. Facts are labeled verified, from a run this session.

## What was built (verified)

Biafra ratified additively as the outer seat (display name and `canonical_agent`, seat ids
unchanged); seat contracts and a Mechanism Card validator in `bin/agents/seat_contracts.py`; a
two-tier model and effort policy; correct W&B defaults pinned to the launcher; a free pair dogfood
test (`tests/test_pair_dogfood.py`); plan `docs/v2/76`. The decisions and open gaps are in
[docs/v2/76](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/76-biafra-outer-seat-canonical-plan.md)
once the pull request merges.

## Lessons graduated in this pass

| Lesson | Rule in one line |
| --- | --- |
| `lesson_5b83414d7c3c` | Pass `--prefix` for one-off npm installs; npm roots at the nearest ancestor project |
| `lesson_af0d30a51f39` | A bare `cat > file` blocks on stdin; hard timeout, stdin from /dev/null, check body files |
| `lesson_d0cc3e46382e` | A replace-to-end-of-file edit deletes later definitions; confirm symbols afterwards |
| `lesson_e01c3144855c` | A hook-rejected commit is no commit; check `git log -1`, stage named files |
| `lesson_a4a3cfaf0f51` | Normalize owner names, then substring-match; refuse non-ASCII or empty names |
| `lesson_c939186d4f2e` | Run every refusal before claiming a once-only marker |
| `lesson_534ac1055bf3` | Docs state only what code and tests enforce; test the wording |
| `lesson_1326d9f7430d` | Check memory before spending a limited probe; V4.1 rejects medium, default high |
| `lesson_4956db417faf` | A reviewing model is untrusted; reproduce every finding before acting |
| `lesson_8846ef3fbb9a` | Two-tier model and effort policy, in code; two CLI aliases break the rule |
| `lesson_1fa650cb3860` | A free dogfood proves boundaries, not model quality |

## Gotchas without a lesson

- **A plugin hook blocks commands that name `node_modules` paths.** It stopped a read-only check of
  a damaged home-directory project. It was not worked around; a restore script was prepared for the
  operator to run. The same family of hook blocks `.venv/` paths.
- **Home-directory `node_modules` damage is unresolved.** A bare npm install pruned a home project;
  88 packages were left renamed aside. A dry run of the restore script would restore 74 and skip 14
  where both copies exist. Until the operator applies it and checks that the gbrain and openclaw
  commands still run, treat that project as suspect.
- **A hook can write inside a worktree.** An untracked `.claude/hooks/.logs/` folder appeared under
  this memory directory. It is a tool log, not memory; it was excluded locally and not committed.
- **A `Write`-style tool that reports the file changed on disk is usually your own edit.** Do not
  treat those notes as outside interference.
- **Two W&B requests were approved and both were used.** The first (medium) failed with a known 400;
  the second (high) produced the review. No further live request is approved. Re-probe the provider
  the same day before any live pair cycle.
- **The pair dogfood is not a live cycle.** No model proposed a search rule. The gate and arm were
  never set.
- **Do not trust a push count from memory.** After the fix loop the orama-system branch was 6
  commits ahead of the pushed head, not 5; a commit I assumed had landed was still staged.

- **A synthetic benchmark is not a live test.** The first live pair loop was set up with an invented
  held-out corpus and an answer key I wrote. The operator corrected this: live turns exist to test
  real-world situations. The run was stopped before its request completed (an attempt marker
  existed, so one request may have been started and cut off). Real CodeRabbit comments on the
  pair's own pull request were the right task; look for existing real feedback first.

- **The first three candidates ran before anyone read them, with the provider key in the scorer's
  environment.** A side agent flagged it; the denylist vet was bypassable. The scorer now runs
  candidates through `sandbox_run` (scrubbed environment, kernel sandbox, allowlist vet). The first
  three candidates were small and harmless; that was luck, not control.

- **The second sandbox commit was also flawed.** Allow-by-default, a read root that can become the
  home folder, and a vet that a builtin-named default parameter beat. Three security reviews, three
  real findings; each reproduced and fixed. The runbook card is `PAIR_LOOP_RUNBOOK_AND_48H_BEST_PRACTICES_2026-11-17.md`.

- **The first spend guard duplicated logic that already existed.** Perpetua-Tools had `CostGuard`, a
  provider policy format and a frugality router; the orama-only ledger was replaced, unpushed, by one
  shared guard (`4a87fb0199f1`). I had searched neither repository first.
- **CodeRabbit found four real gaps in the billing notes** (a 402 has two causes, the certification did
  not cover pay-as-you-go, the runbook relied on that certification alone, and the SDK retried a 429).
  Fixed with an attestation requirement, a live-verified provider policy, and `max_retries=0`.
- **Live turns are blocked until the operator attests.** That is the intended behavior of the
  guard, not a
  fault.

## Open items

Operator decisions: whether Wanda's soul card or the W&B Cline launcher governs the route; the
stall window default (3); where the evaluator digest is pinned at run start; the persona
elaboration for Biafra; applying the home `node_modules` restore. Pushes of both branches wait for
the operator.

## Later status (2026-11-23, append-only)

Two of the operator decisions listed under "Open items" were made on 2026-11-23. G11: the W&B route
is split by role; Wanda keeps the OpenAI client and the Biafra seats are designated to use Cline
under the shared spend gate once the launcher can bound total output and request count. G6: the
persona is accepted as written. See the `DECISIONS.md` entries of that date. The other items listed
there are unchanged.
