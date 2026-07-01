# Coordinated cycle 003 — merged landmark (Mac + Win)

**Date:** 2026-06-28  
**Fan-out:** `2026-06-28-coord-003`  
**Status:** Win deliverables complete; Mac branches ready for PR review

## Branch policy

`orama-system/.../references/subagent-branch-policy.md` — `subagent/<role>/<topic>`; coordination on `main` via file inbox.

## Subagent table

| Host | Subagent | Branch | Deliverable | Status |
|------|----------|--------|-------------|--------|
| Mac | mac-researcher | `subagent/mac-researcher/h4-mac-benchmark` | `mac-h4-comparison.md` | Done → Win |
| Mac | orchestrator | `subagent/mac-orchestrator/self-improve-memory` | cycle landmark | Done (this file) |
| Win | autoresearcher | `subagent/win-autoresearcher/h5-gpu-harness` | `gpu-results-h5.md` | Done |
| Win | coder | `subagent/win-coder/bridge-http-local` | `win-bridge-spike-notes.md` | Done |
| Win | orchestrator | `subagent/win-orchestrator/doc-sync-peer-inbox` | portal doc sync | Done |

## Win session outcomes

- H5 GPU: 3/3 rubric prompts on LM Studio 27B (`run_h5_gpu_benchmark.py`)
- Bridge: `AUTORESEARCH_PREFLIGHT_MODE=auto` → http-local on Win GPU host
- Portal: `/peer-inbox` canonical on Win; `/co-orchestration/windows` → 307 redirect
- Graceful degradation: `orama-system/.../oramasys-method/references/graceful-degradation.md`

## Mac pending / review

- PR review: `subagent/mac-researcher/h4-mac-benchmark`, `subagent/mac-orchestrator/self-improve-memory`
- Cross-host H5 comparison after reading `gpu-results-h5.md`
- Operator: **`approve lessons`** for `docs/LESSONS.md` when ready (landmark only until then)

## Frugality priority (coord-004)

1. **Win autoresearcher + coder** → LM Studio `:1234` first  
2. Online agents (cursor-agent cloud, Codex, etc.) → fallback only  
3. Online failure → LAN peer file inbox + local LM Studio / Mac Ollama  
4. Document escalation tier in one line per `graceful-degradation.md`

## Monitor

- Mac: `http://localhost:8002/co-orchestration/macos`
- Win: `http://localhost:8002/peer-inbox`
