# Mac subagents — where to look (mac-researcher, orchestrator, cursor-agent fanout)

**Parent:** Mac co-orchestrator  
**Harness:** OpenClaw + cursor-agent (local only)  
**Date:** 2026-06-28

## Read order

1. `$PERPETUA_TOOLS_PATH/.agent/memory/working/MAC_CO_ORCHESTRATOR_WHERE_TO_LOOK_2026-06-28.md` — co-orchestrator card
2. `$PERPETUA_TOOLS_PATH/.agent/memory/working/CO_ORCHESTRATOR_LAN_PEER_2026-06-28.md` — affinity + Ollama-warm routing
3. Local inbox: `~/.openclaw/state/lan_peer/inbox/` — assignments with `assignee: mac`
4. `$PERPETUA_TOOLS_PATH/.agent/memory/semantic/LESSONS.md` — search `co-orchestrator`, `lan_peer`, `ollama-mac`

## mac-researcher workflow

```bash
# 1. List Mac-local assignments (no --peer for inbound from fan-out)
python3 "$ORAMA_SYSTEM_PATH/bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py" list
python3 "$ORAMA_SYSTEM_PATH/bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py" read --name mac-hypothesis.md

# 2. Run inference on Ollama (warm) — NOT passive LM Studio
#    Use OpenClaw routing to ollama-mac or cursor-agent locally

# 3. Drop results to Win peer
python3 "$ORAMA_SYSTEM_PATH/bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py" drop --peer \
  --file ./results/hypothesis-summary.md --assignee win --topic autoresearch/hypothesis-done
```

## Topic routing

| Topic prefix | Subagent | Inference |
|--------------|----------|-----------|
| `autoresearch/hypothesis` | mac-researcher | Ollama `:11434` |
| `self-improve/lessons` | orchestrator | cursor-agent + PT memory |
| `code-review/*` | mac-researcher | read peer inbox, reply via `drop --peer` |

## Win peer deliverables to read

After Win drops (check with `list --peer`):

- `gpu-results.md` — H3 benchmark
- `win-code-review.md` — autoresearch_bridge review
- `win-self-improve-runtime-results.md` — runtime lessons

## Do NOT

- Execute on Win over HTTP (file handoff only)
- Warm MLX on passive LM Studio when Ollama is already warm
