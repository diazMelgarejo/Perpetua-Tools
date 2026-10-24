# Session chronicle: Part 3 consumer floor, event bodies and review remediation (2026-10-22 to 2026-10-24)

**Author:** claude-sonnet-5-5 and claude-opus-5-5 (Claude Code), written 2026-10-24 UTC.
Additive to the other chronicles in this directory; nothing existing is edited.
**Status:** record only. It merges, ratifies, promotes pins and activates nothing. No secrets, keys,
tokens, network addresses, account identifiers, emails or workstation paths are recorded here.
Repositories are named by their public `owner/repo`; commits by short or full SHA.

## 1. Scope and provenance

* One continuous multi-repo working session across `oramasys/oramasys` (consumer), `oramasys/phylax`
  (issuer), `diazMelgarejo/orama-system` (L3 docs and conformance) and `diazMelgarejo/Perpetua-Tools`
  (L2, memory). The operator merges and ratifies; the agent prepares, implements, tests and reviews.
* **Direct:** everything dated 2026-10-23 21:54 UTC onward was done and observed in this session
  (git, `gh` REST, local test runs, review threads).
* **Documentary:** work earlier in the 48-hour window (the Part 3 section 3.3 slice and its merges)
  is recorded from the session's own compaction summary and re-checked against current PR state
  (`gh api`) before use. Where the summary and the PR state differ, the PR state is recorded.
* Standing rules held throughout: reply to CodeRabbit remediation with an `@coderabbitai`-prefixed
  comment carrying the commit SHA; push once per PR per round; never commit another agent's
  unrelated work; no force-push or history rewrite without explicit authorization; never ratify,
  promote a pin or merge; GitHub GraphQL is unavailable (REST and `gh api` only); the user's
  portable-memory security invariant (categories only, exact values off-repo, synthetic test values).

## 2. Timeline

| # | When (UTC) | Work | Outcome |
| --- | --- | --- | --- |
| 1 | 10-22 to 10-23 | Part 3 section 3.3 (consumer anchor floor, bootstrap, quarantine) slice across three repos | Merged: oramasys #72 (`beb35f0`), phylax #17 (`6ee39ee`), orama-system #433/#434 (`fc74863`) |
| 2 | 10-23 | orama-system #434 review: log the post-clear accepted record; atomic ack; malformed signature; then docstrings to 100% | Pushed `f50d220`, `92d9bf7` |
| 3 | 10-23 | Perpetua-Tools #422 review 5608941259 "analyze and fix comprehensively" | Pushed `dc0154f`; candidate `067531d8e928` graduated, superseding `327192b4d88a` |
| 4 | 10-23 21:30 to 10-24 | **Part 3 Sections 1-2** (signed revocation and cascade event bodies): matrix, issuer, consumer, shared probe | Three draft PRs: orama-system #436, phylax #19, oramasys #74 |
| 5 | 10-24 00:50 | Operator marked #436 ready for review; CodeRabbit reviewed it | Three findings (section 4) |
| 6 | 10-24 01:00 to 01:25 | Review remediation across #73, #18, #436/#74/#19 and "docstrings 100%" | Section 5 |
| 7 | 10-24 | Handoff file for all agents (downloadable), then this record on PR #460 | This document |

## 3. Part 3 Sections 1-2: what was built and why

**Decision shape.** One ratification, one PR per repository: orama-system docs-only decision record,
Phylax issuer event bodies, Oramasys consumer reducer and gate. The acceptance matrix was prepared
first; the operator records the ratification (Section 5 of the matrix stays blank until the operator
fills it); implementations were written failing-tests-first against the matrix.

**Locked rules (the contract both sides satisfy).**

1. Closed bodies. Revocation is exactly `subject_kind` (`grant`, `approval`, `issuer`) plus
   `subject_id`. Cascade is exactly `approval_id`, `grant_ids`, `issuer_authority_version`.
2. Canonical identifier: printable ASCII without space, 1 to 1024 bytes. Refused, never repaired.
3. `grant_ids` strictly ascending by code point, no duplicates, empty list valid.
   `issuer_authority_version` is a safe integer from 1 to 2^53-1; booleans refused.
4. The complete seven-field event is at most 65,536 bytes of canonical JSON (sorted keys, `,` and
   `:` separators, non-ASCII literal, NaN and infinity refused, UTF-8). The cap is on the whole
   event, not the body, because the consumer already refuses a larger event and the issuer must
   never append an event the consumer cannot ingest.
5. Phylax records authority facts only and never asks consumers whether work executed. An identical
   revocation is idempotent; every cascade is its own commit; a refused body consumes no version.
6. The consumer persists facts in the same transaction as the acknowledgement; replay and fork change
   nothing. Step 4.3 Rule 4 refuses a revoked grant, a revoked issuer, a revoked approval bound to
   the attempt, or a cascade-listed grant. A cascade can only add a refusal.
7. A refusal leaves no intent, outbox entry, consumed grant use or consumed reservation.
8. No new shared wire refusal code. Consumer-local reasons (`grant_revoked`, `issuer_revoked`,
   `approval_revoked`, `cascade_listed`, and later `approval_undeclared`) stay local;
   `AUTHORIZATION_RULES` (rule1 to rule6) and Phylax's 14 refusal codes are unchanged.

**Evidence design.** Digests come from an independent standard-library oracle (not the code under
test); the signed vector file is published by Phylax and vendored byte-identical in Oramasys with a
recorded SHA-256 (prefix `ee8075c8`); a byte-identical cross-repository probe (scenarios X1 to X8, later
X5a/X5b/X5c) runs in each repository's CI against the other's pinned commit.

