# Review Queue — 2026-06-28 (end of session)

## Plans to read at next session start

| Plan | Status | Link |
|---|---|---|
| Security hardening pre-v2 | ⚠️ Partial — Gemini keys stored; TELEGRAM + GATEWAY_AUTH need user values | [`2026-06-27-security-hardening-pre-v2.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-27-security-hardening-pre-v2.md) |
| Windows handoff | ⏳ Pending Win machine — T5 tags, Hermes 6+9, cross-harness affinity | [`docs/2026-06-28-windows-handoff.md`](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/docs/2026-06-28-windows-handoff.md) |
| Hermes-harness onboarding | Phases 1-5+7+8 ✅, 6+9 ⏳ blocked on Win | [`2026-06-24-hermes-harness-canonical-onboarding.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-hermes-harness-canonical-onboarding.md) |
| Optimization priorities | L1 open, L6 📋 | [`2026-06-24-optimization-priorities.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-optimization-priorities.md) |

## Completed this session (2026-06-28)

- ✅ PT PR #173 merged (`820e078a`) — fail-closed routing hardening; all CI + CodeRabbit fixes
- ✅ PR #123 + #111 CodeRabbit post-merge fixes committed directly on main (`e882fb2`)
- ✅ Gemini main + fallback stored in macOS Keychain; `load_keychain_secrets.sh` added
- ✅ 7 lessons graduated (incl. keychain naming convention lesson `2a6766b489c5`)
- ✅ Windows handoff doc created: `docs/2026-06-28-windows-handoff.md`
- ✅ Both repos pushed and clean (PT `75981fd`, orama `3a854bc`)

## PRs open for human review

- **PT #154**: S4+S8 security fixes. CI 4/4 ✅. Ready for review.
- **OS #113**: T3+T4 tier fixes + version 1.1.1.0. CI 13/14 ⚠️ (pytest-asyncio note). Ready after CI resolved.

## Candidate queue

<!-- review-queue-dynamic -->

_No pending candidates._
