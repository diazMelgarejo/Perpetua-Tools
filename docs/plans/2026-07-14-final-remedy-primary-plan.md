# Final Remedy Primary Plan — OramaSys Integration

Status: primary execution/audit plan on `kimi-meta-remediation`; stop at the decision gate before Secondary remediation.

## AFRP

AFRP: Type C | Level Expert | Mode 3
Scope: Preserve refs, isolate misplaced memory-remediation commits, reset `main` and PR #211 to clean anchors with leases, then pause before Secondary review fixes.

## Canonical doctrines applied

- `bin/orama-system/skills/oramasys-method/SKILL.md`
- `bin/orama-system/skills/oramasys-method/references/integrative-merge.md`
- `bin/orama-system/references/post-review-micro-remediation.md`
- `bin/orama-system/skills/git-history-surgery/SKILL.md`

Core rules:

1. Freeze `main` as a development target.
2. Preserve safety refs before every rewrite.
3. Use exact `--force-with-lease` values.
4. Synthesize, never amputate.
5. Do not hand-merge generated memory output such as `LESSONS.md`; replay through the memory pipeline.
6. Stop after primary branch/history cleanup before Secondary remediation.

## Verified primary refs

```text
main pre-reset:
  6c2d211408d9fff34234d8f310808e7aaf17d86d

main rollback target:
  89b7743a450c3699760bbe9437ccc09ac59df111

PR #211 pre-reset branch/head:
  kimi-lan-peer-job-board
  65a6599100d8d2a7ea69db0b1022b9c05476622b

PR #211 clean anchor:
  32f0b76bf68db04d044b4b1bc611c36ff9b1c83f

PR #212 preserved head:
  2026-07-11-001-salvage-heartbeat-skill-wrapper
  680e1e7bcbc3b5f1a97359de44959deb65e81511
```

## Safety refs

```text
safety/final-remedy-main-pre-20260714  -> 6c2d211408d9fff34234d8f310808e7aaf17d86d
safety/final-remedy-pr211-pre-20260714 -> 65a6599100d8d2a7ea69db0b1022b9c05476622b
safety/final-remedy-pr212-pre-20260714 -> 680e1e7bcbc3b5f1a97359de44959deb65e81511
```

## Primary execution sequence

1. Create safety refs for current `main`, PR #211, and PR #212.
2. Create `kimi-meta-remediation` from the PR #211 meta-remediation chain through `22b2a0c`.
3. Exclude `65a6599100d8d2a7ea69db0b1022b9c05476622b` from `kimi-meta-remediation`.
4. Preserve `6c2d211408d9fff34234d8f310808e7aaf17d86d` in `safety/final-remedy-main-pre-20260714` rather than hand-merging its generated `LESSONS.md` delta. Direct cherry-pick onto `32f0b76` conflicted in generated memory output, so doctrine requires replay through the memory pipeline later instead of resolving by hand.
5. Add this plan as the branch-local audit artifact.
6. Reset remote `main` from `6c2d211` to `89b7743a` with exact lease.
7. Reset remote PR #211 branch from `65a6599` to `32f0b76` with exact lease.
8. Re-fetch and verify refs.
9. Stop at the decision gate before Secondary remediation.

## Branch contents and intent

`kimi-meta-remediation` is a quarantine/draft branch, not automatically merge-ready. It preserves the PR #211 meta-remediation sequence through:

```text
cf58ef8915e491765b70540383a37fd5b62bcdea
22b2a0cedccc1acee94e6fa1d7b49cfc6d9187bc
```

It deliberately excludes:

```text
65a6599100d8d2a7ea69db0b1022b9c05476622b
```

The `main`-local memory commit is preserved at the safety ref and must be replayed later via the correct memory ritual/pipeline, not by manual `LESSONS.md` conflict resolution.

## Decision gate before Secondary

After primary steps are complete, do not start Secondary findings until the operator confirms the next target. At the gate, decide whether to:

1. merge/re-evaluate PR #212 against corrected `main`,
2. open/review `kimi-meta-remediation` as quarantine/draft, or
3. begin Secondary review-finding remediation on the appropriate PR branch.

## Secondary backlog classification

Secondary findings remain unstarted until the gate. They should be clustered by invariant:

- transaction/concurrency correctness,
- durable persistence and retry safety,
- security/redaction/fail-closed behavior,
- authenticated identity/provenance,
- coordination lifecycle and ordering,
- path hygiene and generated-memory correctness.

Each finding must be re-verified against current code before patching and reported as fixed, superseded, or skipped with a reason.
