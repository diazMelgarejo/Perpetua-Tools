# Decision: interrupted-agent recovery protocol

**Date:** 2026-08-10  
**Status:** adopted operational pattern

## Decision

When an agent run is interrupted, retried with a different model or speed, or
resumes against a branch that may have changed, recover from repository evidence
rather than conversational continuity.

## Protocol

1. Freeze writes.
2. Read current `main`, branch heads, commit parents, and changed files.
3. Classify repository state as trusted content, untrusted sequencing, or both.
4. Preserve verified blobs and tests.
5. Reconstruct review branches from known-good parent and tree relationships.
6. Avoid shared-history rewrite unless correctness or security requires it.
7. For stacked PRs, encode dependency in commit parentage and PR base.
8. When a single-push workflow is requested, publish the branch only after the
   final tree and tests are assembled.

## Rationale

Conversation and UI continuity are not durable provenance mechanisms. Git
parentage, current file content, explicit ownership contracts, and tests are.

## Related external behavior

OpenAI documents that some requests may undergo additional automated safety
checks and may offer a retry with a faster model. Selecting the faster option
retries the same request using a different faster model. Agents must therefore
re-ground repository state instead of assuming uninterrupted execution state.

Reference: <https://help.openai.com/en/articles/20001326>
