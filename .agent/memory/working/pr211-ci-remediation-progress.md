# PR #211 CI Remediation Progress

Date: 2026-07-14
Branch: `kimi-lan-peer-job-board`
PR: https://github.com/diazMelgarejo/Perpetua-Tools/pull/211

## Current context

PR #206 is merged and out of scope. All work here is PR #211 only.

## Goals

1. Keep PR #211 unmerged for human review.
2. Fix CI red from `lint-and-test` step 7 by addressing first-principles root causes.
3. Provide the FastAPI full-file replacement for review.
4. Close CodeRabbit RC5 attribution-guard finding without weakening attribution policy.
5. Preserve LAN gossip functionality and single-operator-LAN security model.

## Findings so far

- PR #211 head before this pass: `5f413369b22b725574a66f8be83bf0300edd9e97`.
- Security mesh, invariant monitor, and security invariant enforcer were green on that head.
- CI was red only in `lint-and-test` step 7.
- CodeRabbit FastAPI/gossip endpoint findings are resolved.
- One CodeRabbit thread remained unresolved: the literal `${HOME}` assertion in `tests/test_git_attribution_guard_integrations.py`.

## Completed in this pass

- Replaced the no-op literal `${HOME}` assertion with an assertion against an expanded fake `$HOME` path.
- Confirmed RC5 coverage already includes authorized authors/co-authors:
  - `diazMelgarejo`
  - `diaz.Melgarejo`
  - `Lawrence.Melgarejo`
- Confirmed those authorized identities are asserted absent from generated banned attribution tokens.

## Pending verification

- Wait for CI to run on the new PR #211 head.
- Verify no new CodeRabbit actionable threads remain.
- Human review of `orchestrator/fastapi_app.py` full replacement before merge.

## Do not do

- Do not merge PR #211.
- Do not return to PR #206.
- Do not broaden banned attribution allowlists beyond the explicitly approved identities.
- Do not weaken `ensure_hooks_installed.sh`; tests should preserve mandatory hook enforcement.
