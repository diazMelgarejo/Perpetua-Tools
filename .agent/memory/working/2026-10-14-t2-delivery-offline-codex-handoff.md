# Working memory: offline-Codex hand-off for the T2 delivery work (2026-10-14)

> **Provenance:** sanitized, tracked copy of a local hand-off written for an agent that can
> read, edit and test but **cannot push** (no network, no `gh`). Workstation paths are
> rewritten to `~/...` or `$HOME/...`; the untracked original, with absolute paths, sits in
> the worktree hub beside the worktrees it describes.
> **Snapshot:** verified live against GitHub and the local worktrees on 2026-10-14. Working
> memory ages quickly: after any merge below, the PR table is stale. Re-verify with `gh`
> before acting on a state claim.
> **Author:** claude-main, for the operator. **Board:** rows 4303-4337 hold the history.

---

## 0. Read this first

**Your situation:** you can read, edit, test and commit locally, and post to the local
GossipBus board (it is a local SQLite file, so it works offline). You **cannot** push,
open PRs, or call `gh`. Someone with network access (the operator, or an online agent)
must publish whatever you produce.

**So your job is to produce reviewable, self-verifying work product and a precise board
row, not to publish.** Section 6 gives the exact outbox procedure.

**What is waiting on a human, not on you:** every open PR below needs the operator's merge
decision. Nothing here is to be merged, force-pushed or "fixed up" on someone else's
branch.

---

## 1. What this engagement was (one paragraph)

Starting from a hung Exa MCP daemon, the work grew into: fixing that daemon, discovering
that every commit on this Mac was silently failing a pre-commit hook, closing out
Task 6 (phylax startup race and the ADR), then — on 2026-10-14 — analysing the T2
qualification gap receipt and two proposed Codex patches, and replacing them with a
verified fix. Along the way two reusable bug classes and a review-verification discipline
were written into the canonical skills and PT memory.

---

## 2. State of every PR (verified)

### Open — need review / operator merge

