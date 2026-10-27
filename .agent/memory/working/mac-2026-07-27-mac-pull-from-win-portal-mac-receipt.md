# Mac receipt — coord-033 Win portal pull (2026-10-27)

**Fan-out:** coord-033  
**Job:** `win-2026-07-27-mac-pull-from-win-portal.md`  
**Actor:** mac-orchestrator-queue (Cursor)  
**Tier:** 0 (probe + inbox verify; no code mutations)

## Pull attempt

| Step | Result |
|------|--------|
| `probe_lan_peer.py --json` | **fail** — `portal-health` timeout on peer portal `:8002` (see `last_discovery.json`); `portal-status` **SECURITY_STOP** (no bearer over plain `http://`); LM Studio **pass** |
| `curl` health peer LAN host (discovery JSON) | **timeout** (3s) |
| `lan_peer_assign.py read --peer` (env-local ask) | **SECURITY_STOP** then connect timeout |
| Mac Keychain `ORAMA_CONTROL_PLANE_TOKEN` | **not set** (operator must load token for tunneled/TLS pull) |

## Priority cards (job §3)

All three targets are already on **Mac local inbox** (prior handoff / drop — pull not required to unblock orchestrator):

- `win-2026-07-27-env-local-policy-ask.md` — **coord-032 completed** (`mac-2026-07-27-env-local-policy-reply.md` in Mac outbox)
- `mac-2026-07-24-h6-dispatch-bookkeeping-landed.md` — present (informational)
- `win-2026-07-23-monitors-paused.md` — present (informational)

## Operator unblock (live portal pull)

1. On Win: `start.ps1 --lan-peer`, confirm `PORTAL_BIND_LAN=1`, portal **:8002** reachable from Mac.
2. On Mac: establish **SSH `-L`** to Win portal **or** enable **TLS** on peer portal (`PEER_PORTAL_TLS_ENABLED=1`).
3. Load `ORAMA_CONTROL_PLANE_TOKEN` from operator store (must match Win); use SSH-forwarded local portal base URL for `/api/peer-inbox` only (not bare LAN HTTP with bearer).

Until then, rely on **git pull** on Perpetua-Tools / orama-system for cross-host receipts.
