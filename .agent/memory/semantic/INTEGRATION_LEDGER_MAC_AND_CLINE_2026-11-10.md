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

## Mac Final-Head Reconciliation (Later on 2026-11-10)

Author/actor: Codex primary orchestrator, self-reported, identity_verified=false.
This additive disposition supersedes the earlier Mac-test open item and the
scope of the `ee9c65d6` fixed row; it does not erase those historical reports.

- Orama PR487 `69cb2ea79e4a7db50132ad59a59912048621c149`: ten focused files,
  199 passed, 13 Windows-only skips, one disabled-plugin warning. Python
  3.13.18 / SQLite 3.53.1, macOS 27.2 arm64; clean tree, contained child.
- All Windows fixes and reference notes through `9ba89cb9` are preserved.
  `dc8ae1e3` removes output heuristics from not-sent classification and extends
  acquisition cleanup; `03effcc8` preserves changed ownership evidence and
  adds literal IPv6 fallback. Passing baseline tests alone missed these paths.
- The current `lesson_3413c1a3ed12` was corrected with the audited writer:
  short stderr and a fast exit do not prove not-sent. Prior snapshots remain.
- PT #489 incorporates both Windows' catalogue/corrections and the Mac's four
  provisional lessons plus the dated POSIX record. Divergent JSONL streams
  were parsed structurally, preserving the reviewed upstream stack as an exact
  byte prefix and every full local/peer record; corrections intentionally repeat IDs.
  `LESSONS.md` was regenerated with the canonical renderer, never hand-merged.
- Mac software execution is complete for this scope; final-head Windows
  qualification, L4 real-run investigation after operator authentication,
  preflight-doctor design, other agents' claims and operator decisions remain
  distinct. No paid Cline run or automatic claim release was performed.

Later Windows messages `win-hold-ack-shas-and-cline-fix` and
`win-correction-after-fetch` were integrity-checked against their inbox metadata.
Windows independently fetched `69cb2ea7` and confirmed all its commits remain;
its final-head native run is still unreported. Windows reports a successful
isolated plan-mode ClinePass probe, so authentication for that provider is no
longer its reported blocker. Repository-hook/config causality for L4 remains
unproven; do not silently relabel the successful isolated probe as an L4 fix.
The local-only Cline `be3da96` discovery fallback is a separate proposal: the
Mac has not received its exact diff/test and did not merge an unseen branch.
Request its scoped patch for a reviewed follow-up; `CLINE_BIN` remains supported.
