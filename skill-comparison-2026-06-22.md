# Hermes-only skills vs orama-system skills — enrichment & absorption map

> Date: 2026-06-22
> Source: Hermes skill listing vs orama-system `.agents/skills/` tree.

## Enriched comparison table

| Hermes Skill | Category | Orama-system Counterpart / Adjacent | Enrichment Recommendation |
|---|---|---|---|
| `pt-orama-council` | autonomous-ai-agents | `openclaw-dream-setup`, `no-sleep-chains`, `openclaw-skills`, `openclaw-status` | Hermes wraps the council workflow; orama manages OpenClaw/AGY lifecycle and status. Low overlap; keep separate. |
| `pt-orama-harness-integration` | autonomous-ai-agents | `hermes-harness`, `ecc-sync`, `no-sleep-chains` | **Absorb into `hermes-harness`** — cross-harness thin-adapter pattern and three-model council orchestration belong in the harness, not a standalone. |
| `hermes-agent` | autonomous-ai-agents | `hermes-harness` | **Absorb into `hermes-harness`** — self-config/setup logic is harness territory; merge to avoid split-brain between the two. |
| `git-worktree-hygiene` | software-development | `using-git-worktrees`, `orama-repo-rules`, `git-history-surgery` | Complementary; hermes skill is lighter, orama has surgery + rewrite awareness. No merge recommended; refer to orama for surgery cases. |
| `hermes-agent-skill-authoring` | software-development | `skillify` | Adjacent only. Hermes skill authors `SKILL.md` for itself; orama owns general skill authoring pipeline. |
| `plan` | software-development | `agent-methodology`, `oramasys-method` | Adjacent. Hermes produces actionable plans; orama owns system-design methodology. Keep separate. |
| `systematic-debugging` | software-development | `orama-afrp` | Adjacent. orama AFRP is deeper failure-mode analysis; Hermes is 4-phase generic debug. Keep separate. |
| `requesting-code-review` | software-development | `code-review` | Adjacent. Hermes pre-commit gate; orama owns review practice. No merge needed. |
| `claude-code` | autonomous-ai-agents | `codex-openclaw-agent` | Adjacent. orama manages OpenClaw lifecycle; Hermes simply invokes Codex. Keep separate. |
| `codex` | autonomous-ai-agents | `codex-openclaw-agent` | Adjacent. Same as above. Keep separate. |
| `local-inference` | mlops | `perpetua-config`, `perpetua-hardware`, `perpetua-startup-intelligence`, `perpetua-tools` | **Absorb into `perpetua-hardware`** — local model selection, canary test pattern, LM Studio/Ollama affinity rules, runtime routing, timeout/model-ID handling. |
| `jupyter-live-kernel` | data-science | — | No orama counterpart. No action. |
| `google-workspace`, `notion`, `airtable`, `powerpoint`, `nano-pdf`, `ocr-and-documents`, `maps`, `himalaya`, `teams-meeting-pipeline` | productivity | — | No orama counterparts. No action. |
| `architecture-diagram`, `excalidraw`, `comfyui`, `manim-video`, `p5js`, `pretext`, `sketch`, `ascii-art`, `songwriting-and-ai-music`, `touchdesigner-mcp` | creative | — | No orama counterparts. No action. |
| `gif-search`, `heartmula`, `songsee`, `youtube-content` | media | — | No orama counterparts. No action. |
| `arxiv`, `blogwatcher`, `llm-wiki`, `polymarket` | research | — | No orama counterparts. No action. |
| `openhue` | smart-home | — | No orama counterparts. No action. |
| — | — | `first-run-setup`, `mcp-install`, `mcp-orchestration`, `self-discovery`, `self-improve`, `shell-hygiene`, `orama-cidf`, `orama-gstack`, `orama-repo-rules`, `oramasys-method` | Unique to orama-system; no Hermes equivalent. No action. |

## Absorption targets

1. **`hermes-harness` ← `hermes-agent` + `pt-orama-harness-integration`**
   - Take: Hermes self-config, setup, and thin-adapter patterns.
   - Drop: standalone `hermes-agent` and standalone `pt-orama-harness-integration` skills.

2. **`perpetua-hardware` ← `local-inference`**
   - Take: hardware-aware model selection, canary test pattern, LM Studio/Ollama affinity rules, runtime routing, timeout/model-ID handling.
   - Drop: standalone `local-inference` skill.

## Decision rationale

- orama-system already owns hardware/runtime concerns through `perpetua-*` skills; `local-inference` is a parallel implementation.
- `pt-orama-harness-integration` and `hermes-agent` both touch the Hermes boundary; splitting them creates ambiguity about where agent lifecycle belongs.
- Retain `pt-orama-council`, `git-worktree-hygiene`, `plan`, `systematic-debugging`, and `requesting-code-review` as separate because they serve user-facing workflows that don't currently belong in orama-system.
