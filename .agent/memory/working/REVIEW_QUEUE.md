# Review Queue — 2026-06-28 (Hermes Win testdrive)

## Plans to read at next session start

| Plan | Status | Link |
|---|---|---|
| Security hardening pre-v2 | ⚠️ Win partial — Mac↔Win cross-harness + T5 tags remain | [`2026-06-27-security-hardening-pre-v2.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-27-security-hardening-pre-v2.md) |
| Windows handoff | ✅ Phase 6+9 done; ⏳ Mac LAN probe + T5 | [`docs/2026-06-28-windows-handoff.md`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/docs/2026-06-28-windows-handoff.md) |
| Hermes-harness onboarding | **Phase 6+9 ✅ Win 2026-06-28** | [`2026-06-24-hermes-harness-canonical-onboarding.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-hermes-harness-canonical-onboarding.md) |
| Optimization priorities | L1 open, L6 📋 | [`2026-06-24-optimization-priorities.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-optimization-priorities.md) |

## Completed this session (2026-06-28 Win)

- ✅ Hermes Phase 6+9 live on Windows (thin wrappers + canaries)
- ✅ `ensure-partner-cli-paths.ps1` + parametric partner CLI docs
- ✅ `verify_partner_canaries.py`: LM Studio/Hermes/Codex/cursor-agent PASS
- ✅ Canary model `stepfun/step-3.7-flash:free`; LM Studio `state=loaded` probe
- ✅ OpenClaw optional on Windows (skip when absent)
- ✅ Working memory: `.agent/memory/working/HERMES_WIN_TESTDRIVE_2026-06-28.md`

## Still pending (Mac)

- `start.sh --hardware-policy` cross-harness with Win LM Studio LAN
- `openclaw.gateway-auth-token` in Keychain
- T5 git tags after Mac↔Win E2E green

## Candidate queue

<!-- review-queue-dynamic -->

_No pending candidates._
