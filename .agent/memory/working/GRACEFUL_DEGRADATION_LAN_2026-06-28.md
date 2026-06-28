# Graceful degradation — LAN co-orchestration (PT memory)

**Canonical:** `../../orama-system/bin/orama-system/skills/oramasys-method/references/graceful-degradation.md`  
**PT skill:** `SKILL.md` (model selection + budget guard)

## Win agent priority (frugal)

```text
1. LM Studio 27B @ :1234 (autoresearcher, coder)
2. Win Ollama validated fallback (routing.yml)
3. LAN peer file inbox (Mac Ollama / orchestrator)
4. Online agents (cursor-agent cloud, Codex) — budget + operator only
```

## Disaster recovery (both directions)

| Failure | Fallback |
|---------|----------|
| Online API down / 429 | LAN LM Studio or Mac Ollama via inbox handoff |
| Win LM Studio down | Mac Ollama + defer GPU tasks; partial fan-out |
| Mac Ollama down | Win 27B absorbs coder leg; drop results to Mac |
| ws-peer FAIL | SSE+POST; file inbox still works |
| SSH preflight timeout | `AUTORESEARCH_PREFLIGHT_MODE=http-local` on Win |

**Rule:** State escalation tier in one line. Stop at first success.

## coord-004

Fan-out `2026-06-28-coord-004` — operationalize ladders on Win autoresearcher + coder first.
