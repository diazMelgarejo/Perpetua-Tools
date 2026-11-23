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



## Addendum 2 (2026-11-22): IP migration handled; convergence CSR SIGNED

- Mac migrated 192.168.8.52 -> **192.168.8.51** (operator-confirmed). Windows discovery
  updated; queued items retargeted. Their serving leaf still carries SAN .52, so IP-dial
  Gate 2 fails at .51; the CN channel (server_hostname orama-mac.local) is the working
  equal-security path. Their front end is now CADDY on 8443 (backend 127.0.0.1:8002).
- **18/18 queued items DELIVERED over the CN channel to .51 - outbox CLEAR** (first full
  Win->Mac delivery). Byte-exact receipt v2 (exactly the 18 rows) delivered.
- The Mac's fresh-discovery 401 on OUR portal was their probe credential: our receiver
  binding verified - joint mode accepting orama shared `0f61c0c2...` AND PT lane
  `f2019d41...`, both 200 from localhost. Their configured credentials match neither.
  Operator-only ferry file written with the VALUES
  (`canonical-fixes/OPERATOR-ONLY-credential-ferry-2026-11-22.md`); the Mac adopts the
  shared token outbound (rule 3).
- **Convergence CSR received (mac8443.csr, file sha256 cea8b0a4...), VERIFIED (CN + SAN
  DNS:orama-mac.local,IP:192.168.8.51, RSA-2048), SIGNED with the 364490e8 CA key:**
  leaf `2e5fdcd0...`, 60-day (2026-11-22 -> 2027-01-21). Delivered to the Mac:
  `mac8443-leaf-364490e8-20261122.pem` + `mac8443-fullchain-364490e8-20261122.pem` + signing
  status + receipt v2 - all four DELIVERED (stored byte counts confirmed by their portal).
- Remaining: Mac installs the leaf in Caddy -> Python Gate 1+2 vs .51 -> both directions
  verify -> we drop the ef080f01 pin, they retire that key; 87-drain reconciliation (their
  side); the migration-plan workstream (fresh/empty first - decision stated) continues.
- GOTCHA: PowerShell wrappers abort on openssl's stderr (informational lines kill the
  chain) - run openssl via python subprocess for reliable capture.


## Addendum 3 (2026-11-22, later): CONVERGENCE COMPLETE - both directions green on standard machinery

- Mac installed the signed convergence leaf; verified from Windows: served leaf on
  192.168.8.51:8443 = 2e5fdcd0... (exact match), Gate 1+2 PASS with IP server_hostname and
  the 364490e8 pin; authenticated pull from their portal with the shared token = 200 (358 files).
- Their 18-row ack verified against our raw records: 18 parsed, 0 mismatches. Outbox 46
  delivered / 0 pending. Ack-verification receipt delivered to them (direct POST; their
  portal ok:true, 2884 bytes stored).
