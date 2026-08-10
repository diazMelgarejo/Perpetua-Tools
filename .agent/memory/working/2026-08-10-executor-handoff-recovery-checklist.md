# Executor Handoff / Retry Recovery Checklist

Use this when a model switch, reasoning-mode retry, interrupted stream, resumed
agent, or tool executor change occurs while a task has external side effects.

## Before the next write

- [ ] Stop mutating tools.
- [ ] Re-fetch the canonical repository and `main` tip.
- [ ] Re-fetch every branch and PR this task may have touched.
- [ ] Record intended repo, base SHA, branch, PR base, and expected file set.
- [ ] Compare actual changed files against expected scope.
- [ ] Classify existing work: verified-good, uncertain, accidental,
  already-canonical.
- [ ] Do not infer executor/model attribution from the connected Git identity.

## Recovery choice

Prefer, in order:

1. Continue only if state exactly matches the recorded contract.
2. Salvage verified file blobs/content onto the trusted base.
3. Reconstruct a clean commit/tree.
4. Revert only the specifically proven bad delta.

Avoid blanket branch deletion when useful verified work exists.

## Write discipline

- [ ] Never use a production write to test whether a connector supports a
  capability.
- [ ] Use schema discovery and read-only calls first.
- [ ] For Git reconstruction, use explicit tree and parent SHA where possible.
- [ ] For stacked PRs, verify parent SHA and PR base separately.
- [ ] Publish only after the complete intended tree has been assembled and
  reviewed.

## After publication

- [ ] Verify PR base/head SHAs from GitHub.
- [ ] Verify changed-file count and scope.
- [ ] Verify CI is running against the intended head.
- [ ] Record uncertainty and recovery facts in working memory.
- [ ] Graduate a durable semantic lesson only through canonical memory tooling.

## OpenAI context

These references explain surrounding product and safety behavior but do not define
Git transaction semantics:

- https://help.openai.com/en/articles/20001326
- https://help.openai.com/en/articles/20001354
- https://openai.com/policies/usage-policies/

Engineering invariant: **after an executor retry or handoff, external-state
continuity is unproven until revalidated.**
