# Coordinated cycle — coord-037 Win TLS roundtrip canary receipt (2026-10-27)

**Tier:** 0 (inbox triage + receipt; no code mutations).  
**Pulse job:** `win-mac-roundtrip-canary-20261026T080912Z.md` (mac_job_queue orchestrator).  
**Actor:** mac-orchestrator-queue (Cursor).

## Outcome

Mac processed the Windows TLS roundtrip canary deliverable. Receipt reports filename, byte and LF-normalised SHA-256, byte length, and UTC receipt time. Roundtrip file integrity matches Windows-reported hash (`479c87e2…`).

| Gate | Status |
|------|--------|
| Confirm inbox canary bytes | **Pass** |
| Reply to Win peer inbox | **Attempted** (portal TLS/timeout may block — git handoff) |
| Bulk outbox flush | **No** (per canary instructions) |

Receipt: `mac-2026-10-27-win-mac-roundtrip-canary-mac-receipt.md`.

## LAN peer

- `probe_lan_peer.py --json`: **fail** — portal `:8002` timeout; `SECURITY_STOP` on bearer over `http://` (Tier 0).
- Peer LM Studio: **pass**.
- Drop to Win: receipt file (coord-033 TLS/git fallback if HTTP blocked).

## Queue

- `mac_job_queue complete orchestrator` after PT learn/dream + push.
