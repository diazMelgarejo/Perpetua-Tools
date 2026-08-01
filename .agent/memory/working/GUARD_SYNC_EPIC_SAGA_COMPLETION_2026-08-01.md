# Guard sync epic saga — completion record (2026-08-01)

## Outcome

Three-repo attribution-guard stack is aligned on hardened `audit_engine.py` and
`banned_attribution_lib.sh`, delivered through **one open PR per repo** (no
fragmentation).

| Repo | PR | Branch | Role |
| ---- | -- | ------ | ---- |
| Perpetua-Tools | [#319](https://github.com/diazMelgarejo/Perpetua-Tools/pull/319) | `cursor/guard-audit-hardening-f559` | **Canonical source** for this wave |
| AlphaClaw | [#26](https://github.com/diazMelgarejo/AlphaClaw/pull/26) | `cursor/sync-attribution-guards-6421` | Downstream mirror |
| orama-system | [#255](https://github.com/diazMelgarejo/orama-system/pull/255) | `2026-07-31-010-remediation-doctrine-phase6-sync` | Downstream mirror + doctrine |

## Tortuous path (what went wrong)

1. **PR #314 merged** guard-sync tests and `reanchor_scan.sh`, but CodeRabbit
   nitpicks on `audit_engine.py` / `banned_attribution_lib.sh` were left open.
2. **PR #315 falsely claimed** to supersede #314 — it would have *removed* guard
   sync tests and regressed `reanchor_scan.sh`. Never merge duplicate guard PRs.
3. **Blind `sync-attribution-guard-scripts.sh`** (orama → PT) risked overwriting
   PT improvements before they were promoted. **PT staged canonical first**; manual
   byte-copy from PT manifest paths only.
4. **CI hygiene failure** on #319: `tests/test_audit_engine.py` tripped private
   verboten literal scan — fixed via `IDENTITY_DOC_EXCEPTIONS` (same rationale as
   `identity-policy.json`).
5. **Off-by-one** in `_read_commit_metadata`: `len(parts) < max_parts` used split
   maxsplit instead of minimum field count — fixed to `len(parts) < 5`.

## Canonical sync procedure (reuse PRs, one wave)

```text
A. Fix PT on open PR #319 (rebase main → fix CI + CodeRabbit → push)
B. Copy GUARD_SYNC manifest files PT → AlphaClaw PR #26 → push
C. Copy GUARD_SYNC manifest files PT → orama PR #255 → push
D. Merge in order: PT #319 → orama #255 → AlphaClaw #26
   (then flip manifest comment: orama canonical again if desired)
```

**Do not** open N single-file PRs. **Do not** run orama→PT sync until PT wave merges.

## CodeRabbit fixes applied (all three repos)

- `banned_attribution_lib.sh`: pure-bash `_trim_edges`, reuse at line 119
- `audit_engine.py`: co-author fail-closed (`AttributionCheckError`)
- `audit_engine.py`: removed `os.chdir` from `run_attribution_audit`
- `audit_engine.py`: one `git log` per commit + one policy load per run
- `audit_engine.py`: `_meta` discard in `_audit_ref`; `len(parts) < 5` guard

## Verification

- PT: `pytest tests/test_audit_engine.py` (29), guard manifest tests (6), `repo_hygiene.py` OK
- orama: `pytest tests/test_audit_engine.py` (29) after sync
- AlphaClaw: guard files byte-synced from PT manifest

## Related PRs (closed context)

- PT #314 / #318 — guard manifest tests, `pr.md` publisher routing (merged)
- PT #317 — episodic canonical schema (merged)
- AlphaClaw #27 — ecc-tools security-evidence only (narrowed, separate)
