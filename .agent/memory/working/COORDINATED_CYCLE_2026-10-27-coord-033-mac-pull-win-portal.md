# Coordinated cycle — coord-033 Mac pull from Win portal (2026-10-27)

**Tier:** 0 (probe + inbox verification; no code mutations).  
**Pulse job:** `win-2026-07-27-mac-pull-from-win-portal.md` (mac_job_queue orchestrator).  
**Actor:** mac-orchestrator-queue (Cursor).

## Outcome

Mac executed the coord-033 runbook: peer portal pull is **blocked** (Win `:8002` unreachable from Mac; `SECURITY_STOP` on bearer-over-LAN-HTTP). Priority Win inbox cards listed in the job are **already present** on Mac local inbox; coord-032 env-local **reply** is in Mac outbox.

Receipt: `mac-2026-07-27-mac-pull-from-win-portal-mac-receipt.md` (this cycle).

## LAN peer

- `probe_lan_peer.py --json`: **fail** (portal timeout + token transport policy).
- Drop to Win: attempted with receipt file; expect **operator git/TLS/SSH** handoff if peer push fails.

## Queue

- `mac_job_queue complete orchestrator` after PT learn/dream + push.
