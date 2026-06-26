# Review Queue — 2026-06-27

## Plans to read at next session start

| Plan | Status | Link |
|---|---|---|
| Optimization priorities | L1 open, L6 📋 | [`2026-06-24-optimization-priorities.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-optimization-priorities.md) |
| Hermes-harness onboarding | Phases 1-5+7+8 ✅, 6+9 ⏳ | [`2026-06-24-hermes-harness-canonical-onboarding.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-hermes-harness-canonical-onboarding.md) |
| Windows hardware walkthrough | Deferred (live machine) | [`2026-06-24-hermes-windows-hardware-policy-walkthrough.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-hermes-windows-hardware-policy-walkthrough.md) |

## Candidate queue

_No pending candidates._ (Dream cycle 2026-06-24 `76d0407` graduated 4, rejected 2.)

Run `python .agent/tools/list_candidates.py` for detail.

## Next session priorities (by machine)

### Any machine
- L6: create `schemas/` directory with `topology.schema.json`, `devices.schema.json`, `skills.schema.json`
- oramaclaw engine.py: orphan conflict cleanup + cooperative timeout bypass
- Apply progressive-disclosure pattern to the 654-line hermes-harness plan (split into index + sub-specs)

### Live Windows required
- L1: perpetua-core hardware review → push `feat/salvage-plugins-rc1` → tag `v0.2.0-alpha`
- Phase 6: `install_hermes_thin_skills.py --install --verify --test`
- Phase 9: Windows thin wrappers → additive migration → verify
