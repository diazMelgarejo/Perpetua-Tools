# Staged private-range gate — PT #399 and orama #366 (2026-09-26)

Record of the lockstep hygiene work and the lessons graduated from it.
Semantic claims live in `.agent/memory/semantic/lessons.jsonl` (via
`learn.py`). This file is the session narrative those claims point at.

## What shipped

Both repos block prohibited address literals on added diff lines: RFC1918,
loopback, unique-local (ULA), and carrier-grade NAT (CGNAT). Findings name
the path, the line, and the address class. They never echo the literal.
Scanner source and its tests are the only exemptions. The documentation
TEST-NET range is public and must not be flagged.

Perpetua-Tools implements the scanner in `scripts/review/repo_hygiene_core.py`.
`scripts/review/repo_hygiene.py` is the identity entrypoint: it re-exports
core, replaces `check_identity`, and calls core `main()`. orama-system has
no core module. The same scanner lives in the monolith
`scripts/review/repo_hygiene.py`. Function bodies, including docstrings,
must match. Tests differ only in the exempt path and in which module they
patch.

| Repo | Branch | PR |
| --- | --- | --- |
| Perpetua-Tools | `fix/hygiene-staged-private-range-gate-20260926` | https://github.com/diazMelgarejo/Perpetua-Tools/pull/399 |
| orama-system | `cursor/sync-staged-private-range-gate-bb37` | https://github.com/diazMelgarejo/orama-system/pull/366 (draft) |

### Perpetua-Tools commits

| SHA | Role |
| --- | --- |
| `ff26c2845afabb8d5f7b3bc4c5a273005262d9cc` | Original staged gate. Pre-commit still runs `repo_hygiene.py` with no flags (`git diff --cached`). |
| `0037cbe4bd5e8ba971464790fedec5e42341cbbc` | CodeRabbit review 5324084599 on `ff26c284`. Complete tokens, hunk-aware `+++`, UTF-8 `run_git`, diff-filter `ACMRT`. |
| `a8292083d3e0fd18985efbd551da56bde5cd9c18` | CI commit-range mode. Default remains `--cached`. |

### orama-system commits

| SHA | Role |
| --- | --- |
| `2889124e0667f073c178d0de50ca37a93e23ee02` | Initial lockstep sync of the gate onto `origin/main`. |
| `66d9348ee98c7196d92554d87cb72d4fdf128db2` | Docstring of `_parsed_address_token` realigned with Perpetua-Tools so the scanner text matches. |
| `121aeea1ecd970d6ff15f26fb1added8a6d2c954` | Same CI commit-range mode as Perpetua-Tools `a8292083`. |

## Review 5324084599 (Perpetua-Tools #399, commit ff26c284)

All four inline threads were fixed in `0037cbe4bd5e8ba971464790fedec5e42341cbbc`,
replied with that full SHA, and resolved.

| Comment | Thread | Defect |
| --- | --- | --- |
| 4109787018 | `PRRT_kwDOPz7qg86mMw2P` | Token grammar. A partial IPv6 pattern plus a trailing word-or-colon boundary dropped port-suffixed IPv4 and compressed ULA. Fix: bracketed IPv6 with optional port, IPv4-mapped form, IPv4 with optional port, then a compressed IPv6 run. Lookbehind stops at a word or colon; the trailing boundary is a word only. Parse the whole token with `ipaddress` first. Strip a trailing colon-port only when `ipaddress` rejects the whole token. Drop brackets before parsing. |
| 4109787024 | `PRRT_kwDOPz7qg86mMw2U` | `+++` is a file header only outside a hunk. Inside a hunk, an added line whose text starts with `++` is also `+++` in the patch and must be scanned as content. |
| 4109787026 | `PRRT_kwDOPz7qg86mMw2W` | `run_git` text mode without `encoding="utf-8"` can abort on a non-UTF-8 locale before any finding. Perpetua-Tools resolves `git` via `shutil.which` (including `git.cmd`). orama-system calls `git` directly. Both pass `encoding="utf-8"`. |
| 4109787029 | `PRRT_kwDOPz7qg86mMw2Y` | `--diff-filter=ACMR` misses type change `T` (regular file replacing a symlink). Use `ACMRT`. |

