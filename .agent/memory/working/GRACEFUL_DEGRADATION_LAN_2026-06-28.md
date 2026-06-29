# Graceful degradation — LAN co-orchestration (PT pointer)

**SSOT:** `orama-system/bin/orama-system/skills/oramasys-method/references/graceful-degradation.md`  
**PT inference:** `SKILL.md` (perpetua-model-selection — tiers 0–6, budget guard)

Do not duplicate ladder prose here. Use pointers + one-line tier when escalating.

## Ladder map (v1.1)

| Ladder | Scope | PT / oramasys |
|--------|-------|----------------|
| A | Search | oramasys-method — gbrain → CRG → Grep → web |
| B | Inference | perpetua-model-selection — Tier 0–2 local-first |
| B4 | Autoresearch preflight | `AUTORESEARCH_PREFLIGHT_MODE=auto` → http-local |
| C | LAN inbox | `lan_peer_assign.py`; partial fan-out OK |
| D | Portal | joint auth; peer mirror on fetch fail |
| E | Subagents | Task → inline parent → peer drop |
| F | Dispatch gate | model-routing-check + hardware_policy fail-closed |

## Win priority (B1)

```text
LM Studio 27B :1234 → Win Ollama → LAN peer inbox → cloud (budget only)
```

## Bidirectional DR

| Failure | Fallback |
|---------|----------|
| Cloud / API | LAN LM Studio or Mac Ollama via inbox |
| Win GPU down | Mac Ollama; defer GPU rubrics |
| Mac Ollama down | Win 27B absorbs coder leg |
| ws-peer FAIL | SSE+POST; inbox still works |
| Mac peer timeout | Win continues local queue; retry drop when probe green (Ladder C+F) |
| SSH preflight on Win host | http-local (B4) |

**Rule:** Stop at first success. State tier in one line.

## coord-005 closed

H5 routing: autoresearch-coder → Win 27B; Mac 9B latency probes. Bridge PR ready (38/38).