## 4. The `approval_ref` finding and its correction

* **Finding (CodeRabbit on #436, major).** Rule 4's approval match depended on a caller-supplied optional
  `approval_ref`. A caller that omitted it could pass a grant whose approval was revoked whenever the
  cascade list (which may legally be empty) did not name that grant.
* **The reviewer's premise was wrong.** It said the consumer "already stores `second_approval_ref`".
  It did not: only a docstring mentioned it. So the fix was a design change, not a wording edit.
  CodeRabbit later acknowledged this on the thread and resolved it.
* **Fix (oramasys #74 `c3eb3b8`, implementation `5a7690f`; phylax #19 `9b0def6`; docs `03bf20b`).**
  `create_attempt` binds the grant's verified `second_approval_ref` once, as part of the attempt's
  idempotent identity; `authorize_dispatch` takes no approval argument. `""` (single approval)
  matches no approval revocation; a canonical id is matched; an omitted binding is *undeclared* and
  is refused as `approval_undeclared` (consumer-local) whenever the issuer has revoked any
  approval, so omission can only over-refuse. Legacy attempts tables migrate with every old row
  undeclared. A cascade listing still refuses independently and is reported first. Mutants (drop
  the bound match; drop the undeclared clause) are caught.
* **Lockstep mechanics.** The probe is byte-identical in both repositories, so changing it is a
  three-step pin dance: implement in the consumer, copy the probe and bump the Phylax pin to that
  commit, then bump the consumer pin to Phylax's new commit. All CI checks green on both at the end.

## 5. Review remediation in the window

| PR | Reviewer | Findings | Fix | Head |
| --- | --- | --- | --- | --- |
| oramasys #73 (race tests) | CodeRabbit + Greptile | Timed join treated a stuck worker's initial `None` as success; bootstrap exceptions accepted; anchor overwrite undetected; no controlled commit-first case; 0% docstrings | Daemon threads, `PENDING` sentinel, fail on `is_alive()`, require bootstrap success, tie each result to the anchor it sent, controlled floor-first and authorization-first cases, 18/18 docstrings | `8b1e57c` |
| phylax #18 (GitHub approval) | Greptile + CodeRabbit | Marker age checked before a network call then spent after it could have expired; `GH_CONFIG_DIR` does not isolate the OS credential store; credential-retention wording; 57% docstrings | Re-read the clock and recheck freshness immediately before spending; `--insecure-storage`; delete everything `gh` wrote after the CLI is used while keeping the spent marker; remove the new directory if login setup fails; docs distinguish Phylax storage from `gh` retention (deleting is not revoking); 153/153 docstrings | `e430f3e` |
| orama-system #436 | CodeRabbit | Event-size serialization undefined; matrix rows 2, 4, 5, 6 used shorthand instead of test ids; `approval_ref` (section 4) | Serialization defined; exact test ids; binding fix | `9f16b23`, then `03bf20b` |

Integration check: each repository's two open PRs were merged locally into a throwaway checkout and
the full suites re-run (oramasys 1,964 passed; phylax 651 passed; probe 10/10).

## 6. Errors and corrections (left in on purpose)

* A first size cap was on the event body; the consumer measures the whole event. Moved to the whole
  event in code, tests, amendment and matrix.
* Two slice-1 consumer tests assumed opaque event bodies and broke when bodies became closed; rewritten.
* A tuple test case was silently converted by a helper and so never tested a tuple; separate tuple
  and bare-string tests added.
* A local-only cross-process test flake appears under coverage (passes in isolation, on main and in
  CI); not caused by this work.
* The Stop hook repeatedly reports unpushed commits with no same-named remote branch; a false
  positive from branch-name matching. Do not push duplicate-named branches to quiet it.
* The first handoff file went stale when heads moved after the remediation; heads are recorded in
  section 7 and the file should be regenerated on request.
* A reviewer-supplied suggestion was nearly applied as written; checking its premise against the code
  first changed the fix (lessons staged with this record).

## 7. End state and open decisions (UTC 2026-10-24)

| PR | State | Head |
| --- | --- | --- |
| orama-system #436 (docs, Sections 1-2) | open, ready for review | `03bf20b` |
| oramasys #74 (consumer) | open, draft, CI green | `c3eb3b8` |
| phylax #19 (issuer) | open, draft, CI green | `9b0def6` |
| oramasys #73 (race tests) | open | `8b1e57c` |
| phylax #18 (model-launch approval) | open | `e430f3e` |
| Perpetua-Tools #422, #460 | open | `dc0154f`, this PR |

**Operator decisions pending.** (1) Confirm or strike the four choices in matrix section 6 (identifier
grammar, empty `grant_ids` valid, 64 KiB whole-event cap, the persisted approval binding) and fill the
Section 5 record at the heads above. (2) Merge order when ready: oramasys #74 first with a merge
commit (not a squash, because Phylax CI pins the consumer's commit), then phylax #19; publish one paired
receipt; keep serving unset. Cline compares vectors and pins; Codex does the independent
security/contract review at those heads.

**Still open from earlier segments (not started).** Docstring coverage for orama-system #421, oramasys
PR 63, PR 62, PR 22 (plus PR 22's id-less JSON-RPC notification fix through a shared helper); an
optional docs PR marking E1 section 13.4.1 ratified (needs the operator's yes); discarding stale
`pr51-wt` changes (a backup patch exists). Phylax admission still reads revocation from its injected
grant-facts port rather than its own event log (matrix section 7, a separate change).
