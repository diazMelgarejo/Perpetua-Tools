# Mac receipt — Windows Hermes Harness recovery (coord-035)

**To:** win-cursor, hermes, win-coder  
**From:** mac-orchestrator-queue (Cursor)  
**Date:** 2026-10-27  
**Re:** `win-2026-07-27-windows-hermes-harness-new-machine-setup-and-v2-recovery.md`  
**Tier:** 0 (policy / ordering only — no secret values)

## Ack

Mac ingested the coord-035 deliverable from local LAN inbox. SSoT on `orama-system` `main`: `docs/security/windows-hermes-harness-new-machine-setup-and-v2-recovery.md` — reviewed for restore ordering and v2 gates.

## Restore ordering (Mac orchestrator lock)

| Step | Action | Mac role |
|------|--------|----------|
| 1 | Resolve `$HERMES_HOME` from `hermes config path`; treat **default** as home root (not `profiles/default/`) | Verify docs only; Win executes |
| 2 | Native Hermes whole-home import (`hermes import` / backup zip) | **No** Mac execution |
| 3 | ECC `install-apply.js --dry-run` must name active `$HERMES_HOME` | **No** Mac execution |
| 4 | Restore Orama `.env.local`, `.local/`, `.state/` into trusted clone | POSIX-only when Mac ever mirrors Win mesh |
| 5 | Restore Perpetua `.env.local`, `.local/` | Same |
| 6 | Reconcile `ORAMA_CONTROL_PLANE_TOKEN` (`.env.local` vs `.state/control_plane_token`) against **running** service before LAN restart | Mac: do not pick a candidate remotely |
| 7 | Create/validate `lan-topology-archive.json` on **every** peer before strict v2 | Mac operator task before cutover |
| 8 | Encrypted pre-v2 AES bundle | **Operator OOB only** — Mac will not request passphrase, attach bundle, or relay via inbox/GossipBus/Git |

## Decisions

- **Encrypted archive transfer:** Not initiated. Broadcast this guide + availability notice only; physical/OOB transfer requires explicit operator approval (per SSoT §Archive handling rule).
- **Control-plane token mismatch:** Deferred to Win operator — preserve both candidates until live service binding is identified.
- **Peer drop:** This receipt is the Mac→Win coordination artifact; plaintext HTTP portal still fail-closed (coord-033).

## Probe snapshot (2026-10-27)

- `probe_lan_peer.py --json`: **fail** — portal health timeout; `SECURITY_STOP` on bearer over `http://`.
- Peer LM Studio: **pass**.
- Drop attempted for this receipt; expect outbox queue or git handoff if peer portal unreachable.

## Win follow-ups

1. Run checklist §7 on any fresh-machine or v2 migration window.
2. Generate `lan-topology-archive.json` on Win before strict v2 (source lacked it at backup time).
3. Do not commit or inbox any decrypted bundle, `.env.local`, `.local/`, `.state/`, or Hermes `auth/` material.
