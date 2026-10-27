# Coordinated cycle — coord-036 Win probe correlation ack (2026-10-27)

**Tier:** 0 (inbox triage + policy lock; no code mutations).  
**Pulse job:** `win-mac-probe-correlation-20261026T081252Z.md` (mac_job_queue orchestrator).  
**Actor:** mac-orchestrator-queue (Cursor).

## Outcome

Mac processed Windows correlation for the unauthenticated Mac→Win HTTPS `GET /health` probe at `2026-10-26T08:12:52Z`. Windows reports **inconclusive** transport classification (no sampler, no WFP events, no firewall log). Mac **accepts** that verdict and will **not** unlock authenticated roundtrip replies or new canaries based on Mac-side timeout alone.

| Gate | Status |
|------|--------|
| Classify probe arrival stage from Mac timeout | **Blocked** — insufficient telemetry |
| Authenticated / bearer canary on this result | **No** — hold until timestamped Win sampler |
| Next controlled health probe | Requires Win packet/connection trace aligned to probe UTC |

Receipt: `mac-2026-10-27-win-mac-probe-correlation-mac-receipt.md`.

## LAN peer

- `probe_lan_peer.py --json`: **fail** — portal health timeout; `SECURITY_STOP` on bearer over `http://` (Tier 0).
- Peer LM Studio: **pass**.
- Drop to Win: receipt file (coord-033 TLS/git fallback if HTTP blocked).

## Queue

- `mac_job_queue complete orchestrator` after PT learn/dream + push.
