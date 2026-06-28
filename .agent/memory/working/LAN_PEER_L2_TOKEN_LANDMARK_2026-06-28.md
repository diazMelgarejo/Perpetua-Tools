# LAN peer L2 token handoff landmark — 2026-06-28

**Status:** landmark recorded · **Secrets:** never store token values in this tree  
**SSOT:** `orama-system/.../references/lan-peer-self-talk.md` § Operator playbook  
**Bidirectional plan:** `orama-system/docs/guides/lan-peer-bidirectional-talk-2026-06-28.md`

## What happened (no secrets)

| Milestone | Detail |
|-----------|--------|
| **L1 inference** | Mac↔Win LM Studio `:1234` — **bidirectional PASS** |
| **L2 portal-health** | Win `:8002` LAN reachable after `start.ps1 --lan-peer` |
| **L2 portal-status** | Was **401** until cross-host token sync via handoff scripts |
| **Token handoff** | Win `scripts/env/print-lan-peer-token.ps1` → Mac `orama-system/.env.local` |
| **Mac mirror** | `scripts/env/print-lan-peer-token.sh` for Mac→Win paste |
| **Artifact on full PASS** | `~/.openclaw/state/last_lan_peer_probe.json` (local only) |

## Operator rule (memorize)

1. **One shared** `ORAMA_CONTROL_PLANE_TOKEN` on **both** hosts — same string in each `orama-system/.env.local`.
2. **Never commit** the token or paste it into tracked files, chat logs, or `.agent/memory`.
3. **Direction:** whoever generated the token first runs the print script; peer pastes into `.env.local`.
4. **Stale IP:** use `last_discovery.json` — Mac is `.102`, Win is `.100` (not legacy `.110`).

## P2P next (L3 transport — in development)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| P1 | Portal WS + SSE + POST endpoints | 🚧 in progress |
| P2 | `lan_peer_channel.py` state machine | 🚧 in progress |
| P3 | Lifespan auto-connect to peer | planned |
| P4 | `probe_lan_peer.py` `ws-peer` check | planned |
| P5 | Cross-peer `user-input` dispatch | deferred |

**Transport:** FastAPI WebSocket primary, SSE+POST fallback, zero new deps.

## Commands (no token output)

```bash
# Mac
./start.sh --lan-peer --no-open
bash scripts/env/print-lan-peer-token.sh    # Mac → Win handoff
python3 bin/orama-system/skills/hermes-harness/scripts/probe_lan_peer.py --json
```

```powershell
# Win
.\platform\windows\start.ps1 --lan-peer --no-open
.\scripts\env\print-lan-peer-token.ps1      # Win → Mac handoff
python bin\orama-system\skills\hermes-harness\scripts\probe_lan_peer.py --json
```
