# Working memory: interrupted reasoning, faster retry, and clean branch recovery

**Date:** 2026-08-10  
**Scope:** orama-system stacked PR recovery + Perpetua-Tools P4 closure  
**Status:** retained working context for future agents

## Situation

A long-running repository task was interrupted by an in-product notice that
additional automated checks were running. The notice offered a retry with a
faster model. The operator selected that retry accidentally, observed repository
edits diverging from the intended architecture, and stopped the retry.

Official OpenAI context:

- Additional safety checks:
  <https://help.openai.com/en/articles/20001326>
- ChatGPT model and retry overview:
  <https://help.openai.com/en/articles/11909943-gpt-53-and-52-in-chatgpt>

The OpenAI help article says these checks are automated, may take extra time,
and may offer a faster-model retry. Selecting that option retries the same
request with a faster model. It is not evidence that the new execution continues
the exact unfinished reasoning state of the prior run.

## Evidence boundary

Observed:

- The UI displayed the additional-check and faster-retry notice.
- A faster retry was selected accidentally.
- Repository commits appeared before the original task produced its intended
  final response.
- The operator stopped the run after recognizing architectural divergence.
- GitHub showed branch changes and transient commits that needed reconciliation.

Not provable from GitHub alone:

- Which model authored any specific commit.
- Whether a commit came from the original run, the faster retry, or a later
  recovery run when all writes use the same GitHub account identity.

Never label commit provenance by model as fact unless an external execution
record proves it.

## Recovery method used

1. Stop further writes.
2. Read current `main`, feature branch heads, commit parentage, and trees.
3. Preserve `main` content rather than rewrite shared history to remove no-op
   commits.
4. Treat the interrupted feature branch as a salvage source, not a review branch.
5. Reuse only final-good blobs re-verified against current code and tests.
6. Reconstruct a clean PR1 commit directly on current `main`.
7. Create PR1 from that single commit.
8. Build PR2 as a child whose parent is exactly PR1's tip.
9. Point a separate PR2 branch at that child commit.
10. Reset the PR1 branch ref to PR1's exact tip.
11. For PT, assemble blobs, tree, commit, tests, and memory first.
12. Create the public PT branch ref only after the change set is complete.

## Architecture recovered

### orama PR1: MCP first-run readiness

The best boundary is not to grow launchers into installers.

```text
macOS/Linux start.sh
  -> scripts/ensure_requirements.sh
       -> scripts/ensure_ai_cli_mcp.py

Windows start.ps1
  -> existing partner-CLI preparation hook
       -> scripts/ensure_ai_cli_mcp.py

Windows explicit requirements probe
  -> scripts/ensure_requirements.ps1
       -> scripts/ensure_ai_cli_mcp.py

Explicit MCP stack installer
  -> install-mcp-stack.sh
       -> scripts/ensure_ai_cli_mcp.py
```

Core package/runtime readiness and provider authorization are distinct states.
Do not manufacture login, consent, terms acceptance, or permission state from a
marker file or a timeout-tolerant command.

### orama PR2: mastery convergence

Historical plans are evidence and reusable design inventory, not current truth.

The current-state audit showed P0 and M1-M6 are already materially present. The
remaining implementation is a structural convergence test, not a second copy of
the mastery text.

### PT P4

The current frugality router and gate remain policy owners. Tier-5 pipelines are
an execution primitive beneath that gate, never a second model router. Pipeline
enablement is explicit and off by default. Model IDs and provider secrets remain
runtime configuration.

## What went wrong during recovery

A recovery attempt briefly created transient placeholder commits while
identifying connector branch and ref capabilities. The durable lesson is to
discover mutation schemas first. When low-level Git objects are available,
create blobs, trees, and commits without refs and publish only the verified
final branch.

## Durable protocol

When a long reasoning run is interrupted or retried:

- Freeze writes before interpreting provenance.
- Re-read live repository state; do not trust the previous plan's assumed head.
- Separate content recovery from history recovery.
- Salvage verified blobs rather than preserve a noisy execution chronology.
- Never rewrite shared `main` only for aesthetic history cleanup when its tree is
  correct.
- Reconstruct feature branches from known-good parent and tree relationships.
- For stacked PRs, require PR2 parent == PR1 tip and PR2 base == PR1 branch.
- Before publishing, compare the exact diff against ownership boundaries.

## Reflection

The interruption exposed a systems principle: continuity of intent cannot be
inferred from continuity of UI, branch name, or GitHub author identity. Durable
continuity comes from contracts, current repository state, parentage, tests, and
minimal-diff reconstruction.

The strongest recovery was not "undo everything." It preserved good work,
discarded only untrusted sequencing, and rebuilt the review surface from
verified artifacts. That matches CIDF and ORAMASYS: choose the simplest reliable
representation, verify before declaring success, and optimize the larger system
instead of the visible symptom.
