# Win co-orchestrator — where to look (READ FIRST)

**Agent:** Win co-orchestrator — **Hermes-only** harness + cursor-agent + Win subagents  
**Platform:** Windows = Hermes (`start.ps1`); OpenClaw optional on Win  
**Date:** 2026-06-28  
**Mode:** file inbox handoff (no remote agent RPC)

## Step 0 — sync orama

```powershell
cd $env:ORAMA_SYSTEM_PATH
git fetch origin --prune
git pull --rebase origin main   # need >= 435d27a (portal / 500 fix)
.\platform\windows\start.ps1 --stop
.\platform\windows\start.ps1 --lan-peer --no-open
python bin\orama-system\skills\hermes-harness\scripts\probe_lan_peer.py --json
```

### Portal `http://localhost:8002/` → Internal Server Error

| Symptom | Cause | Fix |
|---------|-------|-----|
| `/` → 500, `/health` → 200 | Stale portal before `435d27a` | `git pull` orama `main`, `start.ps1 --stop` then `--lan-peer` |
| Root cause | `api_status` redacted `agents` as `{"agents": [...], "count": N}` | `_unwrap_redacted_list()` in `portal_server.py` |

**Verify:** browser or `Invoke-WebRequest http://localhost:8002/` → status 200.

## Primary playbooks (orama-system, tracked)

| Priority | File | Purpose |
|----------|------|---------|
| 1 | `bin/orama-system/skills/hermes-harness/references/mac-co-orchestrator-playbook.md` | **SSOT** — Mac+Win cursor-agent co-orchestration |
| 2 | `bin/orama-system/skills/hermes-harness/references/co-orchestrator-handoff.md` | Win-side summary + reply protocol |
| 3 | `bin/orama-system/skills/hermes-harness/references/lan-peer-self-talk.md` | Operator index, probe pass criteria, section F file inbox |
| 4 | `bin/orama-system/skills/hermes-harness/references/mac-operator-notice.md` | Short Mac notice (mirror for context) |

**GitHub (if no local pull yet):**

- https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/hermes-harness/references/mac-co-orchestrator-playbook.md
- https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/hermes-harness/references/co-orchestrator-handoff.md

## PT memory (this repo)

| File | Purpose |
|------|---------|
| `.agent/memory/working/WIN_CO_ORCHESTRATOR_WHERE_TO_LOOK_2026-06-28.md` | **This card** |
| `.agent/memory/working/CO_ORCHESTRATOR_LAN_PEER_2026-06-28.md` | **Start here** — platform affinity + routing |
| `.agent/memory/working/LAN_PEER_L2_TOKEN_LANDMARK_2026-06-28.md` | Token handoff (no secrets) |
| `.agent/memory/semantic/DOMAIN_KNOWLEDGE.md` | Windows start.ps1 + LAN peer sticky notes |

## Inbox commands (Win)

```powershell
cd $env:ORAMA_SYSTEM_PATH

# Read Mac assignments
python bin\orama-system\skills\hermes-harness\scripts\lan_peer_assign.py list --peer
python bin\orama-system\skills\hermes-harness\scripts\lan_peer_assign.py read --peer --name hypothesis-summary.md
python bin\orama-system\skills\hermes-harness\scripts\lan_peer_assign.py read --peer --name mac-code-review.md

# Reply to Mac
python bin\orama-system\skills\hermes-harness\scripts\lan_peer_assign.py drop --peer `
  --file .\results\gpu-results.md --assignee mac --topic autoresearch/gpu-done `
  --fanout-id 2026-06-28-autoresearch-001
```

**Local inbox path:** openclaw state `lan_peer/inbox/` (Windows: see probe artifact path in lan-peer-self-talk.md)

## Win local agents (same host only)

```powershell
cursor-agent --print --model composer-2.5 --trust "Read inbox assignments; execute Win tasks"
codex exec "Summarize peer inbox and propose next drops"
```

## Do NOT

- SSH to Mac for coordination (HTTP only)
- Stream large payloads over WS (use file drops)
- Commit or paste `ORAMA_CONTROL_PLANE_TOKEN` anywhere tracked
