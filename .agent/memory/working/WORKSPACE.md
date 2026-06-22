# Workspace (live task state)

Last updated: 2026-06-22 by claude-opus-4.8

## Current task
v2 repos restructured to PyPA src-layout and the session's interpretation gap
captured. Knowledge-capture + structural cleanup session — complete.

## Key findings
- `oramasys/perpetua-core` + `oramasys/oramasys` now use src-layout
  (`src/<pkg>/`, tests in `src/tests/`, thin `/bin`, README). Merged to `main`,
  pushed: `perpetua-core 8c063f4` (62 tests), `oramasys 0f5ba2b` (5 tests).
- An AI interpretation gap was corrected and enshrined: assumed `.agents/memory`
  over the explicit `.agent/memory`, on a stale branch, without reading AGENTS.md.
  Wrong commit erased; lessons recorded via `learn.py`; DO-NOT added to AFRP + CIDF.

## Open files / artifacts
- `docs/2026-06-22-oramasys-v2-intent-and-interpretation-gap.md` (exhaustive account)
- `.agent/memory/semantic/DECISIONS.md` §2026-06-22
- `https://github.com/oramasys/perpetua-core`, `https://github.com/oramasys/oramasys`

## Checkpoints
- [x] perpetua-core + oramasys src-layout, verified (62 / 5 tests)
- [x] Merged to main + pushed (both repos + orama-system + PT memory)
- [x] Lessons recorded via .agent learn.py (4 ids)
- [x] DO-NOT enshrined in AFRP (trigger 3) + CIDF (Target Verification)
- [x] Exhaustive intent/gap/why-v2 account written
- [ ] User hardware review (Mac Ollama + Win LM Studio) before any release gate

## Next step
Awaiting user direction. Hardware review gate remains open per PROGRESS.md push policy.
