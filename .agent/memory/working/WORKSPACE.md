# WORKSPACE — current task state

**Updated:** 2026-08-03 (post-merge follow-up on `main`)  
**Active session:** PR-body grant — #260 and #320 merged; landing Batch H memory + plan deferral

## Current focus

| Repo | PR | Branch | Tip SHA | Role |
| ---- | -- | ------ | ------- | ---- |
| orama-system | [#260](https://github.com/diazMelgarejo/orama-system/pull/260) | merged → `main` | `04048dcc` | Grant v2 squash on `main` |
| Perpetua-Tools | [#320](https://github.com/diazMelgarejo/Perpetua-Tools/pull/320) | merged → `main` | `1319742e` | Grant stack squash on `main` |
| orama-system | follow-up | `post-grant-followup-orama` | (pending push) | Plan v2.1+ deferral doc |
| Perpetua-Tools | follow-up | `post-grant-followup-pt` | (pending push) | Batch H `.agent` memory |

Both PRs **#260** and **#320** are merged (squash). Grant scripts on `main` already match
the old PR branch tips; remaining delta is memory (PT) and plan deferral wording (orama).

## Saga doc (read this first)

`PR_BODY_GRANT_HMAC_MVP_SAGA_2026-08-02.md` — timeline, research, decisions D1–D20, replay state
machine, operator workflow, tips.

**This round:** `PR_BODY_GRANT_CAN6_SCRUB_FOLLOWUP_2026-08-03.md` — scrub_dsstore manifest,
can-6 fixes, v2.1+ deferral doctrine.

## Canonical artifacts

| What | Path |
| ---- | ---- |
| Implementation plan | orama `docs/plans/2026-08-02-pr-body-grant-security-remediation.md` |
| Security research | orama `bin/orama-system/references/pr-body-human-grant-security-gap-research.md` |
| v2.1 deferral | orama `docs/v2/51-security-sentinel-orbit-passkey-mcp.md` |
| Decision JSONL | `.agent/memory/working/PR_BODY_GRANT_HMAC_DECISIONS_2026-08-02.jsonl` |
| CodeRabbit wave report | `CODERABBIT_REVIEW_WAVE_4835024659_4835288649_2026-08-01.md` (Batches F + G) |
| can-6 follow-up | `PR_BODY_GRANT_CAN6_SCRUB_FOLLOWUP_2026-08-03.md` |

## Operator quick path

```bash
# Operator terminal only (TTY + not CURSOR_AGENT/CI)
bash scripts/cursor/grant-pr-body-human-override.sh owner/repo N --file follow-up.md
bash scripts/cursor/append-pr-body.sh owner/repo N --file follow-up.md
```

Grant lifecycle: **mint → reserve → append-pr-body.sh (internal gh edit) → mark-applied → consume**.
Re-run append reconciles if follow-up already on remote (crash recovery).

## Verification (last run 2026-08-03)

```bash
python3 -m pytest tests/test_pr_body_grant_lib.py tests/test_append_pr_body_grant_flow.py \
  tests/test_pr_body_guard_core.py tests/test_check_guard_sync_divergence.py -q
```

Run separately in each repo, not combined into one aggregate figure --
26 passed in orama-system, 26 passed in Perpetua-Tools (same count in
each since the two repos are synced copies of these test files, not a
coincidence worth reading as one combined 26).

## Next

- Merge orama #260 → `main`, then PT #320 → `main`
- Doctrine pass: grep `operator-grant-v1`, `CURSOR_PR_BODY_HUMAN_OVERRIDE_ACK` in hookify/rules
- v2.1+: ENG-6 lock, ENG-4 fail-closed providers, DX-5 extended recovery, WebAuthn sentinel
