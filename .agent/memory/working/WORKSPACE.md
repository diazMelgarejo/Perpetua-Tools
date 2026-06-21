# Workspace (live task state)

Last updated: 2026-06-21 by claude-sonnet-4.6

## Current task
Reviewed perpetua-core repo against salvage translation design spec.
No active work item — this is a knowledge-capture session.

## Key finding
`oramasys/perpetua-core` salvage port is **COMPLETE** as of 2026-05-17.
All 16 tasks DONE, 73 tests green across 3 repos.
Branch still local pending Mac+Win hardware review (per Push Policy in PROGRESS.md).

## Open files
- `https://github.com/oramasys/perpetua-core` (cloned /tmp/perpetua-core)
- `orama-system/docs/superpowers/specs/2026-05-17-salvage-translation-design.md`

## Active hypotheses
- The one remaining gate before merge to `oramasys/perpetua-core` main
  is user end-to-end review on Mac Ollama + Win LM Studio hardware.

## Checkpoints
- [x] perpetua-core repo inspected
- [x] PROGRESS.md confirmed all 16 tasks DONE
- [x] All 6 spec assets verified present in code
- [x] All spec invariants verified (BaseModel, aiosqlite, Python 3.11+, engine ~102 lines)
- [x] Memory updated (DECISIONS.md, AGENT_LEARNINGS.jsonl)
- [ ] User hardware review (Mac + Win) before push to perpetua-core main

## Next step
Ask user whether to initiate hardware review gate or defer.
