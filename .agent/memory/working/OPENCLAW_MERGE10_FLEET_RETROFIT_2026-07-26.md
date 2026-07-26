# Session highlights: OpenClaw MERGE-10 fleet retrofit (2026-07-26)

## Scope

Materialize Raft/Oramasys multi-agent design in **live OpenClaw workspaces** outside git — not in `orama-system` or `Perpetua-Tools` repos until dry-run passes.

## Deliverables (operator local)

| Artifact | Path (env-relative) |
|----------|---------------------|
| Master map | `${ALPHACLAW_INSTALL_DIR}/.openclaw/workspace/docs/oramasys/CROSSREF.md` |
| Registry | `.../docs/oramasys/REGISTRY.yml` (17 agents) |
| Personas | `.../docs/oramasys/personas/*.yaml` (EDITED-03) |
| Plans | `OpenClaw/references/raft-openclaw-MERGE-PLAN-10.md` |
| Plan index | `OpenClaw/references/AGENT-CROSSREF.md` |

## Key decisions (AFRP-gated)

- Atlas = `main`; no `~/.openclaw/fleet/` hub.
- Vera (`codex-agent`) reviews **all** code paths; Sage optional only.
- Hermes display name (not June).
- Cole: Atlas home norms + separate `cole-agent` Relay parity workspace.
- Penn alias on `coder` (Rourke runtime).

## Agents created via CLI

Pipeline: `context-agent`, `architect-agent`, `refiner-agent`, `crystallizer-agent`  
Relay parity: `cole-agent`, `hermes-agent`, `kimi-agent`, `grok-agent`

## Config lesson

`openclaw config set 'agents.list[N].subagents' ... --strict-json --merge` — not `config patch` on `agents.list`.

## Next gate

M3 dry-run probes in `DRY-RUN.md` → then PLAN-08 promotion into orama git.

## PT memory

- Playbook: `.agent/references/openclaw-oramasys-fleet-retrofit-playbook.md`
- **Pipeline proof:** `.agent/memory/working/2026-07-26-merge10-memory-pipeline-proof.md`
- Graduated lessons: `recall.py "openclaw fleet merge-10"` → 7 lessons in `lessons.jsonl` (ids `lesson_ef2bd9372c3a` … `lesson_74e4ea5c91b2`)
- Episodic: `AGENT_LEARNINGS.jsonl` timestamps 2026-07-26T01:00:14–01:00:21 UTC
- Branch: `docs/agent-merge10-fleet-retrofit-lessons` (PR to main — direct push blocked by Phase 0 hook)
