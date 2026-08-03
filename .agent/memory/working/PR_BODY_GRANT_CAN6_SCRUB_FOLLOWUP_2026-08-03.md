# PR-body grant — can-6 + scrub_dsstore follow-up (2026-08-03)

> **Status:** shipped on paired branches (orama #260, PT #320)  
> **orama tip:** `4756d66f` on `2026-08-02-pr-body-grant-hmac-mvp`  
> **PT tip:** `091e2fa4` on `cursor/coderabbit-review-wave-sync-f559` (PR #320)  
> **Trigger:** CodeRabbit can-6.md + scrub_dsstore pre-push warning on PT  
> **Prior batch:** Batch G remediation (`739e2fe5` / `4ca359bb`) — see saga chronicle

## Executive outcome

Closed the **scrub_dsstore manifest gap** (PT hook called a script that never synced) and the
**can-6 CodeRabbit wave** on grant v2 without expanding MVP scope. Grant stack remains
byte-identical orama ↔ PT after `sync-attribution-guard-scripts.sh`.

All plan findings **intentionally not implemented in this round** are **v2.1+ or later** — not
open MVP defects. MVP v2 ships escalation control + replay state machine; crypto-heavy orbit
work stays in security-sentinel v2.1.

## What shipped

### scrub_dsstore (1–3)

| # | Change |
| - | ------ |
| 1 | `scrub_dsstore.sh` added to `guard-sync-manifest.sh` → PT receives script on sync |
| 2 | `.githooks/pre-commit` / `pre-push` run scrub only when `[[ -x scripts/git/scrub_dsstore.sh ]]` |
| 3 | Synced script + manifest to PT; githooks mirrored on PT branch |

### can-6 code

- `pr-body-guard-core.py`: RUF005 `[*backup_lines, "ALLOW"]`
- `grant-pr-body-human-override.sh`: usage error when `<2` positional args
- `append-pr-body.sh`: consume-failure message names ack delete + backup path
- `pr-body-grant-lib.py`: `_locked_nonce_state()` context manager; `_write_private_file()`
  (`O_EXCL|O_NOFOLLOW`); v1 via `fields["marker"]`; repo `|` rejection; CLI rejects both
  `--file` and `--message`

### can-6 tests

- Fake `gh` scans `--body-file`; asserts follow-up in merged PR body
- TTL expired / future `issued-at`; wrong PR; tampered token; repo pipe
- Golden vector without literal hex (gitleaks-safe)

### can-6 docs (orama canonical)

- `docs/v2/51-security-sentinel-orbit-passkey-mcp.md`: v2.1 alpha label consistency
- Plan doc: shipped API/format alignment; deferred findings tagged v2.1+

## Deferred to v2.1+ or later (not MVP gaps)

These remain documented in orama
`docs/plans/2026-08-02-pr-body-grant-security-remediation.md` as **follow-up orbit**, not
blocking merge of MVP v2:

| ID | Topic | Why v2.1+ |
| -- | ----- | --------- |
| ENG-6 | Per-repo/PR file lock + final remote re-read on append | TOCTOU hardening beyond reconcile MVP |
| ENG-4 | Fail-closed `resolve_hmac_secret` on unsupported providers | Provider interface + sentinel orbit |
| DX-5 | Full crash recovery beyond reconcile CLI | Reconcile covers common case; sentinel adds ops |
| MVP-A/C | Doctrine sweep (hookify, rules, ledger grep) | Process hygiene, not crypto |
| WebAuthn / MCP | Human proof + approval sidecar | `security-sentinel` v2.1 — see doc 51 |
| CLI logging | Route diagnostics through `logging` | DX polish; stdout is operator contract today |

**Rule for agents:** Do not treat these as regressions in MVP review. Do not implement passkeys,
JWKS verification, or mesh approval in orama shell scripts.

## Verification (2026-08-03)

```bash
python3 -m pytest tests/test_pr_body_grant_lib.py tests/test_append_pr_body_grant_flow.py \
  tests/test_pr_body_guard_core.py tests/test_check_guard_sync_divergence.py -q
# Result: 26 passed (orama + PT after sync)
bash scripts/git/verify-guard-parity.sh   # PASS on PT
```

## Push notes

PT pre-push `--workspace` divergence can fail when stale `/tmp` sibling worktrees carry guard
mutations absent from orama canonical. PT ↔ orama grant parity was verified before push.
Escape hatch when only stale siblings block: `GUARD_SYNC_SKIP_DIVERGENCE_CHECK=1` (hook-supported).

Prefer `GUARD_SYNC_CANON_ROOT=<orama-grant-worktree>` when running the checker manually.

## Related memory

- `PR_BODY_GRANT_HMAC_MVP_SAGA_2026-08-02.md` (master chronicle)
- `CODERABBIT_REVIEW_WAVE_4835024659_4835288649_2026-08-01.md` (Batches F + G)
- `WORKSPACE.md` (current focus)
- can-6 source: CotEditor `restricted/cursor/can-6.md`

## Open follow-ups

- [ ] Merge orama #260 → `main`, then PT #320 → `main`
- [ ] Doctrine pass: grep `operator-grant-v1`, env override exports in hookify/rules
- [ ] v2.1: security-sentinel satellite (ENG-6, ENG-4, DX-5, WebAuthn)
