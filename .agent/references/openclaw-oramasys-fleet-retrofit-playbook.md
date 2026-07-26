# OpenClaw ↔ Oramasys Fleet Retrofit Playbook (MERGE-10)

> **Audience:** All future agents (OpenClaw, Cursor, Claude Code, PT host-agent).  
> **Session:** 2026-07-23 – 2026-07-26 (Raft plans → live retrofit outside git).  
> **Status:** Executed in operator OpenClaw state; **orama-system / Perpetua-Tools promotion pending M3 dry-run.**

## What we did (3-day arc)

1. **Research & dedup** — EXA/Firecrawl on SOUL/VISION taxonomy; merged Raft outputs (03→06, combined-05, grounded-06).
2. **PLAN-08** — 23-soul repo scaffold plan (orama `bin/agents/`, `.claude/agents/orama-*`) — **plan-only, not executed in git**.
3. **PLAN-09** — Proposed `~/.openclaw/fleet/` hub — **rejected** in favor of retrofit.
4. **MERGE-10** — Retrofit live OpenClaw workspaces: integrative merge, no parallel fleet tree.
5. **EDITED-03 fold** — Raft personas (Cole, Hermes, Sage, Penn, Arthur, Nova, Rex) harmonized with pipeline agents.
6. **CROSSREF spine** — Anti-loss navigation across plans, hub, and 17 live `openclaw.json` agents.

## Core doctrine (never skip)

| Rule | Why |
|------|-----|
| **Retrofit, don't rebuild** | Atlas = `main` at `${ALPHACLAW_INSTALL_DIR}/.openclaw/workspace`; hub at `docs/oramasys/`, not `~/.openclaw/fleet/` |
| **Integrative merge** | Append `## Oramasys role overlay` to SOUL; preserve OpenClaw Core Truths + oramaclaw `generated` blocks |
| **Vera reviews all code** | `codex-agent` = stage 4.5 invariant on every code path; Sage = optional analyzer only |
| **OpenClaw id is runtime SSOT** | orama `agent_registry.json` ids may differ (`executor-agent` vs `coder`) |
| **AFRP before guessing** | Persona bindings (Cole/Penn/Vera/Sage) required AskUserQuestion — see MERGE-10 § EDITED-03 fold |
| **Promotion gate** | M3 dry-run must pass before copying patterns into orama `bin/agents/` (PLAN-08) |

## Live fleet (17 agents)

**Navigation spine:** `${ALPHACLAW_INSTALL_DIR}/.openclaw/workspace/docs/oramasys/CROSSREF.md`

| Group | openclaw_id | Display |
|-------|-------------|---------|
| Lifecycle | `main` | Atlas (+ Cole-facing home norms) |
| Router | `orchestrator` | Glen |
| Pipeline S1–S5 | `context-agent`, `architect-agent`, `refiner-agent`, `coder`, `codex-agent`, `crystallizer-agent` | Cass, Aria, Sena, Rourke, Vera, Crystal |
| Research | `mac-researcher`, `win-researcher`, `autoresearcher` | Arthur, Win Researcher, Scout |
| Specialist | `gemini-coder` | Sage (analyzer only) |
| Adapter | `cline-agent` | Relay |
| Relay parity | `cole-agent`, `hermes-agent`, `kimi-agent`, `grok-agent` | Cole, Hermes, Nova, Rex |

**Penn alias:** automation persona on `coder` workspace (same runtime as Rourke).

## File taxonomy (org vs agent vs task)

| File | Scope | Location |
|------|-------|----------|
| `VISION.md` | Organization | Hub symlink → `orama-system/VISION.md` |
| `REGISTRY.yml` | Fleet machine map | `main/docs/oramasys/` |
| `CROSSREF.md` | Human navigation | `main/docs/oramasys/` |
| `GOALS.md` | Agent standing ownership | Per-agent workspace root |
| `MEMORY.md` | Agent compounding log | Per-agent workspace root |
| `GOAL.md` | Single task | `main/docs/oramasys/tasks/<trace_id>/` |

## How we executed MERGE-10 (repeatable steps)

### Phase M0 — Hub (Atlas workspace)

```bash
HUB="${ALPHACLAW_INSTALL_DIR}/.openclaw/workspace/docs/oramasys"
mkdir -p "$HUB/tasks" "$HUB/personas"
ln -sf "$ORAMA_SYSTEM_ROOT/VISION.md" "$HUB/VISION.md"   # or OpenClaw/orama-system path
# Create REGISTRY.yml, REVIEWER_PROMPT.md, DRY-RUN.md, SCHEDULES.md, CROSSREF.md
```

### Phase M1 — Retrofit existing agents

Per workspace: IDENTITY, GOALS, MEMORY, SECURITY (if missing), `memory/`, append SOUL overlay, insert Oramasys session contract + Fleet navigation in AGENTS.md.

### Phase M2 — Create missing pipeline agents

