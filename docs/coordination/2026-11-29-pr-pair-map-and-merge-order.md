# Pull request pairs and merge order

Date: 2026-11-29. Records the operator's decisions and the pair map as reported on 2026-11-28, then
what changed when Lane 1 was corrected. `PT` is Perpetua-Tools; `orama` is orama-system.

## Operator decisions (2026-11-29)

1. Keep this pair map, its explanation and its diagram with the Lane 1 branch.
2. Review and develop the corrected Lane 1 and stack its pull request on top of PT #527.
3. Merge as soon as possible. Merging stays an operator action.
4. Remediate the PT #526 review and reply to its comments.

## The three pairs, as reported on 2026-11-28

```text
main
 └─ A: PT #525 + orama #533   merged; all four open drafts contain it
     ├─ B: PT #526  ◄── required by ── orama #534
     └─ C: PT #527       (no code link)     orama #535
              └─ corrected Lane 1 (stacked on #527)
```

| Pair | Relationship |
| --- | --- |
| A (PT #525, orama #533) | Merged foundation |
| B (PT #526, orama #534) | Linked in code: #534 needs the model gate and default settings that #526 adds |
| C (PT #527, orama #535) | Opened together only; #535 changes four test files and needs nothing from #527 |

- Across pairs, PT #526 and #527 conflict in shared memory files. Orama #534 and #535 merge cleanly.

### Two gaps in pair B

Passing checks cover neither:

1. Orama #534 carries an out-of-date copy of #526's default settings. It lacks the new Google
   providers and the one-local-model route rule, and the repository's own drift check fails on it.
2. Orama's checks pin an older Perpetua-Tools commit without the model gate, so #534 was never
   tested there against #526.

## Merge order

1. PT #526.
2. Orama #534: refresh the vendored settings (needs the operator's explicit confirmation) and move
   the pin to a Perpetua-Tools `main` commit that contains #526.
3. Orama #535 at any time; then #534.
4. This Lane 1 branch into PT #527, then #527 into `main`, keeping both sides of the memory files
   that conflict with #526.

## Lane 1: what was corrected here

The candidate `56c2298c` passed its tests and its data-safety checks, but its service let requests
through when it should have refused them. On this branch:

| Behaviour | Candidate `56c2298c` | Now |
| --- | --- | --- |
| Verifier returns `None`, `0` or empty text | Request accepted, task written | 401, nothing written |
| Verifier that cannot take the scope | Write allowed | 401 |
| Verifier raises | Its text returned to the caller | Fixed message; `Forbidden` gives 403 |
| Unexpected internal error | Its text returned as 400 | Generic 503, type logged |
| Free-text `detail` on `fail` | Accepted and ignored | Removed; extra fields give 400 |

Store layout, migration, legacy import and clock handling are unchanged from PT #527. The service is
still an in-process dispatcher: no network binding, no auto-start, not deployable before V1-4.

## Still open

- A backward clock step still quarantines the store permanently, with no reconcile path. Choosing
  between a small tolerance and an operator reconcile step is an operator decision.
- The Lane 5 classification evidence remains unaccepted.
- The one-local-model gate is enforced on macOS only.
