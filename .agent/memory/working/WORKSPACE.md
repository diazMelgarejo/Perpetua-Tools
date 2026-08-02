# WORKSPACE — current task state

**Updated:** 2026-08-02  
**Active session:** PR-body grant HMAC MVP (post-#255) + PT #320 pairing

## Current focus

| Repo | PR | Branch | Role |
| ---- | -- | ------ | ---- |
| orama-system | (open next) | `2026-08-02-pr-body-grant-hmac-mvp` | **Canonical** grant v2 + hooks |
| Perpetua-Tools | [#320](https://github.com/diazMelgarejo/Perpetua-Tools/pull/320) | `2026-08-02-pr-body-grant-hmac-mvp` | Mirror via sync script |
| orama-system | [#255](https://github.com/diazMelgarejo/orama-system/pull/255) | merged → `main` | Baseline at `525961d6` |

## Saga doc (read this first)

`PR_BODY_GRANT_HMAC_MVP_SAGA_2026-08-02.md` — timeline, research, decisions, operator workflow, tips.

## Canonical artifacts

| What | Path |
| ---- | ---- |
| Implementation plan | orama `docs/plans/2026-08-02-pr-body-grant-security-remediation.md` |
| Security research | orama `bin/orama-system/references/pr-body-human-grant-security-gap-research.md` |
| v2.1 deferral | orama `docs/v2/51-security-sentinel-orbit-passkey-mcp.md` |
| Decision JSONL | `.agent/memory/working/PR_BODY_GRANT_HMAC_DECISIONS_2026-08-02.jsonl` |
| CodeRabbit wave report | `CODERABBIT_REVIEW_WAVE_4835024659_4835288649_2026-08-01.md` |

## Operator quick path

```bash
# Operator terminal only
bash scripts/cursor/grant-pr-body-human-override.sh owner/repo N --file follow-up.md
bash scripts/cursor/append-pr-body.sh owner/repo N --file follow-up.md
```

## Next

- Push paired branches; open orama PR; refresh PT #320 description with orama commit SHA
- Grep repo for stale `operator-grant-v1` / `CURSOR_PR_BODY_HUMAN_OVERRIDE_ACK` doctrine
- v2.1: security-sentinel satellite (no passkey code in orama scripts)