## Review 5324280369 (orama-system #366)

Comment 4109939031, thread `PRRT_kwDORtdZEM6mNIYM` (outdated, original line
null). CI only ran `git diff --cached`. A CI checkout has an empty index, so
added private-range literals already in the pull-request commits were invisible.

Fix in Perpetua-Tools `a8292083d3e0fd18985efbd551da56bde5cd9c18` and
orama-system `121aeea1ecd970d6ff15f26fb1added8a6d2c954`:

- `_address_scan_diff_spec` returns either `["--cached"]` plus location text
  `staged file`, or a three-dot `base...head` plus location text `commit range`.
- One-sided base or head is an error: both must be set.
- Refs must be non-empty and must not start with `-`.
- CLI flags `--address-diff-base` and `--address-diff-head` are both required
  together. Pre-commit passes neither, so it stays on the index.
- Workflow step: `pull_request` fetches `origin/$BASE_REF` and passes
  `--address-diff-head` as `github.event.pull_request.head.sha` (the branch
  tip, not the synthetic merge commit). `push` uses `github.event.before` and
  `github.sha` unless `before` is all zeros. Both workflows already use
  `fetch-depth: 0`.

Replies on that thread:

- https://github.com/diazMelgarejo/orama-system/pull/366#discussion_r4109967283
- https://github.com/diazMelgarejo/orama-system/pull/366#discussion_r4110008004
  (full SHAs for both repos)

The thread `isResolved` is true, resolved by cursor[bot]. The parent review
object stays `COMMENTED`. Resolving a thread does not change review state.
An outdated comment (`line: null`) still needs the inline reply.

## Verification

Isolated pytest (`--noconftest`, because the repo conftest imports the
orchestrator). Do not collect both repos' same-named test modules in one
process.

- After the token / hunk / encoding / type-change fixes: Perpetua-Tools 52
  passed, orama-system 70 passed.
- After the commit-range mode: Perpetua-Tools 53 passed, orama-system 71
  passed.
- Default mode still asserts the git args begin with `diff --cached`.
- A clean index after commit reports nothing from the cached scan and reports
  the literal on the three-dot range as `commit range`.
- A one-sided base errors with `diff base and head must both be set`.

## What was deliberately left out of the commits

orama-system had unrelated dirty paths already in the worktree. They were
not part of the gate and were not committed:

- `scripts/cursor/append-pr-body.sh`
- `scripts/cursor/pr-body-grant-lib.py`
- `scripts/cursor/hooks/pr-body-guard-core.py` (mode only)
- `scripts/git/resolve_sibling_git_repo.sh` (mode only)
- `scripts/git/identity-policy.json` (would drop an allowed automation
  identity from that repo's bot identities — a policy regression)

`publish-clean-branch.sh` stops in strict PR-body guard mode when the branch
already has an open pull request. The body was not edited. Pushes used
`git push origin <branch>` after the attribution audit. The session record
belongs in this memory file and in a pull-request comment, not in a body
rewrite.

## Lessons (operational)

1. Extract a complete address token and validate it with `ipaddress`. A
   partial grammar plus a trailing colon boundary misses port-suffixed IPv4
   and compressed ULA.
2. Treat `+++` as a file header only outside hunks.
3. Pass `encoding="utf-8"` on text-mode git subprocesses.
4. Include diff-filter `T` so a symlink-to-file replacement is scanned.
5. Keep `git diff --cached` for pre-commit. Pass an explicit three-dot range
   from CI, using the pull-request head SHA.
6. Lockstep means identical scanner text, including docstrings. orama-system
   exempts `scripts/review/repo_hygiene.py`; Perpetua-Tools exempts
   `scripts/review/repo_hygiene_core.py`.
7. Reply on the inline thread with the full 40-character fixing SHA, then
   resolve the thread. Review state staying `COMMENTED` is expected.
8. Do not sweep unrelated identity-policy or PR-body script edits into a
   hygiene sync.
