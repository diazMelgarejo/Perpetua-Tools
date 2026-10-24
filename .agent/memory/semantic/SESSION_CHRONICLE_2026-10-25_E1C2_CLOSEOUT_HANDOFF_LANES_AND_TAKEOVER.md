# Session chronicle: E1/C2 close-out, handoff lanes and Codex takeover (2026-10-24 to 2026-10-25)

**Author:** claude-sonnet-5-5 (Claude Code). Additive to
`SESSION_CHRONICLE_2026-10-24_REVIEW_FOLLOWUPS_STACKED_MERGES_AND_CONFLICT_RESOLUTION.md`, which
is not edited.
**Status:** record only; it merges, ratifies and activates nothing. No secrets, keys, tokens,
network addresses,
account identifiers, emails or workstation paths. Repositories by public `owner/repo`, commits by
SHA.

## 1. How it went

| Step | What happened |
| --- | --- |
| Close-out loop | A goal hook repeatedly judged the close-out unmet because the remaining items were operator-only: merges, the Section 5 signature, a key-ID answer, serving prerequisites. The assistant restated the blockers each time and merged nothing after the operator's stop-merging instruction. |
| Operator rulings | direct-xAI `fast` off (implemented, orama `be571568`), later refined to "only with a fresh one-use exact-use approval; AskUserQuestion is enough, else fresh gh re-auth". `issuer_key_id` keeps the frozen contract rule (non-blank UTF-8, at most 1,024 bytes). Serving prerequisites 1-3 accepted against Codex's evidence map. `ORAMA_GRANT_SERVING` scheduled by the operator for 2026-11-07 UTC unless revoked; never set by an agent. |
| Merges (operator) | orama #381 `bcfd5c98`, #437 `6281e969`; PT #461 `cd82cc76`; Alexandria #1. Section 5 now on orama main. |
| M1 pins | A plan step to promote them was wrong: Oramasys main already records `pins-merged` (orama #414, Oramasys #53 and #55, 2026-10-18). Codex's cross-check caught it; the plan was corrected. |
| Handoff | A cross-repo review defined findings F1-F4 and a trusted-composition slice. Claude wrote the TC1-TC7 acceptance matrix draft and verified F1 and F2 against PT main `cd82cc76` (both inputs were accepted). |
| Takeover | The operator told Claude to finish Codex's started lanes. Claude announced it on the board, checked file modification times, and built its own worktrees from Codex's branch tips (cherry-pick or copy), crediting Codex with a co-author line. |
| Pushed PRs | oramasys/phylax#20 (signer adapter, 666 passed), oramasys/oramasys#76 (F3 qualification plus F4 status, 2002 passed, 2 skipped), orama-system#438 (F4 reconciliation), Perpetua-Tools#463 (F1/F2, 488 governance tests). None merged by Claude. |

## 2. Corrections Claude made to itself

* Claude called `59c623fa` "a Hermes merge, not a ratification". The orama ratification addendum
  names it as the
**ratified base commit**; a base commit is simply main's tip when the spec was ratified, so an
unrelated merge
  subject does not make the citation wrong. The wording was removed before pushing.
* Claude merged Oramasys #74 before fixing the combined-tree break with #73 and was told to stop
  merging. The fix was
  the public typed call, not a private shortcut.

## 3. Open work, by owner

* Operator: merge or review the four PRs; freeze or amend TC1-TC7; decide TC7 (the fast-mode allow
  path).
* Codex or Claude: TC2/TC3 and TC4/TC5 need a signed v2 dispatch-grant format first; Sections 3.1,
  3.2 and 4.
* Not done: any `fast=True` allow path, serving, signing activation, provider transport, pin
  changes.
