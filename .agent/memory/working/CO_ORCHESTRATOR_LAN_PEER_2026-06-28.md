# Co-orchestrator LAN peer lessons — 2026-06-28

**Status:** graduated to `.agent/memory/semantic/lessons.jsonl` via `learn.py`  
**Human index:** `docs/LESSONS.md` section 2026-06-28 co-orchestrator  
**orama playbook:** `../../orama-system/bin/orama-system/skills/hermes-harness/references/mac-co-orchestrator-playbook.md`

## Platform affinity (memorize)

| Host | Primary harness | Subagents | Co-orchestration executor |
|------|-----------------|-----------|---------------------------|
| **macOS** | **OpenClaw** + AlphaClaw (`start.sh`) | main, mac-researcher, orchestrator + **cursor-agent** | OpenClaw/cursor-agent run **locally** on Mac |
| **Windows** | **Hermes-only** (`start.ps1`; OpenClaw optional) | win-researcher, coder, autoresearcher + **cursor-agent**, Codex, AGY | Hermes/cursor-agent run **locally** on Win |

**Rule:** No remote agent RPC. Mac does not run Hermes dispatch on Win and vice versa. Coordination = **file inbox** (`lan_peer_assign.py`) + git pull on both repos.

Canonical: `../../orama-system/bin/orama-system/skills/hermes-harness/references/platform-affinity-routing.md`

## Mac inference mode (2026-06-28 — operator reported)

| Backend | Mac state | Use for |
|---------|-----------|---------|
| **Ollama** `:11434` | **Active / warm** | Mac co-orchestrator, mac-researcher, cursor-agent inference |
| **LM Studio** `:1234` | **Passive only** | Probe catalog / optional MLX; **not** primary execution path |

**Routing:** Mac subagents run local inference on `ollama-mac` (localhost:11434). Do not warm or dispatch through passive LM Studio unless hardware policy explicitly requires MLX on `:1234`.

**Probe note:** `peer-lmstudio` can still PASS (LMS listening with model list) while Mac active work uses Ollama. `peer-lmstudio` ≠ Mac primary coder.

## Where co-orchestrator + subagents look first

| Role | Harness | Read this | Purpose |
|------|---------|-----------|---------|
| **Mac co-orchestrator** | OpenClaw + cursor-agent | `MAC_CO_ORCHESTRATOR_WHERE_TO_LOOK_2026-06-28.md` | **Start here on Mac** |
| **Mac subagents** | OpenClaw | `MAC_SUBAGENTS_WHERE_TO_LOOK_2026-06-28.md` | mac-researcher, orchestrator |
| **mac-researcher** | OpenClaw | `~/.openclaw/state/lan_peer/inbox/` + `list` (local) | Mac-assigned hypothesis tasks |
| **Win co-orchestrator** | Hermes + cursor-agent | `WIN_CO_ORCHESTRATOR_WHERE_TO_LOOK_2026-06-28.md` | Fan-out replies to Mac |
| **autoresearcher (Win)** | Hermes | `WIN_AUTORESEARCHER_WHERE_TO_LOOK_2026-06-28.md` + Win inbox `list` / `read --name` | Mac→Win inbound (local) |
| **All agents** | either | `.agent/memory/semantic/LESSONS.md` | Rendered lesson brain |
| **All agents** | either | `.agent/memory/semantic/DOMAIN_KNOWLEDGE.md` | LAN peer + co-orchestrator gold |
| **Probe / ops** | either | `LAN_PEER_L2_TOKEN_LANDMARK_2026-06-28.md` | Token handoff (no secrets) |
| **Win deliverables pending** | Hermes | `tasks/gpu-results.md`, `tasks/win-code-review.md`, `tasks/win-self-improve-runtime-results.md` on Win disk | Drop to Mac when Mac peer-file UP |

## GitHub links (pull `main`)

- Playbook: https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/hermes-harness/references/mac-co-orchestrator-playbook.md
- Mac notice: https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/hermes-harness/references/mac-operator-notice.md
- LAN peer SSOT: https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/hermes-harness/references/lan-peer-self-talk.md

## Lesson summary (machine records in lessons.jsonl)

1. **File inbox beats WS** — markdown via `/api/peer-file`; fan-out manifest by `assignee`
2. **Repo root** — `lan_peer_assign` uses `parents[4]` for orama root
3. **Partial fanout** — peer 404 while local succeeds → `status: partial`
4. **Win inbound** — Mac drops arrive local; `read --name` without `--peer`
5. **Win outbound** — `drop --peer` to Mac; Mac uses `read --peer`
6. **autoresearch_bridge** — SSH GPU_BOX path vs LAN HTTP + file handoff
7. **Mac unblock** — pull `>= 9f89051`, `./start.sh --lan-peer` for peer-file
8. **Joint auth** — PT `.state` token + orama env lanes → `auth_mode: joint`
9. **Mac inference** — Ollama warm (`:11434`) primary; LM Studio passive (`:1234`)

## Mac commands (OpenClaw co-orchestrator + subagents)

```bash
export ORAMA_SYSTEM_PATH="$(git -C "$(dirname "$0")/../../.." rev-parse --show-toplevel 2>/dev/null || git rev-parse --show-toplevel)"
export PERPETUA_TOOLS_PATH="$(git -C "$ORAMA_SYSTEM_PATH/../perplexity-api/Perpetua-Tools" rev-parse --show-toplevel 2>/dev/null)"

git -C "$PERPETUA_TOOLS_PATH" pull --rebase origin main
git -C "$ORAMA_SYSTEM_PATH" pull --rebase origin main
"$ORAMA_SYSTEM_PATH/start.sh" --stop && "$ORAMA_SYSTEM_PATH/start.sh" --lan-peer --no-open

cat "$PERPETUA_TOOLS_PATH/.agent/memory/working/CO_ORCHESTRATOR_LAN_PEER_2026-06-28.md"

python3 "$ORAMA_SYSTEM_PATH/bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py" list
python3 "$ORAMA_SYSTEM_PATH/bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py" list --peer
python3 "$ORAMA_SYSTEM_PATH/bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py" read --peer --name gpu-results.md

# cursor-agent on Mac task (OpenClaw stack already running)
cursor-agent --print --model composer-2.5 --trust \
  "Read PT .agent/memory/working/CO_ORCHESTRATOR_LAN_PEER_2026-06-28.md and local inbox; execute Mac-side work."
```

**Mac peer-file is live** when `POST /api/peer-file` returns 200 after `--lan-peer` restart. Win can then drop pending deliverables.

## Win deliverables to drop (when Mac peer-file UP)

```powershell
python bin\orama-system\skills\hermes-harness\scripts\lan_peer_assign.py drop --peer --file tasks\gpu-results.md --assignee mac --topic autoresearch/results
python bin\orama-system\skills\hermes-harness\scripts\lan_peer_assign.py drop --peer --file tasks\win-code-review.md --assignee mac --topic code-review/autoresearch-bridge-done
python bin\orama-system\skills\hermes-harness\scripts\lan_peer_assign.py drop --peer --file tasks\win-self-improve-runtime-results.md --assignee mac --topic self-improve/review
```

## Self-improve merge

Drafts: `mac-lessons-draft.md` (inbox) + Win runtime results — merged into PT `.agent` via this session. `docs/LESSONS.md` human section updated; orama `docs/LESSONS.md` not touched unless operator requests.
