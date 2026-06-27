# Review Queue — 2026-06-27 (end of session)

## Plans to read at next session start

| Plan | Status | Link |
|---|---|---|
| Security hardening pre-v2 | 🔄 In progress — PRs #154 + #113 open | [`2026-06-27-security-hardening-pre-v2.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-27-security-hardening-pre-v2.md) |
| Hermes-harness onboarding | Phases 1-5+7+8 ✅, 6+9 ⏳ | [`2026-06-24-hermes-harness-canonical-onboarding.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-hermes-harness-canonical-onboarding.md) |
| Hermes-harness onboarding | Phases 1-5+7+8 on main (#108); 6+9 prep offline (`--prepare`, checklist) | [`2026-06-24-hermes-harness-canonical-onboarding.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-hermes-harness-canonical-onboarding.md) |
| Optimization priorities | L1 open, L6 📋 | [`2026-06-24-optimization-priorities.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-optimization-priorities.md) |

## PRs open for human review

- **PT #154**: S4+S8 security fixes. CI 4/4 ✅. Ready for review.
- **OS #113**: T3+T4 tier fixes + version 1.1.1.0. CI 13/14 ⚠️ (pytest-asyncio note — see WORKSPACE). Ready for review after CI note resolved.

## Candidate queue

_No pending candidates._

## Next session priorities

### Human required first
- Review + approve (or request changes on) PR #154 and PR #113
- Confirm PR #113 CI note (pytest-asyncio [dev] extras in CI install step)

### Any machine (after PRs merge)
- Freeze procedure: version bump → tag v1.1.1/v1.0.0 → release → v2 branch
- L6: schemas/ JSON Schema files

### Live Windows
- L1: perpetua-core hardware review → push → v0.2.0-alpha
- Phase 6+9: Hermes thin wrappers
