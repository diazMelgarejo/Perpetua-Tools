# PR258 Code Review Coordination Synthesis - 2026-07-18

This note distills the cross-agent coordination around PR258 without preserving
private identity literals, workstation-specific paths, or secret values.

## What Happened

PR258 began as a coordination-module consolidation and privacy/attribution
remediation branch. Multiple agents touched the branch while Git history was
being rewritten and reanchored, which made ordinary ahead/behind counts
misleading. The final content was useful, but the active PR history had become a
poor review surface.

The durable solution was a clean replacement PR:

1. Preserve the old PR tip with local refs and saved diff artifacts.
2. Create a new branch from current `origin/main`.
3. Replay the old PR final tree exactly as the first replacement commit.
4. Prove the replacement diff matches the saved old PR diff.
5. Add later memory/surgery doctrine as a separate follow-up commit.
6. Close the old PR and keep its branch/ref history only as audit evidence.

## Review-Finding Lessons

The review findings were handled by checking current code, not stale review line
numbers. One finding had already been resolved; the remaining findings required
fixes in the attribution guard, private-literal parsing, allowlist behavior,
fallback handling, and hygiene scanning. Literal suggestions from review tools
were treated as hypotheses: where a suggested patch would have broken whitespace
handling or backward compatibility, the implementation kept the intent but used
a safer local design.

## Scrub-Scope Lessons

The session separated four gates that earlier reports had blurred together:

- current tracked-tree hygiene;
- commit metadata/message hygiene;
- branch-unique reachable blob hygiene;
- repository-wide all-ref reachable blob hygiene.

The replacement PR proved the branch-unique scope clean. Historical hits already
reachable from `origin/main` remain a separate repository-wide cleanup question
and must not be described as solved by a branch replacement.

## Tree-Twin Lessons

Tree-twin reanchoring is still the right first diagnostic after a metadata-only
rewrite. In this case, blob-level changes meant an exact tree twin did not exist
for every old point in the graph. That made the clean replacement PR the better
operation: preserve content, remove the noisy/contaminated intermediate commits,
and make the review surface match the intended final artifact.

## Cross-Repo Linkage

The canonical operational doctrine now lives in Orama's `git-history-surgery`
skill. PT should treat that skill as the cross-repo reference for:

- reanchor-after-rewrite tree-twin diagnostics;
- Case C, where blob changes prevent exact tree twins;
- local-only forbidden-pattern scanning;
- clean replacement PRs when final content is correct but intervening history is
  not worth preserving;
- precise closeout language for scrub scope.

Future PT agents should look there before declaring git scrub/surgery complete.
