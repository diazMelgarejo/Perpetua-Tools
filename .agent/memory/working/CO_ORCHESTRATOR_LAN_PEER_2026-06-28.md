# Co-orchestrator LAN peer lessons — 2026-06-28

**Status:** graduated to `.agent/memory/semantic/lessons.jsonl` via `learn.py`  
**Human index:** `docs/LESSONS.md` §2026-06-28 co-orchestrator  
**orama playbook:** `orama-system/.../references/mac-co-orchestrator-playbook.md`

## Where Mac co-orchestrator + subagents look first

| Role | Read this | Purpose |
|------|-----------|---------|
| **Mac co-orchestrator** (Hermes / cursor-agent) | This file + `mac-co-orchestrator-playbook.md` | Fan-out, peer read/write |
| **mac-researcher** | `~/.openclaw/state/lan_peer/inbox/` + `list` (local) | Mac-assigned hypothesis tasks |
| **autoresearcher (Win)** | Win inbox `list` / `read --name` (no `--peer` inbound) | Mac→Win assignments |
| **All agents** | `PT/.agent/memory/semantic/LESSONS.md` | Rendered lesson brain |
| **All agents** | `PT/.agent/memory/semantic/DOMAIN_KNOWLEDGE.md` | LAN peer + co-orchestrator gold |
| **Probe / ops** | `PT/.agent/memory/working/LAN_PEER_L2_TOKEN_LANDMARK_2026-06-28.md` | Token handoff (no secrets) |
| **Win deliverables pending** | `orama-system/tasks/gpu-results.md`, `win-code-review.md`, `win-self-improve-runtime-results.md` | Drop to Mac when peer-file live |

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

## Mac commands (subagents)

```bash
export ORAMA_SYSTEM_PATH="$(git -C ~/path/to/orama-system rev-parse --show-toplevel)"
export PERPETUA_TOOLS_PATH="$(git -C ~/path/to/Perpetua-Tools rev-parse --show-toplevel)"

# Memory
cat "$PERPETUA_TOOLS_PATH/.agent/memory/working/CO_ORCHESTRATOR_LAN_PEER_2026-06-28.md"
cat "$PERPETUA_TOOLS_PATH/.agent/memory/semantic/LESSONS.md" | tail -40

# Co-orchestration
python3 "$ORAMA_SYSTEM_PATH/bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py" list --peer
python3 "$ORAMA_SYSTEM_PATH/bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py" read --peer --name gpu-results.md

# cursor-agent on Mac task
cursor-agent --print --model composer-2.5 --trust \
  "Read PT .agent/memory/working/CO_ORCHESTRATOR_LAN_PEER_2026-06-28.md and inbox assignments; execute Mac-side work."
```

## Win deliverables to drop (when Mac peer-file UP)

```powershell
python bin\orama-system\skills\hermes-harness\scripts\lan_peer_assign.py drop --peer --file tasks\gpu-results.md --assignee mac --topic autoresearch/results
python bin\orama-system\skills\hermes-harness\scripts\lan_peer_assign.py drop --peer --file tasks\win-code-review.md --assignee mac --topic code-review/autoresearch-bridge-done
python bin\orama-system\skills\hermes-harness\scripts\lan_peer_assign.py drop --peer --file tasks\win-self-improve-runtime-results.md --assignee mac --topic self-improve/review
```

## Self-improve merge

Drafts: `mac-lessons-draft.md` (inbox) + Win runtime results — merged into PT `.agent` via this session. `docs/LESSONS.md` human section updated; orama `docs/LESSONS.md` not touched unless operator requests.
