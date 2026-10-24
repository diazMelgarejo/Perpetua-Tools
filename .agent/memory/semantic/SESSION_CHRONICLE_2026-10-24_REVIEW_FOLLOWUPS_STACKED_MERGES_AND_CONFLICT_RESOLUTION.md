# Session chronicle addendum: review follow-ups, stacked merges, conflict resolution (2026-10-24)

**Author:** claude-sonnet-5-5 (Claude Code), written 2026-10-24 UTC.
Additive to
`SESSION_CHRONICLE_2026-10-22_TO_2026-10-24_PART3_CONSUMER_FLOOR_EVENT_BODIES_AND_REVIEW_REMEDIATION.md`,
which was merged with PR #460 and is not edited. **Status:** record only; it merges, ratifies and
promotes nothing. No secrets, keys, tokens, network addresses, account identifiers, emails or
workstation paths. Repositories by public `owner/repo`, commits by SHA.

## 1. What changed since the merged chronicle

The earlier record ended with Part 3 Sections 1-2 open for operator decisions. Since then:

| Item | Result |
| --- | --- |
| oramasys #73 (race tests) | Added `zip(strict=True)` (`86d1ca2`) and a Rule 2 before Rule 3 gate-order test (`6816db9`); a mutant that swaps the checks fails it. **Merged** (`33bec04`). |
| phylax #19 (issuer events) | CodeRabbit partial index `issuer_events_by_kind_body ... WHERE kind = 'revocation'` (`14d0d5c`); Greptile P1 and P2 fixed (section 2). **Merged** (`849351f`). |
| oramasys #74, #75 | #74 merged (`112cf47`); #75 (new, stacked) merged with a merge commit (`68f0630`). |
| orama-system #436 | Docs-only Sections 1-2 amendment **merged** (`3efce98`). Its Section 5 operator record on main is still the blank template. |
| phylax #18 | **Merged** (`36cc3e2`). |
| orama-system #381 | Two review rounds fixed (section 3); open, head `89b9942`. |
| Perpetua-Tools #422 | Conflicts with main resolved by a merge commit (section 4); open. |

## 2. Greptile findings on phylax #19 and the stacked fix

* **P1, `issuer_key_id` grammar.** An earlier commit validated the signing key name with the ASCII
  identifier grammar at permit issuance and event append. The frozen contract says non-blank UTF-8,
  at most 1,024 bytes, so `clé-1` or `key 1` would stop issuing and outstanding permits would fail
  to finalize. Fix: `validate_key_id` built on the existing text rule, used at both sites; tests
  refuse empty, blank and over-long ids and accept non-ASCII, spaced and 1,024-byte ids.
* **P2, probe scenario X2.** X2 hashed the case name, so every malformed event also carried a wrong
  digest and a digest-checking consumer could refuse for the wrong reason. Fix: hash the canonical
  wrapper with `hashlib` (the issuer's own digest function refuses these bodies), sign it, and
  self-check the helper against the issuer digest on a valid event.
* **Stack.** The probe is byte-identical in both repos, so: oramasys #75 first commit `8ad8a1a`
  (probe), phylax #19 head `03fe51b` (key-id fix, probe copy, pin to `8ad8a1a`), then #75 second
  commit pinning `03fe51b`. Merge order was #75 with a merge commit, then #19, so the pinned commit
  stays an ancestor of main. Both Greptile findings were confirmed and withdrawn.

## 3. orama-system #381

* Round 1 (review 5399034113 and follow-ups, `c3c581a`): adaptive thinking example for Sonnet 5.5,
  `gpt-5.3-codex-low` replaced by `gpt-5.6-terra` at medium (config row plus a generalized checker
  helper), model allowlist moved out of project settings into a managed-settings example, stale
  grok-4.6 text corrected, test annotations.
* Round 2 (review 5636595927, `89b9942`): one shared `_require_consistent_effort` for both
  `plan_launch` and `assert_launch_allowed` (conflicting `effort`/`reasoning_effort` and forbidden
  values); the Cursor gate reads either effort field and checks ungated rows with the existing
  `_assert_gated_params`, so Terra must set medium explicitly; worker cleanup skips the group
  signal only where `/proc` descendants are complete; the caching-policy line names
  `output_config.effort`; Grok 4.7 removed from two escalation lists. 2,647 tests pass; no new
  ruff findings. Each fix reused existing code instead of adding the reviewer's duplicate check.

## 4. Perpetua-Tools #422 conflict resolution

Merging main into the PR head (no rebase, no force-push) conflicted in nine files. The branch had
never changed the five dependency files, so main's newer pins and locks were taken whole; the CLAUDE.md
floors (starlette, aiohttp, hono) still hold. The three memory ledgers were resolved as a line
union with exact-duplicate removal and a per-row JSON parse; the branch's Codex identity test stayed.
The merged ledgers still contain an older lesson saying Cursor defaults to grok-4.6; append-only, so
it is left for a supersession entry rather than edited.

## 5. Errors and corrections left in

* A fresh `gh pr create` failed because GraphQL is unavailable; the PR was opened with the REST API.
* The Stop hook again reported unpushed commits because the local branch name differed from the PR
  branch; renaming the local branch and setting its upstream cleared it. The stray remote branch
  `fix/pr73-review-20261024` on oramasys/oramasys could not be deleted through the proxy and is left
  for the operator.
* A first conflict-marker check matched marker text that appears inside lesson prose; markers must be
  matched as whole lines.

## 6. Open items (unchanged by this record)

Fill the matrix Section 5 record on main and confirm the section 6 choices; docstring coverage for
orama-system #421, #381's two Python files, oramasys PRs 62, 63 and 22 (plus 22's id-less JSON-RPC
notification fix); the unaddressed inline comments on #381; delete the stray remote branch.
