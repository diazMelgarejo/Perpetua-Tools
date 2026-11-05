# Weekly durable fixes and open gates — 2026-11-02 to 2026-11-05 UTC

## Scope, provenance and authority

This is a bounded reconciliation of work recoverable from this conversation,
linked PRs and implementation receipts, not a claim to have audited every change
made by every contributor this week. Dates are UTC; the approved November 4
Asia/Manila slice was executed November 3 UTC.

Author/actor of this synthesis: Codex, self-reported session identity. Existing
Windows contributors and prior author lanes retain their Git authorship. Fresh
same-session reviewers supplied bounded code review, not independently authenticated
R6 endorsement. The user authorized this new PT memory PR; that does not authorize
merging, credential operations, production promotion or activation.

Baseline PT main: `a1e59e50e7dd794584fb5b0cd459924345c0e833`.
This memory change imports no v2 runtime and changes no production pin or policy.

## 1. November 2–4: authority composition, concurrency and loaded identity

The recovered patch bundle was reconciled against current main rather than
replayed wholesale. Stronger merged public revocation/retention interfaces and
Windows contributions were preserved; overlapping WIP proposals were not revived.

- [Oramasys #91](https://github.com/oramasys/oramasys/pull/91) merged as
  `98b7568fa4bedbf59be788b62d2c7333f10535f4`; the per-installation deployment
  profile and review fixes remain software evidence, not actual deployment proof.
- [Phylax #30](https://github.com/oramasys/phylax/pull/30) merged as
  `a7211df7d58695f35f5afee9b6b50af6a3f96139`; platform primitives were added,
  not universal native-Windows qualification or migration of all existing callers.
- [Oramasys #92](https://github.com/oramasys/oramasys/pull/92) merged as
  `f89f82c6c8e256378fac0f9b072738f0f28480f1`: refresh time is resampled under
  the second cache write lock; retryable approval outages can recover and send
  once; the bounded loaded-identity API freezes an allowlisted public projection.
- [Phylax #31](https://github.com/oramasys/phylax/pull/31) merged as
  `1d2f2bb2ed7792c48f6320da36de9bc7459f0da3`: registry freshness, key validity,
  revocation and assertion expiry are rechecked under the nonce write lock.
- Earlier operator-clock repair samples an aware commit-time clock under the
  write lock, instead of comparing an earlier request sample to a newer writer's
  persisted observation. Actual backwards time still refuses; false rollback
  caused by valid request interleaving does not.
- Approval paths preserve `RevocationUnavailable` as retryable/nonterminal.
  Fail-closed diagnostics log exception class only, not exception messages,
  traceback, grant or approval identifiers.

Exact prior candidate verification and limits:
[next-slice receipt](https://github.com/oramasys/oramasys/blob/f89f82c6c8e256378fac0f9b072738f0f28480f1/docs/release12-postmerge-qualification-2026-11-04.md),
[completion matrix](https://github.com/oramasys/oramasys/blob/f89f82c6c8e256378fac0f9b072738f0f28480f1/docs/release12-r3-completion-matrix-2026-11-02.md),
[loaded-identity ADR](https://github.com/oramasys/oramasys/blob/f89f82c6c8e256378fac0f9b072738f0f28480f1/docs/adr/loaded-deployment-identity.md).
The receipt's old draft publication status is superseded by the merges above;
its test counts remain evidence for its named candidates only.

## 2. November 3–4: legacy Windows, routing and memory closure

- [PT #475](https://github.com/diazMelgarejo/Perpetua-Tools/pull/475) merged as
  `fa6b914e9dcaf2f86b0b895da80a284dfe25d0ca`: Windows job-object/process-tree,
  absolute-path launch, fail-closed ACL and encoding work. TLS bootstrap error
  aggregation retains a new TLS failure even when an earlier error exists.
  Source changes do not stand in for physical Windows effective-access evidence.
- [PT #476](https://github.com/diazMelgarejo/Perpetua-Tools/pull/476) merged as
  `bd188626963b9b614dae763ae7f93cc7999befcc`: Mac MLX default corrections and
  reviewed documentation coverage. Do not generalize changed-file docstring
  coverage into repository-wide 100 percent.
- [PT #477](https://github.com/diazMelgarejo/Perpetua-Tools/pull/477) then
  [#479](https://github.com/diazMelgarejo/Perpetua-Tools/pull/479) merged as
  `c32df70c9283ba71b613b77565ab6e7829f93d4c` and
  `a1e59e50e7dd794584fb5b0cd459924345c0e833` respectively.
  Supersession explicitly covered both the original overbroad cleanup rule and
  its intermediate successor (`4d298e7a` then `2fe91153`); original JSONL bytes
  were preserved. Actual credential exposure and attribution-only exposure have
  different responses, and history rewriting still needs specific approval.
- Legacy Orama [#472](https://github.com/diazMelgarejo/orama-system/pull/472) →
  [#473](https://github.com/diazMelgarejo/orama-system/pull/473) →
  [#474](https://github.com/diazMelgarejo/orama-system/pull/474) merged as
  `8392fff5ffa58f58a2d87e0089d932bab89df57d`,
  `745e6715555654ee906da6b6b2436d5348f7a472`, and
  `c5fcfdf3716ae4d2437b98f251aed73ba22b4299`.
  Existing contents were propagated through normal merges without force-pushing.
- The Hermes card now uses the installer-generated `~/.openclaw/.env.glm52`.
  Bash sources it; PowerShell reads literal assignments rather than executing
  Bash substitutions. Neither operator-local candidate file existed in the
  cloud environment: repository contracts were compared, not private contents.
- Real-jq health tests reject null, non-string, empty and whitespace-only
  completions. Persistence tests explicitly enable opt-in and exercise the
  second-run guard. The probe requests a short reply with 512 tokens rather
  than 10; this mitigates reasoning-budget exhaustion, not a guarantee of
  completion. No unsupported disable-thinking flag or live model call was added.
- MCP and shell Cline entrypoints apply the Cline-pass model default only to
  that provider; other providers preserve explicit models or omit `-m`.
- Final legacy mains matched three shared runtime modules, 51 guard payloads
  and two ADR pointers. The pointer checker was rerun against a proper clone
  because a worktree skip is not evidence. Root guards retain their canonical
  owner; shared endpoint files retain their separately documented PT owner.

[Final legacy receipt](https://github.com/diazMelgarejo/orama-system/pull/474#issuecomment-6642406944).
By November 5, PT and legacy Orama final-main check runs had all succeeded
(11 and 25 check runs respectively; these are not counts of unique tests).

## 3. November 5: architecture synthesis and the CI regression we introduced

Existing refinements were preserved on the original branches. The accessible v1
landing reference is squash merge `832b4945` (#409); an absent pre-squash SHA is
not evidence that the underlying content never landed.

- Legacy [Orama #475](https://github.com/diazMelgarejo/orama-system/pull/475)
  and clean [Oramasys #93](https://github.com/oramasys/oramasys/pull/93) were
  opened as draft PRs, not merged. Repository-qualified PR identity matters:
  **PT #475 and Orama #475 are different PRs**, and neither number identifies a stack.
- The maps distinguish planned controller/satellite boundaries from implemented
  interfaces; all ten v2 System Shape edges name owner and contract. Five shared
  graph meanings match, but v1 questions and v2 record shapes remain distinct.
- The standard-library checker has one canonical implementation in legacy Orama.
  Both workflows check explicit peer commits. This validates a revision pair,
  not automatic synchronization with every later peer-main update.
- **Our introduced regression:** the new documentation checkout was classified
  as a second production registry by a repository-only test scanner. It mixed
  documentation SHA `8fbbed13` with the accepted registry SHA `a5bdcd2b`, causing
  manifest failures and all six oracle cells to fail. The early full local suite
  started before the final workflow existed, so it did not cover the final tree.
- Fix `10cfaa210427d1e31ff74772ea10eec00d8647bb` classifies dependency edges by
  explicit checkout role. Both existing registry paths remain enforced; the
  documentation-only role is separate. Unknown roles, ambiguous fields and
  nonimmutable revisions refuse. Production pins, generations and registry bytes
  were not changed to accommodate documentation.
- At that exact head, both clean CI-style local interpreter suites passed
  2,874 tests with one optional skip and 93.06 percent coverage; 147 focused
  pin/manifest tests passed. All 22 executable hosted checks then succeeded;
  CodeRabbit was skipped and was not counted as a passing review.
  [Hosted verification receipt](https://github.com/oramasys/oramasys/pull/93#issuecomment-6671131304).
- CodeRabbit review `5792983379` then exposed bounded-parser defects. Fix
  `b6c27b699d81b29b6138122f8ff48a8e1473a39a` preserves escaped pipes and blanks
  fenced examples without joining table fragments. Tests cover fence style,
  matching length, unclosed fences, shared/audience cells and malformed tables.
  Removing either separator or row-width guard makes its new regression fail.
  All 17 CLI tests pass; changed Python documentation is 26/26 items.
- Both inline findings have `@CodeRabbitAi fixed in commit` replies, and the
  review-level nitpick has a separate response. Companion commit
  `e1f653c04dfcfa6ce2638e78e13891834d818781` advances only #93's documentation
  checker pin. Both new exact-head hosted parity jobs succeeded:
  [legacy](https://github.com/diazMelgarejo/orama-system/actions/runs/42121971912),
  [clean](https://github.com/oramasys/oramasys/actions/runs/42121972004).
  Other latest-head CI was still running at this record's initial readback;
  do not transfer the older head's green checks to these new commits.

The candidate full legacy run had 3,270 passed, 79 skipped and four known
container baseline failures in `tests/test_win_exec.py`: grandchild cleanup,
reparented orphan, orphan after root exit, and descendant-held pipe. These also
failed on unchanged main; a diagnostic observed a zombie descendant and a
conservative process-group liveness probe. No containment guarantee was weakened.
The final companion local suite passed 2,874 with one optional skip.

## 4. Explicit remaining gates — not erased by merged software

- Revocation lookup availability: large-feed replay under the SQLite write lock
  remains expensive. Any snapshot cache must invalidate on both cached bytes and
  current issuer-key trust. Benchmark complete sends with concurrent refresh on
  the actual filesystem before claiming an SLO. [Capacity record](https://github.com/oramasys/oramasys/blob/f89f82c6c8e256378fac0f9b072738f0f28480f1/docs/revocation-capacity-handoff-2026-11-03.md).
- A frozen public topology projection does not bind mutable effective config to
  what a service later consumes. Actual loader/policy/artifact/process binding,
  private evidence protection and installed R4/R5 proof still require the real
  deployment. Do not publish bare hashes of secret or low-entropy values.
- Actual Mac Studio, RTX 3080 and RTX 5080 canaries, Windows ACL denial under a
  separate identity, native runtime containment, both TLS directions and independent
  receiver receipts require current host evidence. Reconcile newer receipts first.
- The original uncommitted September 25 physical-canary runbook remains unrecovered.
  Its comparison/reconstruction is not the original; no guessed collector command
  or timestamp flag is evidence.
- R6 independent review, R7 operator generation/pin promotion and R8 separate
  scoped activation are different gates. Same-session agent review, prior approval
  of another generation and successful CI cannot substitute. Keep serving off.
- Checkpoint/replay/pruning, continuation, Telos provider transport, framework
  differential compatibility and multi-host partition qualification remain scoped
  follow-ons, not automatically delivered by the architecture maps.
- The swarm handoff was produced as a portable artifact with lanes, dependencies
  and human-only gates. Its read-only discovery found additional Telos,
  Alexandria and Anamnesis repositories needing audit, not permission to modify
  every organization repository. The earlier v2 hold was lifted only for the
  subsequently approved architecture work, not for unrelated deployment work.

For operators, route first to the current qualification receipt and canonical
hardware/Windows plans linked there. Historical unchecked boxes are not proof
that the same work remains open, and empty PR queues are not roadmap completion.

## 5. Durable recall and preservation

| Accepted lesson | Recall trigger |
| --- | --- |
| `lesson_7186d20f6f8f` | `final-tree` — includes the last workflow edit. |
| `lesson_8566e53d2fff` | `checkout-role` — registry versus documentation pins. |
| `lesson_5c2cd936c760` | `markdown-parity escaped-pipes code-fences mutation-tests`. |
| `lesson_ae7945721cbb` | `clock-rollback commit-time nonce-lock`. |
| `lesson_c13468273ad8` | `revocation-unavailable approval-retry`. |
| `lesson_bc88f186f426` | `loaded-identity config-binding`. |
| `lesson_110c597f11c3` | `environment-file installer-contract launcher-parity`. |

New semantic lessons are graduated through `learn.py` with rationale and matching
episodic evidence, then `LESSONS.md` is regenerated by the native renderer.
Existing source JSONL bytes, IDs, duplicates and ordering must remain unchanged.
This weekly record and its index links are additive; it supersedes historical
status descriptions by reference, not by erasing their evidence.

Recall with the exact condition tags above, for example
`python .agent/tools/recall.py 'checkout-role' --quiet --top 5`.
All seven accepted IDs were retrieved in the top five using their listed tags;
natural-language paraphrases can rank older contextual lessons first. Test
evidence is not operator authority.

### Follow-up readback while preparing this memory PR

Oramasys #93 at `e1f653c04dfcfa6ce2638e78e13891834d818781` subsequently completed
all 22 executable checks successfully, with one skipped CodeRabbit check. Legacy
Orama #475 at `b6c27b699d81b29b6138122f8ff48a8e1473a39a` had 26 successful and
two neutral checks; its skill scanner was still pending. Those current-head
observations supplement, rather than rewrite, the earlier readback above.
