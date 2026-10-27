# Coordinated cycle — coord-034 Hermes portable brain (2026-10-27)

**Tier:** 0–1 (verify scripts + memory; no code mutations).  
**Pulse job:** `win-2026-07-27-hermes-portable-brain-implemented.md` (mac_job_queue orchestrator).  
**Actor:** mac-orchestrator-queue (Cursor).

## Outcome

Mac ingested Win deliverable from LAN inbox (card already present locally; peer portal push still blocked on plain HTTP). Compared **Path A** (`install_hermes_profiles.py --sync`) vs **Path B** (`hermes_portable_brain.py` export/restore per `hermes-portable-brain-map.md`).

| Path | Mac state (2026-10-27) | When to use |
|------|------------------------|-------------|
| A — profile install | `HERMES_HOME=~/.hermes` is sparse: `config.yaml`, `skills/`, `plugins/` only; `--verify` reports all registry profile SOULs **missing** | Greenfield / roster sync from `bin/agents/REGISTRY.yml` |
| B — portable brain | Script on `main`; `export --dry-run` → schema `hermes-portable-brain/v1`, 1 config entry (no sessions); `py_compile` OK | Clone full Win brain or disaster recovery; sessions need `--include-sessions` |

Win verification (676→698 entries with sessions) is authoritative for production Hermes on Win; Mac orchestrator should run `install_hermes_profiles.py --sync` before relying on profile personas locally.

## LAN peer

- `probe_lan_peer.py --json`: **fail** — portal health timeout; `SECURITY_STOP` on token-over-HTTP (expected).
- LM Studio on peer: **pass**.
- Drop to Win: attempted with `mac-2026-07-27-hermes-portable-brain-mac-receipt.md`; may require operator git/TLS handoff (coord-033 pattern).

## Queue

- `mac_job_queue complete orchestrator` after PT learn/dream + push.
