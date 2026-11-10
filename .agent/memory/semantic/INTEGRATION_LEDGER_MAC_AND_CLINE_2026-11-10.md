# Integration ledger: Mac and local Cline contributions (2026-11-10)

Where every contribution from the Mac peer and the local Cline session landed. Author/actor: Claude
Code on the Windows host (self-reported, identity_verified=false). V = read directly (inbox file,
session log, GitHub), P = peer-reported and not rerun here. Nothing here is an approval; merges are
the operator's.

## Mac peer (Claude Code and the Codex sidecar, both self-reported)

| Contribution (inbox file) | Landed as | Status |
| --- | --- | --- |
| Review of the lock branch, 5 findings (mac-review-of-ar-win-1-backend-lock-branch) | orama PR 487: lock-leak fix, exception paths, distinct permission refusal | fixed (V) |
| Real Cline 3.0.74 dry run plus two corrections (mac-real-cline-dry-run, mac-correction-*) | not-sent versus unknown outcomes, scratch working directory, positional prompt | fixed (V) |
| Cline 3.0.74 qualification and a six-item update request | items 1 to 5 in orama PR 487; item 6 as dated notes on the two Cline reference docs | done (V) |
| ClinePass roster and ten lessons; PT branch c70100dc, 04a9656d (mac-cline-roster, mac-pushed-branches) | Perpetua-Tools PR 488, plus audited corrections after review | open PR (V) |
| orama branch 46b81aa3 (positional prompt) | reimplemented inside orama PR 487 at the Mac's request; never merge it separately | superseded (V) |
| Codex sidecar review, REQUEST CHANGES at 71ab3560, 3 findings (mac-review-gossip-lan-handoff) | commit ee9c65d6: strong not-sent evidence, descriptor close, loopback-only probe | fixed (V) |
| Orama reconciliation: main 2537cefa, merged PR list, D1 and gate boundaries | read and consistent with Windows facts; no Windows action | noted (V) |
| Mac test runs: 59 passed and 1 skipped earlier, 81 passed at e35d950c | reported by the Mac; the exact current-head suite has not been reported | open (P) |

## Local Cline session (provider cline-pass, GLM-5.3-Flash, session g8azq and its subagents)

| Contribution | Landed as | Status |
| --- | --- | --- |
| Layered benchmark L0 to L5 (tasks/cline-bench-20261110/results.md) | read in full; L0, L2, L3, L5 passed, L4 failed | recorded (V) |
| L1: "Cline not found" on a machine where it runs | shim-aware discovery (cline.cmd to node plus entry script), commit ca6895ca | fixed (V) |
| L1: "LM Studio not reachable" while it was up | measured localhost 2106 ms against 8 ms; IPv4 probe, commit 71ab3560 | fixed (V) |
| Docs drift: reference docs say CLI 3.0.34 | dated update note on both reference docs, commit bcb41f81 | done (V) |
| L4: hook dispatch failed, session.hook requires a valid hook event payload | not reproduced; it ran in an older checkout with the retired glm-5.2 slug; scratch working directory is now the default | open (U) |
| Board notes (review, full results, session log, correction) | kept as written; append-only | recorded (V) |
| Attempted Mac handoff for CLINE-PICKUP-03 over plain http | queued in the Windows outbox, never delivered, marked superseded with evidence | closed (V) |
| Recon of four old OPEN claims | Windows released its own two (all branches merged 2026-10-25); the other two belong to other agents and were left | partly done (V) |
| Suggestion: `cline doctor` is cheap and non-interactive | candidate preflight check, not adopted yet | open idea (V) |

## Still open

- Mac re-review of the newest orama PR 487 head and a macOS run of the new test files.
- L4 root cause: needs a real Cline run after the operator signs in (`cline auth`).
- Whether `cline doctor` belongs in the controller preflight.
- Operator-held: merges, certificate renewals, qualification, serving, the two claims of other agents.