| PR | Repo | Branch @ head | CI | What it is |
| --- | --- | --- | --- | --- |
| [#36](https://github.com/oramasys/oramasys/pull/36) | oramasys/oramasys | `feat/t2-admitted-observation-delivery-20261014` @ `afea6f48` | all green incl. 6 offline-oracle cells (production, policy-r3, core-r3 × py3.11/3.12); CodeRabbit pending | **T2 delivery fix** (see §3.D) |
| [#37](https://github.com/oramasys/oramasys/pull/37) | oramasys/oramasys | `fix/terminal-evidence-source-checkout-20261014` @ `9f52ad6e` | all green, CLEAN | Test-harness fix (§3.E). Independent of #36 |
| [#404](https://github.com/diazMelgarejo/orama-system/pull/404) | diazMelgarejo/orama-system | `docs/skills-shell-and-review-verification-lessons-20261014` @ `8eaad098` | green; `test (3.11)` pending | Canonical skill updates (§3.F) |
| [#441](https://github.com/diazMelgarejo/Perpetua-Tools/pull/441) | diazMelgarejo/Perpetua-Tools | `docs/t2-delivery-and-verification-lessons-20261014` @ `911f9b17` | green; `lint-and-test` + CodeRabbit pending | 7 lessons via `learn.py`. Lockstep with #404 |

`UNSTABLE` merge state on these means **pending** checks, not failing ones.

### Merged during this engagement (context only)

phylax #11, oramasys #34, orama-system #400, #401, #403, Perpetua-Tools #438, #439, #440.

---

## 3. What each thread did and why (so you can challenge it)

### A. Exa MCP daemon crash loop (orama-system #400, merged)
The shared daemon had crash-looped since about 2026-08-22. Root cause: on backend EOF it
called `loop.stop()` from a background task, racing `asyncio.run()`'s own future. Replaced
with an `asyncio.Event` shutdown, guarded a `ProcessLookupError` that only surfaced once
that path became reachable, and pinned the backend to `exa-mcp-server@3.4.2`. Codex's
`mcp-remote` pin was raised to 0.14.3 in a local config outside any repo.

### B. Guard lint script + free-slot line (orama-system #403, PT #439, merged)
`check_markdown_lint.sh` used `mapfile`, which stock macOS bash 3.2 lacks, so the
pre-commit hook failed every commit on this machine. Fixed, then adopted PT's NUL-delimited
variant as canonical and added it to `GUARD_SYNC_EXECUTABLES`. **`.githooks/pre-commit` is
deliberately NOT in the manifest**: PT's is a parallel dispatcher, orama's is sequential.

### C. Task 6 / phylax (phylax #11, oramasys #34, orama-system #401, merged)
Startup race: `ensure_active_key` decides first-key initialization in one transaction.
Darwin-only `openat(O_CREAT)` race fixed with a single retry without `O_CREAT`.
**Declined** a reviewer-recommended "must equal a pristine record" gate: it fails both
restart tests because recording a grant legitimately mutates the active key and the check
runs on every start. ADR 71 + plan 72 are canonical in orama-system; oramasys holds
link-only pointers.

### D. T2 observation-delivery gap (oramasys #36, OPEN) — the main open work
Your two proposed patches were **verified, not applied**. Findings:

1. **Transport already exists.** Core's `run_with_plugins(graph, state, *, delivery, gate)`
   is present at the production pin `609ff0e`, Core #12 and #13. It detaches per listener,
   fails closed and closes the iterator. The patch's `ainvoke(delivery=)` duplicates it and
   is weaker: measured on a patched scratch Core, a listener mutating `observation.state`
   leaked into the final state; via `run_with_plugins` it did not. It would also force a
   new Core release and pin bump.
2. **The "Core-owned lifecycle seam" already exists:** `DurableStartGate.before_start`
   ("immediately before the actual callable receives control"), implemented by
   `AdmissionGate`.
3. **The real gaps were identity and persistence.** `BoundedObserver` took
   `attempt_id/hold_id/fence_epoch` as constructor strings although a run has many
   attempts; blank ids make `UnknownDisposition` raise and `_trip_circuit` returned on that
   `ValueError`, silently dropping the record. And `StepLedger.mark_unknown` had **no
   production caller**, so no durable disposition could exist by any wiring.

What #36 does: `BoundedObserver.bind_authority(identity_source, on_unknown, stop_signal)`
resolves identity at trip time from `StepLedger.started_unsettled_attempts` (the same
held-and-started rule `recover()` uses; held-without-start is released, never unknown) and
persists through the validated `mark_unknown`. The runner drains via `run_with_plugins`,
refuses an observing delivery before any lease if it cannot be drained, and records
`delivery.critical_failure` as the terminal reason. New `run_delivery_factory(run_id)`
because `BoundedObserver` refuses sinks without a run id and the existing factory takes no
argument.

### E. Test-harness bug (oramasys #37, OPEN)
Three tests failed in any source checkout but passed in CI. `test_terminal_evidence` prefers
an installed-package child and falls back to a source-checkout child; the fallback dropped
`PYTHONPATH` and never supplied the source root. CI always `pip install`s, so the branch
was never taken there. Same class in `test_runtime_review_hardening`. Fix: a pure
`_child_launch` decision function plus unit tests.

### F. Lessons (orama-system #404, PT #441, OPEN)
Silent zsh traps, a corrected quoted-heredoc rule, and the review-finding verification and
harness-first debugging disciplines. Touching the two `SKILL.md` files triggered whole-file
OSSF-1 validation they had never met, so compliance metadata was added (derived from rules
the skills already state; nothing removed).

---

## 4. Local worktree map (all clean, 0 dirty)

Hub: `~/code/oramasys/worktrees/`

| Directory | Branch | Head | Use it for |
| --- | --- | --- | --- |
| `t2-oramasys-main-20261014` | `feat/t2-admitted-observation-delivery-20261014` | `afea6f48` | **PR #36** — review and test here |
| `t2-harness-fix-20261014` | `fix/terminal-evidence-source-checkout-20261014` | `9f52ad6e` | PR #37 |
| `t2-core-main-20261014` | detached | `6d75cfe0` | Core `main` (#13) — `PYTHONPATH` source for tests |
| `t2-core-pin-609ff0e` | detached | `609ff0ed` | **Production Core pin** — proves graceful degradation (no start seam) |
| `2026-10-14-skills-lessons` | `docs/skills-shell-and-review-verification-lessons-20261014` | `8eaad098` | PR #404 |
| `2026-10-14-pt-t2-lessons` | `docs/t2-delivery-and-verification-lessons-20261014` | `911f9b17` | PR #441 |
| `_outbox-codex-20261014/` | — | — | **Your deliverables go here** (§6) |

Main checkouts (operator-owned; **do not edit**): `~/code/OpenClaw/orama-system`
(1 leftover change, `exa-mcp-daemon.py`, redundant since #400 merged),
`~/code/OpenClaw/perplexity-api/Perpetua-Tools` (9 uncommitted lesson files, redundant
since #440 merged — do not `git pull` over them), `~/code/oramasys/phylax` (a tracked
`.DS_Store`).

---

## 5. Open items, ranked (what to do next)

1. **Review PR #36 independently and post APPROVE or specific findings.** Challenge these
   three choices in particular:
   - *Nothing unsettled → run-level terminal only.* When a critical failure arrives with no
     started-unsettled attempt (e.g. delivering evidence of an already-settled attempt, or
     before any attempt), #36 records the existing run-level terminal with reason
     `delivery.critical_failure` and **no** `UnknownDisposition`, because there is no hold
     to settle against. Is that the conservative terminal the receipt wants?
   - *Marking every held-and-started attempt unknown* on one critical failure (fan-out can
     hold several). Conservative, but is it too broad?
   - *Persistence failure is swallowed into `unpersisted_dispositions`* so the sink's own
     failure stays the visible exception; recovery re-derives from the ledger. Acceptable?
2. **T2 receipt items 3 and 4 are NOT done** — the fresh production-install matrix,
   compatibility cells and crash recovery against the **final merged** Core/registry pins,
   then a dated qualification receipt. #36's CI cells passing on its own head is evidence,
   not the receipt. **M1 is not claimed.** Do not claim it.
3. **ADR 71 does not mention the interim serving gap**: merged #33's serving script calls
   `open_grant_authority`, which loads seeds and the P5 secret in the web process, against
   the ADR's Ownership rule. The plan says so; the ADR does not. A one-sentence status note
   is proposed but **not applied** (it changes policy text the operator is reviewing).
4. **Hook-script drift risk** is closed by #403/#439 for `check_markdown_lint.sh`, but
   `.githooks/pre-commit` legitimately differs per repo. Do not "sync" it.
5. **Post-merge cleanup** (operator's call): reset the PT main checkout once confident, and
   prune the worktrees in §4.

---

## 6. How to deliver work when you cannot push

Work in the matching worktree, commit locally, then export. Never push, never `gh`.

```bash
# in the worktree you changed (example: PR #36)
cd "$HOME/code/oramasys/worktrees/t2-oramasys-main-20261014"
OUT="$HOME/code/oramasys/worktrees/_outbox-codex-20261014"
git format-patch origin/feat/t2-admitted-observation-delivery-20261014..HEAD -o "$OUT/pr36"
git bundle create "$OUT/pr36.bundle" origin/feat/t2-admitted-observation-delivery-20261014..HEAD
```

Then post **one** board row stating: which PR/branch, the patch directory, the base SHA the
patches apply to, the commands you ran and their results, and what you could not verify
offline. The operator or an online agent applies with `git am` and publishes.

**Rules for the outbox:**
- Patches must apply cleanly to the base SHA you name; run `git am --check` first.
- One concern per patch series. Do not mix review fixes with new work.
- Do not edit another agent's PR branch directly; propose it as a patch.

---

## 7. Reproduce the evidence offline

```bash
H="$HOME/code/oramasys/worktrees"
cd $H/t2-oramasys-main-20261014

# The core_gate directory plus the observer-authority module, on both Core revisions.
# Collect by DIRECTORY: the conftest capability bands only apply to directory collection.
for core in t2-core-main-20261014 t2-core-pin-609ff0e; do
  PYTHONPATH=$H/$core/src:$PWD/src python3 -m pytest \
    src/tests/core_gate src/tests/test_bounded_observer_authority.py -q -p no:cacheprovider
done
# Verified: 39 passed on Core main; 31 passed at the production pin 609ff0e, where the
# start-seam-dependent module is correctly NOT collected (that pin writes no start markers).
#
# TRAP: naming test_admitted_observation_unknown_disposition.py explicitly bypasses the
# gate and it FAILS at the production pin by design (nothing can be held-and-started
# there). That is not a regression.

# Full suite on #36's branch (measured): 714 passed + 2 failed + 2 skipped on Core main;
# 706 passed + 2 failed + 2 skipped at the production pin. The 2 failures are the
# cross-process terminal-evidence pair (child cannot import `orama` in a source checkout);
# they fail identically on pristine main and are the bug PR #37 fixes. In plain checkout
# #36's branch shows "2 failed, 28 passed" for test_terminal_evidence.py; #37's worktree
# runs the whole suite at 710 passed, 2 skipped, 0 failed.
cd $H/t2-harness-fix-20261014 && env -u PYTHONPATH python3 -m pytest src/tests -q -p no:cacheprovider
```

Mutation check (proves the tests bite): in `admission_runtime.py` change
`if observing and callable(bind):` to `if False and observing and callable(bind):` and the
durable-disposition test must fail; make `_drain` always call `ainvoke` and the drain tests
must fail. Restore afterwards.

---

## 8. Environment gotchas (each cost a debugging round)

- **`env -u GITHUB_TOKEN`** before `gh`/`git push`: a stale token in `~/.env` shadows the
  working keyring credential. Never print or edit the secrets file.
- **The autoresearch hook blocks `git push --force` and `git reset --hard`** by text. Use a
  merge instead of a rebase, and `git update-ref` + `git read-tree --reset -u HEAD` to back
  out. Do not word around the hook for a genuinely destructive command.
- **Another hook blocks paths containing "log"** (e.g. `~/.openclaw/log/...`). Use other
  temp names.
- **zsh traps:** never name a variable `path` (tied to `$PATH`); write `"${ref}:src/f.py"`
  not `"$ref:src/f.py"`; `git -C <repo> worktree add <relative>` resolves against the repo,
  so pass absolute paths. `for x in $var` does not word-split.
- **Quoted heredocs** (`<<'EOF'`) for board payloads; backticks in double quotes vanish.
- **Pre-push divergence guard** may say it cannot choose among several orama worktrees: set
  `GUARD_SYNC_CANON_ROOT` to the worktree holding the canonical change; do not bypass it.
- **Commit-message identifier-claim check** rejects "add/register/introduce <Symbol>" when
  the symbol is not in an added diff line. Reword; do not skip hooks.
- **Staging a canonical `SKILL.md` runs whole-file OSSF-1 validation.** It validates the
  *staged* blob, so re-`git add` after editing.
- **Capability bands:** `src/tests/core_gate/conftest.py` decides which test modules are
  collected per Core revision. A test needing the start seam belongs in the gated list.
- **GitHub cannot reopen a PR whose base branch was deleted.** Open a new PR; do not fight it.

---

## 9. Hard rules

1. **No merges.** Opening or updating a PR is not a merge. The operator decides.
2. **No force-push, no history rewrite** of anything already published.
3. **Verify, don't trust** — including this file. Re-derive any claim that matters from the
   code and a command, and say so on the board when you found a discrepancy.
4. **Do not claim M1 or the T2 qualification receipt.** They are not done.
5. **No secrets** in any file or board row; no workstation paths in tracked files.
6. **State what you could not verify offline** instead of guessing.

---

## 10. Where the reasoning lives

- Board rows 4335-4337 (T2 analysis, follow-ups, engagement summary), 4303-4334 (Task 6 history).
- PR #36 description: full design, why each patch was not applied, evidence.
- `references/post-review-micro-remediation.md` Phase 1 (in orama-system, PR #404): the
  verification and debugging discipline used throughout.
- PT memory lessons from #441: the same material as retrievable rules.

<!-- END HANDOFF: complete document -->
