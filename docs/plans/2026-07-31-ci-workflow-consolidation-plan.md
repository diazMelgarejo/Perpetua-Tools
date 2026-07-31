# CI Workflow Consolidation Plan

> **Status:** Plan, partially executed same session. Based on reading all
> 6 `.github/workflows/*.yml` files in full, not assumed from names.
> **Date:** 2026-07-31

---

## What actually exists (corrects the premise)

The request named 6 checks in two groups. Reading the repo shows the
mapping isn't 6 files:

| Named check | Actual location |
|---|---|
| Markdownlint | `.github/workflows/markdown-lint.yml` (own file) |
| CI Git hygiene | `ci.yml` → job `git-hygiene` |
| Docs/Config Sync Gate | `ci.yml` → job `docs-sync` |
| OramaSys Security Invariant | `security-invariant-enforcer.yml` (own file) |
| Invariant Monitor Bot | `invariant-monitor-bot.yml` (own file) |
| Multi-Repo Security | `multi-repo-security-mesh.yml` (own file) |

Group A is 2 files, not 3 — `git-hygiene` and `docs-sync` are already
two jobs inside the same `ci.yml`. `docs-sync` has no `needs:`, so it
already runs as its own independent parallel job today, not serialized
after the others.

---

## Group B — Security Invariant workflows

### Finding: 2 of the 3 run ~95% the same work, twice, on every push/PR

`security-invariant-enforcer.yml` and `invariant-monitor-bot.yml` are
line-for-line nearly identical: same checkout, same Python setup, same
dependency install, same `check_endpoint_policy_core.py` check, same
double-scheme transport grep. The only real differences:

- the enforcer's pytest list includes `tests/test_fastapi_health.py`;
  the monitor bot's list omits it
- the monitor bot has one extra step: posts a PR comment via
  `actions/github-script` when the job fails

This is genuine redundancy, not two checks that happen to look similar
— it is the same test suite compiled and run twice per push/PR for no
functional gain. **Merged** (this session): one workflow,
`security-invariants.yml`, running the union of both test lists (so
nothing that was checked before is now unchecked) plus the PR-comment
step (a real feature, kept, not dropped). ~50% of this compute
eliminated with zero loss of coverage.

### `multi-repo-security-mesh.yml` — not merged, flagged instead

This workflow does not actually check anything yet. Every step under
"Cross-repo invariant fetch," "Fetch Orama-system state," and "Validate
divergence rules" is a bare `echo`; nothing in the file can ever exit
non-zero. It carries its own `TODO: integrate GitHub API
compare_commits for orama-system` acknowledging this.

It also has a genuinely different trigger profile from the other two —
`schedule: cron "0 */6 * * *"` plus `workflow_dispatch` plus
**unscoped** `pull_request` (no branch filter, runs on PRs from forks
too) — versus the other two's `push`/`pull_request` to `main` only.
Folding a scheduled, unscoped-PR job into a file whose other jobs gate
merges to `main` would either force the (currently fake) mesh check to
start gating every PR, or force the real invariant tests onto a 6-hour
schedule instead of every push. Neither is a real consolidation; both
change behavior in ways nobody asked for.

**Recommendation, not executed this session:** either implement the
stated cross-repo divergence check for real (a separate, scoped piece
of work — the actual GitHub API `compare_commits` call, real
assertions, real failure conditions) or remove the file rather than
leave a workflow that always reports "Mesh check complete" regardless
of what's actually true. A check that can never fail is worse than no
check — it looks like coverage that doesn't exist.

---

## Group A — Markdownlint / Git hygiene / Docs-sync

### Hard constraint: `on:` is workflow-level, not job-level

`markdown-lint.yml` triggers `pull_request: branches: [ "**" ]` (any
target branch — deliberate, so the MD013 ratchet applies everywhere).
`ci.yml` triggers `pull_request: branches: [main]` only. GitHub Actions
does not support per-job triggers within one file — the `on:` block
governs every job in the file. Merging `markdown-lint.yml`'s job into
`ci.yml` would force one of:

