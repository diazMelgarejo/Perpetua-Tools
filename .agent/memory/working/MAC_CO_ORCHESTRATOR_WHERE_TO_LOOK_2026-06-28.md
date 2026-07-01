# Mac co-orchestrator — where to look (READ FIRST)

**Agent:** Mac co-orchestrator — **OpenClaw** + AlphaClaw + **cursor-agent**  
**Platform:** macOS = OpenClaw (`start.sh`); Hermes is Win-only  
**Date:** 2026-06-28  
**Mode:** file inbox handoff (no remote agent RPC)

## Step 0 — sync both repos

```bash
export ORAMA_SYSTEM_PATH="$(git -C ~/path/to/orama-system rev-parse --show-toplevel)"
export PERPETUA_TOOLS_PATH="$(git -C ~/path/to/Perpetua-Tools rev-parse --show-toplevel)"

git -C "$PERPETUA_TOOLS_PATH" fetch origin --prune && git -C "$PERPETUA_TOOLS_PATH" pull --rebase origin main
git -C "$ORAMA_SYSTEM_PATH" fetch origin --prune && git -C "$ORAMA_SYSTEM_PATH" pull --rebase origin main
"$ORAMA_SYSTEM_PATH/start.sh" --stop && "$ORAMA_SYSTEM_PATH/start.sh" --lan-peer --no-open
python3 "$ORAMA_SYSTEM_PATH/bin/orama-system/skills/hermes-harness/scripts/probe_lan_peer.py" --json
```

## PT memory — read first (canonical brain)

| Priority | File | Purpose |
|----------|------|---------|
| 1 | `$PERPETUA_TOOLS_PATH/.agent/memory/working/MAC_CO_ORCHESTRATOR_WHERE_TO_LOOK_2026-06-28.md` | **This card** |
| 2 | `$PERPETUA_TOOLS_PATH/.agent/memory/working/CO_ORCHESTRATOR_LAN_PEER_2026-06-28.md` | Platform affinity + Mac Ollama-warm / LMS-passive |
| 3 | `$PERPETUA_TOOLS_PATH/.agent/memory/semantic/LESSONS.md` | Rendered lessons (`lesson_87636d658879` … `lesson_49a5af119f6f`) |
| 4 | `$PERPETUA_TOOLS_PATH/.agent/memory/semantic/DOMAIN_KNOWLEDGE.md` | Co-orchestrator gold nuggets |
| 5 | `$PERPETUA_TOOLS_PATH/docs/LESSONS.md` | Human index §2026-06-28 co-orchestrator |

## orama playbooks (tracked)

| Priority | File | Purpose |
|----------|------|---------|
| 1 | `bin/orama-system/skills/hermes-harness/references/mac-co-orchestrator-playbook.md` | **SSOT** — fan-out, cursor-agent, inbox |
| 2 | `bin/orama-system/skills/hermes-harness/references/lan-peer-self-talk.md` | Operator index §F |
| 3 | `bin/orama-system/skills/hermes-harness/references/mac-operator-notice.md` | Short notice |

**GitHub:** https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/hermes-harness/references/mac-co-orchestrator-playbook.md

## Mac inference (operator 2026-06-28)

| Backend | State | Use |
|---------|-------|-----|
| **Ollama** `:11434` | **Warm** | Primary — `ollama-mac` for cursor-agent / mac-researcher |
| **LM Studio** `:1234` | **Passive** | Probe catalog only; not primary coder |

## Inbox commands (Mac)

```bash
cd "$ORAMA_SYSTEM_PATH"

# List local + Win peer inbox
python3 bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py list
python3 bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py list --peer

# Read Win deliverables (after Win drops)
python3 bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py read --peer --name gpu-results.md
python3 bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py read --peer --name win-code-review.md

# Fan-out new work
python3 bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py fanout \
  --manifest bin/orama-system/skills/hermes-harness/references/autoresearch-fanout-example.json

# Reply to Win
python3 bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py drop --peer \
  --file ./results/hypothesis-summary.md --assignee win --topic autoresearch/hypothesis-done
```

**Local inbox:** `~/.openclaw/state/lan_peer/inbox/`

## Portal monitor (bidirectional queue UI)

| URL | Purpose |
|-----|---------|
| `http://localhost:8002/co-orchestration/macos` | **Live queue** — OpenClaw skin, local + peer inbox, markdown preview |
| `http://localhost:8002/co-orchestration` | Auto skin (macOS on Mac) |
| `http://localhost:8002/` | Service health + navbar links |

Auto-refreshes every 10s. On Win use `http://localhost:8002/co-orchestration` after `git pull` + `start.ps1 --lan-peer`.

## Mac local agents (same host only)

```bash
cursor-agent --print --model composer-2.5 --trust \
  "Read PT .agent/memory/working/MAC_CO_ORCHESTRATOR_WHERE_TO_LOOK_2026-06-28.md and local inbox; execute Mac tasks via Ollama."
```

## Subagents

Point **mac-researcher** and other Mac subagents at:  
`$PERPETUA_TOOLS_PATH/.agent/memory/working/MAC_SUBAGENTS_WHERE_TO_LOOK_2026-06-28.md`

## Do NOT

- Run Hermes on Mac for co-orchestration (Win-only harness)
- Use passive LM Studio `:1234` as primary inference when Ollama is warm
- Stream large payloads over WS (use file drops)
- Commit or paste control-plane tokens in tracked files
