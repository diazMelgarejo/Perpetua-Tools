# Win<->Mac auth restoration chronicle — 2026-11-17 (win-cline-20261115)

Timeline of the restoration session; the durable lessons live in
`semantic/LAN_PEER_TLS_AUTH_CHAIN_AND_RENEWAL_V2_DOMAIN_KNOWLEDGE_2026-11-17.md`.

## Timeline (all times local machine clock)

1. **Mac reports cert fixed** (`2026-11-17-mac-action-flush-now-for-win.md`): new leaf
   `4d735f60...` claims "same SANs incl. IP 192.168.8.52", verified by `openssl verify` (chain
   only) + `/health` (no auth). Asks Windows to flush the queued outbox.
2. **Flush attempt** (`flush-outbox --peer --state queued`): 0 delivered, 11 still queued —
   every item: `certificate verify failed: IP address mismatch, certificate is not valid for
   '192.168.8.52'`. New failure mode: chain now verifies, hostname does not.
3. **SAN probe** (CERT_NONE): served leaf IS `4d735f60...` (CA-signed ✓) but has **NO SAN
   extension at all** — the note's SAN claim was false.
4. **CN-fallback probe**: `server_hostname='orama-mac.local'` (the CN) PASSES full
   verification (pinned CA `ef080f01...` + hostname). Same security level; viable workaround.
5. **Hand-rolled POST** over the CN-verified channel (all 16 non-delivered outbox items):
   TLS passes, but **HTTP 401** on every item.
6. **Token enumeration**: exactly one local token (`ORAMA_CONTROL_PLANE_TOKEN`, 43 chars,
   sha256[:12] `0f61c0c2ad0c`); the Mac portal rejects it (401 with and without; `/health`
   200). Mac's portal rebuild regenerated the inbound token nobody else holds.
7. **CA mystery solved**: `364490e8...` = the ORIGINAL CA, alive at
   `backups/2026-10-28-pre-8443-listener/dot-local/share/oramasys/lan-control-plane/private/ca.crt`
   (+ its key). Live tree `~/.local/share/oramasys/lan-control-plane/` holds the SAME CA
   (pinned 2026-10-25 in `ca-pin.json`) — pubkey-matched `6de7903b...`. The `ef080f01...` CA
   (which the Mac signs with) has NO key on this machine. Convergence decision flips:
   **single CA = `364490e8...`, key custody Windows, peers send CSRs.**
8. **60-day regime coded**: `LEAF_VALIDITY_DAYS` 30→60 in `lan_control_plane_pki.py`
   (+ docstrings) — renewal agreement v2.
9. **Proxy restart**: first relaunch on the uv cpython failed (`cryptography` missing —
   the original process must have had it via env); relaunched on the PT venv python (3.13.14,
   cryptography 50.0.2) — UP, CA unchanged `364490e8...`, listening PID logged.
10. **Live traffic during restart**: a Mac POST hit the new proxy within seconds → 401 (their
    outbound token may have been regenerated too — watch; the shared-token rule covers it).
11. **Leaf not yet reissued**: one-shot `ensure()` → `reused` despite ~6d21h remaining —
    `timedelta.days` flooring + the T-7 boundary not yet crossed (fires at remaining < 7.0d);
    the proxy's 6h recheck will pick it up automatically. CA/SAN/Mac-pin unaffected.
12. **Gate checks on the Windows side all PASS**: chain+hostname (IP SAN present),
    `/health` 200, authenticated `/api/peer-inbox` 200 (334 files listed).

## Current state (end of session)

- Windows→Mac: blocked at Mac layer 2 (no SAN) + layer 3 (token). 16 items queued, auto-retry.
- Mac→Windows: TLS fine; their outbound token status uncertain (12:23 POST → 401).
- Windows leaf: 60-day validity coded; auto-reissue imminent; CA unchanged (no re-pin).
- Mac action file delivered to the operator:
  `ultrathink/2026-11-17-MAC-ACTIONS-NOW-3-STEPS-AND-CONVERGENCE.md`
  (1: re-pin shared token; 2: SAN re-issue; 3: CSR → Windows signs under `364490e8` → converge
  → retire `ef080f01`).

## Next actions

- Windows: on Mac completing steps 1–2, run `flush-outbox --peer --state queued`, send the
  byte-exact receipt (assignee mac), acknowledge per file.
- Windows: sign the Mac's CSR when it arrives (60-day, SAN `DNS:orama-mac.local,
  IP:192.168.8.52`); after they serve it, drop the `ef080f01` pin and keep only `364490e8`.
- Both: maintain `TRUST-INVENTORY.md`; stagger renewals; 4 gates per renewal.

## Addendum (same day, later): pull-publish adopted; Mac layers 2+3 PASS

- Mac's 12:37 layer report (`2026-11-17-mac-layer-report-all-gates-green.md`): SAN omission
  OWNED (CSR had it, x509 extfile didn't; `openssl x509 -req` doesn't copy); new leaf
  `1a11ce8c...` WITH IP SAN + 60-day validity (v2 adopted); shared token re-pinned as their
  portal's inbound credential (38-char rebuild token dead); Gate 4 outbound canary2 delivered.
- Mac→Win outbound healthy (drops keep arriving); the 12:23 401 on our portal was their
  inbound-token state during the rebuild window.
- **Convergence decided (operator-confirmed): `364490e8...`, key custody Windows, CSR flow** —
  resolves the contradiction the Mac flagged between the two earlier Windows files.
- **Pull-publish institutionalized:** 4 CANONICAL files + FIX-INDEX self-dropped into the
  Windows portal inbox (verified PRESENT via authenticated GET /api/peer-inbox, 340 files):
  `CANONICAL-FIX-INDEX-for-peer-agents.md`, `CANONICAL-4-GATE-AUTH-CHECKLIST-and-standing-rules.md`,
  `CANONICAL-RENEWAL-AGREEMENT-V2-60-DAY.md`, `CANONICAL-TRUST-INVENTORY.md`. Standing rule 6:
  permanent fixes are PUBLISHED and PULLED; the operator ferries only out-of-band secrets.
- Status line `2026-11-17-win-status-line-convergence-decided-364490e8.md` queued in the
  outbox (portal_port 8443 recorded; first attempt had fallen back to plain 8002 — always
  set `PEER_PORTAL_TLS_ENABLED/PORT` + `PEER_CA_FILE` when dropping).
- Flush still pending: Mac portal UNREACHABLE (~12:45+, WinError 10060, likely mid-restart);
  17 queued items retry automatically; byte-exact receipt follows on delivery.
- GOTCHA added: verify OUR own portal with the `364490e8` public CA
  (`public/orama-lan-ca-PHLab-H2LGBV3.pem`), not the Mac-direction CA file — wrong-CA
  verification fails with "self-signed certificate in chain" and wastes a diagnosis cycle.