- **PEER_CA_SHA256 pin switched ef080f01 -> 364490e8 at USER scope** (durable; profiles
  clean). The machinery fail-closed correctly on the stale pin first ("PEER_CA_FILE does not
  match PEER_CA_SHA256; refusing to trust it (token not sent)") - the pin discipline works.
- **Gate 4 post-convergence proof: pure standard-machinery canary drop -> ok:true,
  received_at present** (2026-11-22-win-convergence-canary.md). No CN fallback, no custom code.
- Final state: ONE CA (364490e8, Windows-held key), ONE pin (User-scope), ONE shared token
  (0f61c0c2...) both directions, 60-day leaves, CSR flow. ef080f01 retired from active use;
  Mac to destroy that key. Open: their 87-drain reconciliation; migration-plan steps 2-5.


## Addendum 4 (2026-11-22, final): pending-task split + Mac focus directive delivered

- Windows leaf auto-reissue VERIFIED: served leaf bb19e06a... (60-day, expires 2027-01-16,
  SAN intact) - the T-7 regime is live on both sides now.
- Migration plan status: step 1 CLOSED; fresh/empty-first confirmed; step 2 blocked on the
  oramasys clone (NOT on this machine - verified; ultrathink-system is a different lineage);
  step 3 Windows parts DONE (PT caller/old-writer inventory: .state/perpetua_core.db 4.1MB;
  writers gossip_bus/lan_gossip_bridge/supervisor/heartbeat_monitor; consumer fastapi_app
  :8000; deployment binding evidence for 8443/8002/8001/8000 recorded); steps 4-5 gated.
- Delivered to the Mac via PURE standard machinery: migration-execution-status (push +
  self-drop) and the MAC FOCUS DIRECTIVE (7 ordered tasks: ef080f01 key retirement, 87-drain
  reconciliation, migration-2 offline proof, canonical-history/protected-routing tests,
  controller track, Cline launcher limits, then C8-C11; explicit NOT-your-tasks list and
  no-churn rule).
- Windows owns: ef080f01 file retention until Mac confirms destruction; long-running process
  restart note for the new pin; nothing else pending on this side.


## Addendum 5 (2026-11-23): WC1/WC2 + five-queue closeout delivered (subagent-executed)

- WC1 (receiver receipts for the 2026-11-15 Mac deliveries): 10 preserved receiver-side rows
  (received_at/bytes/sha256 from inbox sidecars; 242 mac-origin pre-11-16 context). File
  2026-11-23-win-wc1-receiver-receipts-nov15.md, sha256 6e2cf65f... The 87 is the Mac
  sender-side count; our preserved receiver records for that day are these 10.
- WC2 (runtime/qualification evidence, evidence-only): 2026-11-23-win-wc2-runtime-evidence.md,
  sha256 05cd8312... Custodian win-cline-20261115; native qualification owner UNNAMED
  (blocker, operator). Historical trials confirmed: scheduled p95 136.29/138.36/139.06 ms
  vs 60 ms gate (not a pass). Corrections to earlier session claims: (1) oramasys clones DO
  exist under worktrees (qual 5c4b3bbe w/ PR-100 tip ff81c6d, pin f33d809; v3 02e4f6d7) -
  none contains the Mac candidate e82530b7; (2) the 150 ms provisional native-only budget is
  NOT in the local PT memory file - it exists only as the Mac correction note assertion.
- Five-queue closeout: 2026-11-23-win-five-queue-closeout-reply.md, sha256 9a7e382e...
  PICKUP-03 in progress (no POSIX results yet); V1-1b blocked (no reviewer); V1-1c blocked
  (Mac POSIX evidence never arrived; migration2 receipt out of scope); PICKUP-09 blocked
  (PT #489 merged, orama docs follow-up NOT landed; route GPT-6.1 Terra Medium, operator go);
  D0 blocked (Orama #493 merged, no review artifact; reviewer reassignment needed).
- All three delivered via standard machinery (ok:true). Blockers route to the Mac
  orchestrator / operator per the original requests.


## Addendum 6 (2026-11-23): V1-1c independent review + queue dispositions + budget-blob verdict

- V1-1c INDEPENDENT REVIEW (self-claimed, eligible - did not author/implement): reproduced the
  exact 12-test run on Windows (Python 3.13.14 vs Mac 3.13.18, SQLite 3.53.1 both):
  12 passed / 0 skipped / 0 failed, tmp DBs only, repo stayed clean. Claims (b)/(c) CONFIRMED
  with line citations (liveness.py:8-12,131; heartbeat_monitor.py:355-366; task_queue.py:440-444).
  Gap: the ValueError(expected_agent_id) branch is unpinned; the strongest silence-not-
  termination test lives in an adjacent suite. Base 968a4de4 NOT in our object store - run
  against our clean HEAD; byte-equality unprovable (recorded). VERDICT: VERIFIED-WITH-GAPS.
  File 2026-11-23-win-independent-review-qf-v1-1c.md, sha256 58eb97e8...
- Queue dispositions emitted to the local gossip bus (4 events: PICKUP-03 macOS result
  recorded against claim autoresearcher-followups-CLINE-PICKUP-03-posix-test-run-e7b1aec8;
  PICKUP-09 follow-up NOT in snapshot 5afa6cd4, routing gate retained; D0 review-target-not-
  receipt; V1-1b unclaimed - Windows Antigravity NOT active, fallback to eligible reviewer).
  File 2026-11-23-win-queue-dispositions-and-budget-blob.md, sha256 3211b633...
- **C6 budget blob f93a163a NOT VERIFIED locally**: absent from ALL local PT clones; commits
  04aeb5d0/968a4de4 invalid locally; local git history has NO Nov-16 append and NO 150 ms
  anywhere (pickaxe empty). The 150 ms provisional native-only budget remains Mac-self-
  reported; WC2 must cite the LAN correction message, not a locally verified blob. Offline
  closure path documented (Mac drops blob bytes -> git hash-object equality -> operator-
  authorized fetch for ancestry).
- Both files delivered to the Mac via standard machinery. Caution noted: GOSSIP_SHARED_SECRET
  visible in env dumps - rotation recommended at next operator opportunity.
