# Review Queue — 2026-06-28 (Mac↔Win live re-verify)

## Plans to read at next session start

| Plan | Status | Link |
|---|---|---|
| Security hardening pre-v2 | ✅ COMPLETE 2026-06-28 | [`2026-06-27-security-hardening-pre-v2.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-27-security-hardening-pre-v2.md) |
| Hermes-harness onboarding | ✅ Phase 6+9 done (Win + Mac) | [`2026-06-24-hermes-harness-canonical-onboarding.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-hermes-harness-canonical-onboarding.md) |
| Optimization priorities | L1 in progress (pytest + probes ✅); L6 📋 | [`2026-06-24-optimization-priorities.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-optimization-priorities.md) |

## Completed this session (2026-06-28 live re-verify)

- ✅ Both repos on `main`, synced with origin
- ✅ `start.sh --status` Tier 1 FULL — Mac localhost + Win `192.168.254.100`
- ✅ Win `LM_READY` via 27B canary from Mac (cross-harness)
- ✅ `start.sh --hardware-policy` — openclaw.json clean
- ✅ Mac Ollama `qwen3.5:9b-nvfp4` + `bge-m3`
- ✅ perpetua-core pytest 62/62
- ✅ orama evidence doc committed on main

## Still pending (needs Win console or user)

- Win localhost: `verify_partner_canaries.py` + thin skills `--install --verify --test` (SSH :22 closed from Mac)
- `openclaw.gateway-auth-token` in Keychain (user must provide value)
- L1: `engine.ainvoke` round-trip both hardware targets → `v0.2.0-alpha` tag

## Candidate queue

<!-- review-queue-dynamic -->

_No pending candidates._
