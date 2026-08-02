# CI Tool-Version Mismatch + Gitleaks History False-Positive — Session Report

> Compact report of a real debugging arc across PT (`cursor/coderabbit-review-wave-sync-f559`)
> and orama-system (`2026-08-02-pr-body-grant-hmac-mvp`), 2026-08-02. See
> `lesson_77ce859d6970`, `lesson_084412e4e566`, `lesson_5f0362a3f95f` for the
> extracted, generalized lessons; this doc is the narrative evidence trail.

## What happened, in order

1. Wrote a `.markdownlint-cli2.jsonc` config using an `overrides`/`filter`/
   `combine` block to exempt `DECISIONS.md` (and similar append-only logs)
   from MD013 line-length. Tested locally with a fresh `npm install`d
   `markdownlint-cli2` — clean, 0 issues.
2. Pushed. Real CI (`davidanson/markdownlint-cli2-action@v19`) still failed,
   showing the *full*, unexempted violation count on `DECISIONS.md` — as if
   the config change had done nothing at all.
3. Root cause: CI's pinned action version bundles `markdownlint-cli2 v0.17.2`
   (`markdownlint v0.37.4`) — traceable directly from the error message's own
   doc links, which pointed at `v0.37.4`-specific pages. The locally-installed
   `markdownlint-cli2` was `v0.23.2` (`markdownlint v0.41.1`), a much newer
   release. The `overrides`/`filter`/`combine` schema apparently isn't
   supported in the older, actually-pinned version — it was silently ignored,
   not erroring, so the local "clean" result was never representative of what
   CI would actually do.
4. Fix: installed `markdownlint-cli2@0.17.2` explicitly (matching CI exactly),
   reproduced the failure locally, then verified a simpler `ignores`-based
   config resolves it under *that* version. Applied to both repos.
5. Pushed the corrected config. PT went green. Orama surfaced two *more*
   real, distinct problems on the next run:
   - A second `WORKSPACE.md` (orama's own TTY-gate research tracker, not
     PT's grant-HMAC one — same filename, different file, different repo)
     had pre-existing formatting violations pulled into scope by an earlier
     commit on the same branch that had touched it.
   - `gitleaks (secrets)` started failing — a **new** failure category not
     related to the markdownlint work at all.
6. Gitleaks root cause: an *already-superseded* earlier commit on the branch
   had hardcoded a test's expected HMAC digest as a literal hex string
   (`assert token == "0852c9f3..."`). A later commit on the same branch
   already fixed this (computing the expected digest independently via
   `hashlib`/`hmac` instead of hardcoding it) — but gitleaks scans the whole
   `base^..head` commit range, including commits whose problematic content
   was later fixed, so the old commit kept tripping the scan on every run
   regardless of current file state.
7. Fix: `.gitleaks.toml` with `[extend] useDefault = true` (keep the full
   default ruleset) plus a global allowlist for the 2 specific commit SHAs
   that introduced the flagged pattern.
8. **Near-miss caught before shipping**: the first draft of that allowlist
   used commit SHAs extrapolated from `git log --oneline`'s short-SHA output
   by guessing/padding the remaining hex characters, rather than resolving
   them for real. Caught by comparing against `git rev-parse <short-sha>`'s
   actual output — completely different past the original short prefix.
   A fabricated SHA in an allowlist entry would have silently matched
   nothing, providing zero real exemption while looking syntactically
   correct.
9. Verified the final fix genuinely works, not assumed from config syntax
   alone: downloaded gitleaks `8.24.3` (the exact CI version) and ran it
   directly against the identical commit range CI scans. Confirmed
   `no leaks found` with the allowlist in place.

## Net result

Both repos' CI green, confirmed via the GitHub API's real check-run status,
not inferred from local testing. Two config fixes now exist in both repos'
histories (`ignores`-based markdownlint exemption; scoped gitleaks
allowlist) that are verified against the actual pinned tool versions CI
runs, not the newest locally-available versions.

## Reusable checklist for the next CI-tool-config fix

1. Identify the exact tool version CI actually pins — check the error
   message's own doc links, or the action's release notes, before assuming
   a locally-installed version is representative.
2. Install and test against that exact version, not `latest`.
3. If a scanner (secrets, license, dependency) flags something already
   fixed in a later commit, check whether it's scanning full history —
   if so, the fix is a scoped allowlist for the specific commit(s), not
   another edit to current files.
4. Never extend a short SHA by guessing — always `git rev-parse` it.
5. Verify the final config against the real tool binary and the real scan
   scope (commit range, glob pattern) CI actually uses, not just its syntax.
