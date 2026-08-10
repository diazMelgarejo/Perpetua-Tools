# Lessons journal: interrupted reasoning and branch recovery

**Date:** 2026-08-10  
**Theme:** continuity, provenance, branch hygiene, and reviewable reconstruction

## Gold nuggets

- **Current state beats remembered intent.** After an interrupted or retried
  agent run, re-read branch heads, commit parents, and exact diffs before
  writing again.
- **A retry is a new execution path, not proof of continuous hidden reasoning.**
  The OpenAI additional-check flow can offer a faster-model retry for the same
  request. Treat the result as a fresh execution that must re-ground itself.
- **GitHub identity is not model provenance.** When several agent runs write
  through one connected account, commit author metadata cannot identify the
  model or run that produced a change.
- **Recover content separately from history.** A noisy branch may contain
  excellent final blobs. Reuse verified artifacts while reconstructing clean
  parent and tree relationships for review.
- **Do not rewrite shared `main` for cosmetic cleanup when its tree is correct.**
  Preserve shared history unless correctness or security requires surgery.
- **Stacked PRs should be true in Git, not just in prose.** PR2's commit parent
  must be PR1's tip, and PR2's GitHub base must be PR1's branch until PR1 merges.
- **Historical plans are a parts bin.** Mine schemas, invariants, acceptance
  tests, and naming patterns. Reject stale assumptions, model IDs, paths, and
  obsolete ownership.
- **Feature flags must not be inferred from credentials.** An
  `OPENROUTER_API_KEY` does not enable paid Tier-5 execution.
  `PIPELINE_TIERED_ENABLED=1` is a separate explicit decision.
- **Policy and execution stay separate.** `frugality_router` and `gate` decide
  whether Tier 5 is allowed. `tiered_pipeline` executes only after permission.
- **Never synthesize provider authorization.** Package presence, `doctor`,
  marker files, browser consent, login state, and terms acceptance are different
  facts.
- **Publish once when coordination matters.** Build blobs, tree, tests, and
  memory first. Expose the branch only after the PT change set is coherent.
- **The elegant recovery minimizes new concepts.** Reuse requirement gates,
  frugality policy, memory conventions, and current mastery ownership instead
  of introducing parallel mechanisms.

## OpenAI references

- Additional automated safety checks and faster-model retry behavior:
  https://help.openai.com/en/articles/20001326
- ChatGPT model and retry behavior:
  https://help.openai.com/en/articles/11909943-gpt-53-and-52-in-chatgpt
