# Coordinated cycle 003 — landmark

**Date:** 2026-06-28  
**Status:** ACTIVE — Mac+Win subagents working in parallel  
**Fan-out:** `2026-06-28-coord-003`

## Branch policy

See `orama-system/.../references/subagent-branch-policy.md`:

- Naming: `subagent/<role>/<short-topic>`
- Branch from latest `origin/main`; one branch per subagent task
- Coordination stays on `main` via file inbox — branches are for **mutations only**
- Operator merges via PR after cycle; no `docs/LESSONS.md` without **`approve lessons`**

## Subagent table

| Host | Subagent | Branch | Deliverable |
|------|----------|--------|-------------|
| Mac | mac-researcher | `subagent/mac-researcher/h4-mac-benchmark` | `mac-h4-comparison.md` |
| Mac | orchestrator | `subagent/mac-orchestrator/self-improve-memory` | `mac-self-improve-cycle-003.md` |
| Win | autoresearcher | `subagent/win-autoresearcher/h5-gpu-harness` | `gpu-results-h5.md` |
| Win | coder | `subagent/win-coder/bridge-http-local` | `win-bridge-spike-notes.md` |

## Inbox read (cycle 003)

| File | Source | Notes |
|------|--------|-------|
| `win-self-improve-runtime-results.md` | Win drop | Runtime verified; Win inbox = autoresearcher queue |
| `self-improve-merge-final-proposed.md` | Mac inbox | PROPOSED — operator gate for `docs/LESSONS.md` |
| `mac-win-portal-merge-notes.md` | orama `references/results/` | Portal merge strategy (Mac skins + Win peer-inbox lane) |

## Self-improve gate

**Status:** PROPOSED — landmark in PT `.agent/memory/working/` only; no `docs/LESSONS.md` commit

## Mac orchestrator (this branch)

- **Branch:** `subagent/mac-orchestrator/self-improve-memory`
- **Landmark:** this file
- **Summary drop:** `mac-self-improve-cycle-003.md` → Win peer

## Win waiting on

- autoresearcher: H5 GPU harness → drop `gpu-results-h5.md`
- coder: bridge HTTP spike → drop `win-bridge-spike-notes.md`

## Monitor

http://localhost:8002/co-orchestration/macos
