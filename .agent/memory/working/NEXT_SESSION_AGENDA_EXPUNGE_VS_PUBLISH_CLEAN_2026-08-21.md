# Next-session agenda: expunge-all-workspace-repos.sh vs publish-clean-branch.sh (2026-08-21)

**Source:** CodeRabbit review #4984716341 on AlphaClaw PR #29, finding #4 (Major).
Deferred rather than patched blind — see [[lesson_71502462c759]] for the full
investigation. This doc is the design-decision writeup for whoever picks it up next.

## The finding, verbatim intent

Both `.cursor/rules/never-undo-attribution-expunge.mdc` and
`zero-banned-attribution-everywhere.mdc` (canonical: orama-system, synced
byte-identical to PT and AlphaClaw) already require normal work to publish via
`scripts/git/publish-clean-branch.sh`. CodeRabbit wants that same contract
extended to `scripts/git/expunge-all-workspace-repos.sh`'s force-push step, so
there is exactly one audited publishing path, no raw force-push exception.

## Why it's not a one-line swap

`expunge-all-workspace-repos.sh` and `publish-clean-branch.sh` were built for
different shapes of problem:

| | `publish-clean-branch.sh` | `expunge-all-workspace-repos.sh` |
|---|---|---|
| Scope | one repo (cwd, via `$SCRIPT_DIR/../..`) | every repo under `$WORKSPACE_ROOT` |
| Branch | one branch, arg or current | every local branch, looped (`for-each-ref refs/heads`) |
| Precondition | ordinary commits on top of `main` | full-history `filter-branch` rewrite already ran |
| Audit | `audit_attribution.sh` (range `remote/base..branch`) + `repo_hygiene.py` + `scan-tracked-banned-tokens.sh` | its own before/after `scan_repo_hits()` banned-metadata count only |
| Push | plain `push --force-with-lease` (has a `HISTORY_SURGERY_PUSH=1` mode identical to expunge's) | `push --force-with-lease="refs/heads/<branch>:<old_sha>"` per branch, or `push -u` for new branches |

Two concrete blockers to a naive "just call publish-clean-branch.sh":

1. **Base-branch assumption breaks post-rewrite.** `audit_attribution.sh`'s range
   is `${remote}/${base}..${branch}`. After a full-history rewrite, `main..main`
   is empty and arbitrary branches may have no clean ancestry against `main` —
   the range logic isn't meaningful for "audit every branch in every repo after
   a history rewrite," only for "audit this one feature branch before merging."
2. **Call shape mismatch.** `publish-clean-branch.sh` takes one branch, runs
   from one repo's root. `expunge-all-workspace-repos.sh` would need to `cd`
   into each repo and loop-invoke it once per branch — turning an emergency,
   fast, workspace-wide remediation script into N×M sequential audited pushes,
   each also running `repo_hygiene.py` and a full token scan. That's a real
   runtime and partial-failure-mode change worth deciding on purpose, not by
   accident.

## What already overlaps (the encouraging part)

`publish-clean-branch.sh` has a `HISTORY_SURGERY_PUSH=1` code path that does
**the exact same** force-with-lease + hooks-off + `history-surgery-git.sh push`
sequence `expunge-all-workspace-repos.sh`'s `force_push_repo()` does today. The
push mechanics are already unified in spirit — just not wired together.

## Options for next session (none implemented yet)

- **A. Extract a shared library function** — factor "force-with-lease + hooks-off
  push" out of both scripts into one function in `banned_attribution_lib.sh` (or
  a new `force-push-lib.sh`), called by both. Doesn't fix the audit-range gap on
  its own, but removes the mechanical duplication CodeRabbit is really flagging.
- **B. Loop-call `publish-clean-branch.sh` per (repo, branch)** from inside
  `expunge-all-workspace-repos.sh`, accepting the slower, fully-audited runtime
  as intentional for a rare emergency-remediation script. Needs a base-branch
  fallback (skip range audit, or use `--root` diff, when `base` doesn't exist
  or the range is empty) added to `publish-clean-branch.sh` first.
- **C. Document the exception explicitly** instead of forcing uniformity — keep
  `expunge-all-workspace-repos.sh`'s own narrower audit (it already does a
  banned-metadata before/after count), and edit the two `.mdc` rule files to
  state "normal work: `publish-clean-branch.sh`; workspace-wide expunge: its
  own audited force-push, documented here as the one sanctioned exception."

**Recommendation for whoever starts this:** lean B if the runtime cost is
acceptable (this script only runs when a leak is actively being remediated,
not routinely) — it actually delivers what CodeRabbit asked for (one audited
contract) instead of codifying a second path. But it needs the base-branch
fallback in `publish-clean-branch.sh` designed first, and it's a change to a
**destructive, multi-repo force-push script** — do the design pass and get
explicit user sign-off before touching it, per this session's git-safety
discipline.

## Where to make the fix

`orama-system/scripts/git/` is canonical for both scripts (confirmed
byte-identical in PT and AlphaClaw as of 2026-08-20's guard-sync). Fix there
first, then `sync-attribution-guard-scripts.sh <target>` to every downstream
repo — never hand-edit a downstream copy.

## Cross-references

- [[lesson_71502462c759]] — the atomic lesson with the full investigation.
- AlphaClaw PR #29, CodeRabbit review #4984716341, finding #4.
- Attribution guard sync doctrine: PT `CLAUDE.md` § 6, orama `docs/v2/27-git-governance-zero-fragmentation.md`.
