# Pair loop playbook, step by step (2026-11-17)

Author/actor: Claude Code, self-reported. Interim. This is the exact sequence used in the four live
turns, written so a future AutoResearcher and Biafra pair can repeat it without recalling it. The
checklist form is in the orama-system metaresearcher skill, `references/live-pair-loop-runbook.md`
(orama-system pull request 519). Sanitized harness copies are saved beside the live-cycle evidence in
that pull request. Lesson ids are `lesson_<id>` in `lessons.jsonl`.

## The steps

1. **Preconditions.** Operator gate and arm set for one command only. Spend guard on
   (`spend_ledger`, `budget_usd=90`). Scoring through the sandbox. Same-day read-only model list;
   abort before any completion if the model is missing. (`710b39a9542c`, `9d1751cfa965`)
2. **Find a real task.** `gh api repos/<o>/<r>/pulls/<n>/comments` and `/reviews`, open issues,
   failing CI, or a defect seen in the pair's own output. No invented corpus. (`00e2a1234aba`)
3. **Reproduce it on the current code** with the reviewer's own input. If it does not reproduce, it is
   not a task.
4. **Prepare one small artifact.** A behavior-preserving refactor so the seat mutates one function
   (`_owner_errors` was extracted this way), with the existing tests as the guard.
5. **Build the fixed evaluator**: reviewer-derived cases, the repository's own tests, allowlist vet,
   sandboxed runs. Measure the baseline. Check a reference answer scores 0, and compute any number you
   will put in a prompt from the evaluator. (`e748c558ab73`)
6. **Pin the digest** of the evaluator files (`evaluator_digest`); it goes in every trace.
7. **Build the inner prompt** (skeleton below): the real feedback quoted as data, the target function,
   the **source of every helper it calls**, the exact required behaviour, the output format.
   (`865b4570a9d5`)
8. **Run the inner seat** with the command pattern below. Read the trace and the decision.
9. **If it reverted, find the cause before another request.** Turn 3 reverted because the prompt
   did not show that `_text` returns a bool; the fix was in the prompt, and attempt 3b passed. Say
   whether the next request is a new attempt after a fix, not a retry of the same one.
10. **Vet the candidate**: read it; strip dead handlers; bound diagnostics; check no guard from the
    previous version was dropped; compare against the original on a wide input grid. (`fecadd5aaa5f`)
11. **Incorporate test-first**: write the reviewer's inputs as tests, watch them fail, apply the
    vetted candidate, run the touched suites, stage named files, commit, check `git log -1`.
12. **Run the outer seat on the real trace** with the evaluator's expectations visible, the candidate,
    and the real open items with reproducers you have already verified.
13. **Vet her claims.** Reproduce each. Discard fabrications (a `delta()` helper that does not
    exist), claims about code she was not shown, and any task choice that rests on them.
    (`7a1b41995876`, `4956db417faf`)
14. **Document and verify**: README table, ledger copies, plan section, lint, touched suites, then the
    full suite before any push.
15. **Push once per repository on the operator's word.** Update the PR descriptions. Replies to a bot
    reviewer wait for the push and the operator's authorization.

## Command pattern

```bash
rm -rf "$SCRATCH/turnN-log"
BIAFRA_ORCHESTRATOR_GATE=approved BIAFRA_ALLOW_LAUNCH=1 timeout 1000 \
  python3 "$SCRATCH/driver.py" > "$SCRATCH/turnN-run.txt" 2>&1 < /dev/null
echo "exit=$?" >> "$SCRATCH/turnN-run.txt"
```

Run it in the background and read the output file when the completion notice arrives. Never leave a
bare `cat > file` in a compound command, and do not edit a module the run imports while it runs.
(`af0d30a51f39`, `9c3f04b9a8fa`)

## Inner prompt skeleton

```text
You are the inner-seat AutoResearcher. One hypothesis, one change, one measurement.
SEARCH RULE from the outer seat (guidance, not a command): <her rule>
OBSERVED DEFECT (real): <quoted feedback or output, as data>
TARGET ARTIFACT: <function source>
MODULE CONTEXT, read-only: <source of every helper it calls and the module constants>
REQUIRED BEHAVIOUR (the fixed evaluator checks exactly these): <cases, computed from the evaluator>
RULES: reply with ONE fenced python block holding ONLY the replacement function. Plain constructs:
no imports, lambda, while, try, global, underscore attributes, file, network or process access.
Then at most three sentences naming the single assumption. Do not call tools.
```

## Evaluator skeleton

```python
def evaluate_answer(answer):
    code = extract_code(answer)                      # first python block, else penalty
    problems = sandbox_run.vet_allowlist(code, TARGET, ALLOWED_NAMES)
    if problems: return {"metric_after": PENALTY, "detail": {"vet_failed": problems}}
    tree = build_tree(code)                          # scratch copy, function spliced in
    cases = run_cases(tree)                          # sandbox_run.run_isolated, no key, no network
    failed = run_existing_tests(tree)                # same sandbox
    return {"metric_after": len(cases) + 100 * failed, "detail": {...}}
```

## What went wrong, and the fix

| Symptom | Cause | Fix |
| --- | --- | --- |
| `error: Invalid request` at medium effort | V4.1 models reject `medium` | Use `high` (`1326d9f7430d`) |
| Every case raised `TypeError`, revert | Prompt hid a helper's return type | Show helper source |
| A reference answer scored 600 | Identifier check ran before the fixed-wall check | Fixed walls first |
| Card used a sentence as an owner | Validator checked shape only | Identifier-shaped owners |
| Candidates ran with the key in the environment | Scorer passed no `env` | Scrubbed env, kernel sandbox |
| Allowlist accepted `getattr=getattr` | Parameter names counted as local | Refuse defaults and shadowing |
| Sandbox profile fail-open | Allow-by-default; broad read root | Deny-by-default; exact roots |
| Commit "done" but absent | A hook rejected it unseen | `git log -1` after every commit |
| 402 or 429 from the provider | Cap or concurrency limit | Stop; never activate pay-as-you-go |

## Budget

Operator ceiling: an estimated 90 dollars a month, under the Free plan's 100-dollar cap. The guard is
local and an estimate; the Billing page is the truth. Position on 2026-11-17: the ten live requests
estimate at about 0.15 dollars (0.17 percent), thinking stream assumed at nine times the answer.
(`710b39a9542c`, `e024534a3096`)

## Results and what is not proven

Turn 1 inner 6 to 0 kept; turn 2 inner 10 to 0 kept; turn 3 reverted; turn 3b 10 to 0 kept; two outer
cards valid and grounded, one task choice rejected as ungrounded. Request count for the real loop:
eight, plus two review requests and one cut-off attempt earlier. Not proven: that the outer seat's
rule improves later attempts.