```bash
for id in context-agent architect-agent refiner-agent crystallizer-agent; do
  openclaw agents add "$id" \
    --model "ollama/qwen3.5:9b-nvfp4" \
    --workspace "$HOME/.openclaw/agents/$id" \
    --non-interactive --json
done
```

### Phase M2b — Relay parity agents (EDITED-03)

```bash
for id in cole-agent hermes-agent kimi-agent grok-agent; do
  openclaw agents add "$id" \
    --model "openrouter/free" \
    --workspace "$HOME/.openclaw/agents/$id" \
    --non-interactive --json
done
```

### Orchestrator delegation

**Do:** `openclaw config set 'agents.list[<orchestrator-index>].subagents' '{"allowAgents":[...]}' --strict-json --merge`

**Don't:** `openclaw config patch` on full `agents.list` — refuses to replace array.

Verify index: `openclaw config get agents.list | jq 'to_entries[] | select(.value.id=="orchestrator") | .key'`

### Phase M3 — Dry-run

Probes in `docs/oramasys/DRY-RUN.md`. Pass criteria: each agent cites VISION, own GOALS, correct reviewer.

## How to promote into orama-system (PLAN-08, future)

Only after M3 passes:

1. Copy proven GOALS/SOUL/AGENTS patterns → `orama-system/bin/agents/<stage>/` (integrative merge, never amputate).
2. Generate `docs/agent-souls/` from hub `REGISTRY.yml`.
3. Sync `.claude/agents/orama-*.md` from validated OpenClaw text.
4. Update `agent_registry.json` only where OpenClaw binding is stable.
5. PT `.agent` lessons (this playbook + graduated lessons) inform promotion — do not duplicate fleet hub in PT orchestrator.

**Boundary:** OpenClaw retrofit = operator local state. orama/PT git = canonical specs after validation.

## Plan document lineage

```text
raft-Output-03/EDITED-03 → personas + heartbeats
raft-Output-combined-05 / grounded-06 → reviewer graph, Relay model
raft-orama-PLAN-08 → repo scaffold (23 souls)
raft-openclaw-PLAN-09 → fleet hub (DEPRECATED path)
raft-openclaw-MERGE-PLAN-10 → executable retrofit + EDITED-03 fold
references/AGENT-CROSSREF.md → plan-side index → live CROSSREF.md
```

## Lessons learned (highlights)

1. **Main workspace path** — Not `~/.openclaw/workspace`; operator uses `${ALPHACLAW_INSTALL_DIR}/.openclaw/workspace` for `main`.
2. **No parallel fleet/** — Central metadata in main workspace `docs/oramasys/` avoids duplicate infrastructure.
3. **gemini-coder CORRECTION history** — Never delete Antigravity audit trail; Sage demoted to optional analyzer.
4. **codex-agent dual role** — Vera (pipeline 4.5) on same id as Codex model; Penn persona lives on `coder`.
5. **Scale one pillar** — Glen + Cass + one Relay agent before full adapter catalog (EDITED-03 caution).
6. **MEMORY compounding** — Append learnings after each task; judgment in MEMORY becomes compounding soul.
7. **Cross-ref propagation** — New agent = update REGISTRY + CROSSREF + allowAgents + AGENTS.md Fleet navigation.

## Related PT / orama artifacts

- PT: `.agent/references/openclaw-oramasys-fleet-retrofit-playbook.md` (this file)
- PT: `.agent/memory/working/OPENCLAW_MERGE10_FLEET_RETROFIT_2026-07-26.md`
- PT: `.agent/memory/working/2026-07-26-merge10-memory-pipeline-proof.md` (AGENTS.md compliance proof)
- OpenClaw: `references/raft-openclaw-MERGE-PLAN-10.md`
- OpenClaw: `references/AGENT-CROSSREF.md`
- orama: `VISION.md`, `bin/orama-system/config/agent_registry.json`
- Skill: `openclaw-new-agent`, `oramasys-method` integrative merge

## How to add lessons to PT memory (AGENTS.md contract)

Future agents capturing retrofit or promotion work **must** use the pipeline — not hand-edit `LESSONS.md`.

```bash
cd Perpetua-Tools

# 1. Recall before acting
python3 .agent/tools/recall.py "openclaw fleet merge-10"

# 2. One-shot graduate (creates episodic mirror + graduated/ audit + lessons.jsonl row)
python3 .agent/tools/learn.py "<specific claim>" --rationale "<incident + why>"

# 3. Log significant session outcome
python3 .agent/tools/memory_reflect.py <skill> <action> <outcome> \
  --importance 8 --note "<context>" \
  --evidence <episodic-timestamp-or-lesson_id>

# 4. Update WORKSPACE.md; add DECISIONS.md entry if architectural
# 5. Verify: python3 .agent/tools/show.py
# 6. Commit .agent/** on a branch; merge via PR (main push blocked by Phase 0 hook)
```

**Proof chain:** each `learn.py` lesson has `evidence_ids` → episodic `manual-stage:<id>` row → `graduated/<id>.json` with `decisions[]`.
