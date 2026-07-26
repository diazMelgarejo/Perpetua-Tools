# MERGE-10 memory pipeline proof (AGENTS.md compliance)

**Date:** 2026-07-26  
**Branch:** `docs/agent-merge10-fleet-retrofit-lessons`  
**Commit:** `f418add9` (agent memory only)

This document proves the PT `.agent` memory pipeline was used correctly per `AGENTS.md` — not hand-edited `LESSONS.md`.

## Required workflow (from AGENTS.md)

| Step | Tool | Required? | Done? |
|------|------|-----------|-------|
| Graduate lessons | `learn.py` (stage + graduate + render) | Yes — never hand-edit LESSONS.md | ✓ 7 lessons |
| Episodic mirror per lesson | `learn.py` → `_append_episodic_mirror` | Yes — evidence_ids resolve | ✓ 7 mirrors |
| Audit trail | `memory/candidates/graduated/<id>.json` | Yes — permanent | ✓ 7 files |
| Session episodic log | `memory_reflect.py` | Rule 3 — significant actions | ✓ merge-10-complete |
| Architectural decision | `DECISIONS.md` | When costly to re-debate | ✓ 2026-07-26 entry |
| Working state | `WORKSPACE.md` | Rule 4 | ✓ this session |
| Path hygiene | `path_hygiene.py` via learn.py | Always | ✓ env anchors only |

## Evidence chain (lesson → episodic → graduated)

Each `learn.py` call creates:

1. Episodic row in `AGENT_LEARNINGS.jsonl` (`manual-stage:<candidate_id>`)
2. Candidate staged then graduated with `evidence_ids: [<same timestamp>]`
3. Row in `lessons.jsonl` with matching `evidence_ids`
4. Permanent `graduated/<id>.json` with `decisions[]` audit

| lesson_id | candidate_id | episodic evidence timestamp |
|-----------|--------------|----------------------------|
| `lesson_ef2bd9372c3a` | `ef2bd9372c3a` | `2026-07-26T01:00:14.174796+00:00` |
| `lesson_0dfa24ea223b` | `0dfa24ea223b` | `2026-07-26T01:00:14.583664+00:00` |
| `lesson_8d5d1f5540ee` | `8d5d1f5540ee` | `2026-07-26T01:00:14.953848+00:00` |
| `lesson_a8b9334fb8d3` | `a8b9334fb8d3` | `2026-07-26T01:00:15.271...` (see jsonl) |
| `lesson_d7d098444586` | `d7d098444586` | `2026-07-26T01:00:15.631857+00:00` |
| `lesson_b1749d2e8081` | `b1749d2e8081` | `2026-07-26T01:00:15.962883+00:00` |
| `lesson_74e4ea5c91b2` | `74e4ea5c91b2` | `2026-07-26T01:00:16.310448+00:00` |

Session summary episodic: `2026-07-26T01:00:21.944608+00:00` (`openclaw-fleet-retrofit` / `merge-10-complete`)

## Verification commands (re-run anytime)

```bash
cd Perpetua-Tools

# Surface lessons for future agents
python3 .agent/tools/recall.py "openclaw fleet merge-10"

# Brain dashboard (episodes, accepted lesson count, graduated candidates)
python3 .agent/tools/show.py

# Spot-check one graduated audit trail
python3 -c "import json; print(json.dumps(json.load(open('.agent/memory/candidates/graduated/ef2bd9372c3a.json')), indent=2)[:800])"

# Confirm lesson row has evidence_ids
rg 'lesson_ef2bd9372c3a' .agent/memory/semantic/lessons.jsonl
```

## recall.py output (2026-07-26 verify)

```
Consulted lessons for intent: 'openclaw fleet merge-10'
  → returned 3 (top: lesson_ef2bd9372c3a MERGE-10 retrofit, lesson_d7d098444586 CROSSREF propagation)
```

## What we did NOT do (intentionally)

- Did not hand-edit `LESSONS.md` (rendered artifact only)
- Did not skip `graduated/` JSON audit files
- Did not push directly to `main` (pre-push hook Phase 0 — PR required)

## How future agents should add more lessons from this work

```bash
# One-shot when you already know the rule:
python3 .agent/tools/learn.py "<claim>" --rationale "<why with incident reference>"

# Significant session event:
python3 .agent/tools/memory_reflect.py <skill> <action> <outcome> \
  --importance 8 --note "<context>" \
  --evidence 2026-07-26T01:00:14.174796+00:00 lesson_ef2bd9372c3a

# Before OpenClaw fleet work:
python3 .agent/tools/recall.py "openclaw fleet merge-10"
```