- narrowing markdown lint to `main`-only PRs (loses the ratchet on
  every other branch — a real behavior regression), or
- widening `ci.yml`'s trigger to all branches (the full pytest matrix,
  git-hygiene, and docs-sync would now run on every branch PR
  regardless of target, not just ones aimed at `main` — meaningfully
  more compute for branches that were never going to merge to `main`
  directly)

Neither is a "for efficiency" win; both are silent scope changes.
**`markdown-lint.yml` stays a separate file** for this reason, not out
of an incomplete pass.

### What *did* merge: `docs-sync` folded into `git-hygiene`

`docs-sync` and `git-hygiene` share the exact same trigger already (both
live in `ci.yml`). `docs-sync`'s own separate job meant a second full
checkout + Python + pyyaml setup for two lightweight script calls that
`git-hygiene`'s own checkout could just as easily run as two more steps.
**Merged** (this session): `docs-sync`'s two checks became two
additional steps at the end of `git-hygiene`.

**Correction (caught by review, not by this doc's own first pass):**
folding the steps in without further care would have silently coupled
them to `git-hygiene`'s success — GitHub Actions skips later steps in a
job by default once an earlier one fails, so a repo-hygiene or
banned-token failure would have silently skipped the docs/config sync
checks entirely, contradicting the "same failure behavior" claim this
doc originally made. Each of the 3 folded-in steps now carries
`if: ${{ !cancelled() }}`, restoring genuine independent execution
(they run and can fail on their own regardless of earlier step outcomes
in the same job) while still respecting an actual manual cancellation.
With that fix, "same conditions, same failure behavior, one fewer
job/runner/checkout" is verified true, not assumed.

`lint-and-test` (the actual pytest matrix, `needs: [git-hygiene]`)
stays a separate job — it's genuinely the slow, resource-heavy one, and
serializing it after `git-hygiene` was already correct; folding it in
would make every push wait on a 2-Python-version test matrix before the
fast hygiene checks even report, which is a regression in feedback
latency, not an improvement.

---

## Net result

| Before | After |
|---|---|
| 6 named checks across 5 workflow files (4 in `.github/workflows/`, `docs-sync`+`git-hygiene` sharing `ci.yml`) | 4 named checks across 4 workflow files |
| `security-invariant-enforcer.yml` + `invariant-monitor-bot.yml` run near-duplicate suites | 1 `security-invariants.yml`, union of both test lists, PR-comment kept |
| `docs-sync` = separate job/runner/checkout | folded into `git-hygiene` as 2 extra steps |
| `multi-repo-security-mesh.yml` = always-passes placeholder | unchanged, flagged for real implementation or removal |
| `markdown-lint.yml` = separate file (different trigger scope) | unchanged, correctly, for the `on:` reason above |

Two files removed (`security-invariant-enforcer.yml`,
`invariant-monitor-bot.yml` → 1 file), one job removed (`docs-sync`
folded into `git-hygiene`), zero coverage lost, zero trigger-scope
changes to anything that was correctly scoped before.

**Also caught, this PR's own CI (landed as a separate, concurrent
commit, `c8f0c53`):** `scripts/security/check_endpoint_policy_core.py`
and `config/endpoint-policy-contract.yml` both hardcoded the 2 old
workflow filenames as required/must-run files — a structural self-check
verifying CI enforcement hasn't quietly been removed. Deleting those 2
files as part of this consolidation correctly tripped that check from
both places. Updated to `security-invariants.yml`; also granted
`issues: write` (the permission `github.rest.issues.createComment()`
needs) since the PR-comment step had started failing with a live 403 --
an unrelated permissions-hardening pass earlier this session had
narrowed this workflow's permissions to `contents: read` only, without
accounting for the comment step already present in the file it was
hardening.

**Also fixed (same session, this branch):** the alert's summary line
only mentioned transport and endpoint-policy invariants even though the
test list below it already included `test_fastapi_health.py` --
broadened to mention all three categories, test list and structure
otherwise unchanged.
