# Hermes Skill Absorption Audit — 2026-06-28

> Canonical map: `orama-system/.../hermes-skill-absorption-map.md`

## Audit follow-up (completed)

- ✅ `.agents` thin wrappers: `hermes-agent`, `pt-orama-harness-integration`, `local-inference` → canonical paths
- ✅ `.agents/perpetua-hardware` retargeted to `hardware-affinity-gate` (orama methodology), not PT/hardware folder
- ✅ `archive/llm-council-orchestration-absorbed` marked SUPERSEDED → `pt-orama-council`
- ✅ Win LM Studio coder: `qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2` (replaces invented "Qwen 3.6 Coder")
- ✅ Onboarding plan Phase 2 + success metrics updated
- ✅ `redirect_to` + `status: absorbed` on bin redirect stubs

## Dual-layer hardware (sticky)

| Layer | Path |
|-------|------|
| orama methodology | `hardware-affinity-gate` |
| PT runtime SSoT | `$PERPETUA_TOOLS_PATH/config/model_hardware_policy.yml` |
| Hermes edge | `commands/pt-hardware-policy` |

## Still pending

- Mac↔Win cross-harness E2E
- `hermes-harness` authority parity vs `openclaw-skills` (subjective metric)
