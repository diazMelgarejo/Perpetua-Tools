# Coordinated cycle — coord-035 Windows Hermes recovery (2026-10-27)

**Tier:** 0–1 (read SSoT + memory; no code mutations).  
**Pulse job:** `win-2026-07-27-windows-hermes-harness-new-machine-setup-and-v2-recovery.md` (mac_job_queue orchestrator).  
**Actor:** mac-orchestrator-queue (Cursor).

## Outcome

Mac reviewed Win Hermes new-machine / pre-v2 recovery guide and locked restore ordering: Hermes native home → ECC active-home preflight → Orama/PT local-only state → token reconciliation → topology archive → v2 flags. Encrypted private bundle remains operator OOB; Mac did not initiate transfer.

| Gate | Status |
|------|--------|
| SSoT guide on `orama-system` `main` | Verified |
| `ORAMA_CONTROL_PLANE_TOKEN` dual-candidate mismatch | Open on Win — reconcile before LAN |
| `lan-topology-archive.json` per host | Open — create before strict v2 |
| Encrypted pre-v2 bundle | Local to Win; no agent relay |

## LAN peer

- `probe_lan_peer.py --json`: **fail** — portal health timeout; `SECURITY_STOP` on token-over-HTTP (expected).
- LM Studio on peer: **pass**.
- Drop to Win: `mac-2026-07-27-windows-hermes-harness-recovery-mac-receipt.md` (coord-033 TLS/git fallback if HTTP blocked).

## Queue

- `mac_job_queue complete orchestrator` after PT learn/dream + push.
