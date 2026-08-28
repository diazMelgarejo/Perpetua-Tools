# MiniGraph core latest review closure — 2026-08-29

This append-only record closes the two still-open `oramasys/perpetua-core` PR #1
findings preserved by `lesson_230c6d2c5a7e` and the weekly reconciliation
record.

## Exact head

```text
488bc6cc440247ca86811c46ae0dd05869898324
```

PR #1 is open, mergeable, and not draft at this head.

## Finding 1 — caller-owned mutable delta aliasing

Fixed with:

```python
from copy import deepcopy

return self.model_copy(update=deepcopy(delta), deep=True)
```

The dedicated regression proves:

- caller mutation after `merge()` cannot mutate the merged state;
- merged-state mutation cannot mutate the caller-owned delta;
- prior state remains unchanged;
- ordinary delta application still works.

CodeRabbit marks the review thread addressed/resolved in commit `488bc6c`.

## Finding 2 — persisted checkout credentials

The PR workflow now uses:

```yaml
- uses: actions/checkout@v4
  with:
    persist-credentials: false
```

CodeRabbit marks the CWE-522 review thread addressed/resolved in commit
`488bc6c`.

## Exact-head verification

GitHub Actions run:

```text
33218400901
```

completed successfully.

```text
pytest (3.11)  SUCCESS
pytest (3.12)  SUCCESS
```

Therefore both findings are closed for exact head `488bc6cc...`.

A later PR head does not inherit this proof automatically; current-head CI and
review state must be rechecked after any additional code change.

## Related memory

- `lesson_230c6d2c5a7e`
- `WEEKLY_RECONCILIATION_2026-08-23_TO_2026-08-29.md`
- `PT_UNBUNDLING_MIGRATION_MAP_2026-08-29.md`
