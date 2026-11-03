# Remediation flow and agy parallel lanes (2026-11-02)

Operator-approved working method for review and CI remediation across the stack. Scrubbed:
no workstation paths, addresses or secrets.

## Remediation flow (one push per PR)

1. **Collect once.** Read every review, inline comment, issue comment and failing CI log for all
   open PRs in one pass. Strip bot markup. Do not re-read per item.
2. **Classify into groups** by file and root cause. Several bots often report one finding; a CI
   failure and a review comment can share a cause. Duplicates are fixed once.
3. **Compile the file changes first**, then fix each PR once, elegantly: one root-cause fix per
   group, not one patch per comment.
4. **Prove it.** New tests must fail on the pre-fix source (run them against the earlier commit).
   Docstrings 100% on every touched file. Docstring-only commits are checked by comparing syntax
   trees with docstrings stripped.
5. **Push once per PR**, then reply to each inline comment with
   `@<BotName> we fixed this in commit <SHA>` and resolve the threads.
6. **Hand off after the push, not before.** One short report per PR; no narration while working.
7. **Frugal tooling.** Batch reads, write results to files, show only counts and failing lines.

## Parallel lanes with agy (Windows, direct binary)

- Use the installed agy binary directly (not through a wrapper): `agy models` lists models;
  `--print=<prompt>` must be attached to the flag (`-p` followed by another flag swallows it).
- Headless `agy` denies shell commands unless permissions are granted. The operator may direct
  `--dangerously-skip-permissions`. Pair it with `--sandbox`, one disposable git worktree per lane
  (`--add-dir` only that worktree and a read-only task folder), no push rights, no `.env*` access.
- Each lane gets a self-contained task file (agy does not see the conversation): exact files,
  commands, test interpreters, "commit locally, never push", and the report format.
- The orchestrator verifies every report against the code (tests, byte checks, syntax-tree
  equality for docstring commits) before pushing; a report is a claim, not evidence.
- Lanes never share a worktree or the shared stash stack; never `git stash pop`.

## CI lesson: cross-repo branch pairing

PT CI pairs a PR branch with an orama-system branch of the same name. When the companion branch
has a different name, declare it in `config/cross-repo-policy-stacks.json` (`peer_ref`,
`peer_pull`, `equivalents`) instead of renaming branches or skipping the parity check.
