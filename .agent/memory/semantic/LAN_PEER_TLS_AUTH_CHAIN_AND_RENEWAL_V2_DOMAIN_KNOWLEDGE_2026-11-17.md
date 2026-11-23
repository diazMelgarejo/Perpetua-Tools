# LAN peer TLS: the 3-layer auth chain, CA/token topology, and renewal v2 — domain knowledge (2026-11-17)

Durable facts distilled from the 2026-11-15 → 11-17 Win<->Mac outage and restoration work.
Every claim traces to a live probe or an on-disk artifact; no secrets (tokens by length +
sha256 prefix, certs by DER sha256).

## 1. The 3-layer chain (memorize this model)

Every peer call passes THREE independent gates; a fix at one says nothing about the others:

1. **TLS chain** — leaf must chain to the pinned CA (`PEER_CA_FILE`, DER sha256 compared).
2. **TLS hostname** — `server_hostname` = the URL host = the raw IP; must match the cert's
   **SAN**. CN-only certs can NEVER match an IP connection (RFC 6125; no CN fallback for IPs).
3. **HTTP bearer** — `Authorization: Bearer <shared token>` must validate at the peer portal.

Fail-closed invariant: tokens travel only after layers 1+2 passed (RFC 6750 §5.3).

## 2. The 4-gate verification checklist (the antidote to "verification theater")

`openssl verify` checks chains ONLY (no hostname); `/health` is unauthenticated. Both were
used as "proof" during this incident and both proved nothing. The real checklist:

1. Chain: `openssl s_client -connect <host>:8443 -CAfile <ca> -brief` → Verification: OK
2. Hostname: add `-verify_hostname <addr-peer-dials> -verify_return_error` → OK
3. Bearer: `curl --cacert <ca> -H "Authorization: Bearer $TOKEN" https://<host>:8443/api/peer-inbox` → 200 + JSON
4. Machinery: `lan_peer_assign.py list --peer` + real canary drop, receiver sidecar hash match

Report per-gate: `LAYER n: PASS/FAIL(<exact error>)`; the word "fixed" only after Gate 4.

## 3. CA topology as of 2026-11-17 (the "two same-subject CAs" trap, resolved)

| DER sha256 | Identity | Key custody | Status |
|---|---|---|---|
| `364490e8...` | ORIGINAL "Orama LAN Control Plane CA (PHLab-H2LGBV3)", pinned 2026-10-25 | **Windows** (`~/.local/share/oramasys/lan-control-plane/private/ca.key`) | **CONVERGENCE TARGET** — signs the Windows leaf; already pinned by the Mac |
| `ef080f01...` | The CA distributed to the Mac 10-25 (re-copied 11-09) | Mac (evidenced: they signed leaf `4d735f60...` with it) | INTERIM — retire after CSR convergence |
| `8df85bdf...` | 11-03 interim CA | — | superseded |
| `53c1ef1f...` | Self-signed leaf that was mis-delivered as a "CA" (mac-ca-2026-11-15) | Mac | retired |

Lesson: two live CAs shared the SAME subject text — the "never dedupe" trap. It spawned the
"pin 364490e8 matches nothing" confusion (it lived in
`Downloads/SKILLS.md/ultrathink/backups/2026-10-28-pre-8443-listener/dot-local/share/oramasys/lan-control-plane/private/ca.crt`).
Rule: **search the full inventory (incl. backups/handoff zips) before claiming any pin
"matches nothing"**, and keep `TRUST-INVENTORY.md` current. Never create two certs with the
same subject.

## 4. Token topology

- ONE shared control-plane token, both directions (2026-11-04 contract): 43 chars,
  sha256[:12] `0f61c0c2ad0c`, env `ORAMA_CONTROL_PLANE_TOKEN` (candidates:
  `ORAMA_CONTROL_PLANE_TOKEN_PEER` > orama lane > PT lane; `probe.outbound_control_plane_tokens()`).
- Incident: the Mac's portal rebuild regenerated the inbound token it validates → 401 for
  Windows with-and-without the shared token (`/health` stayed 200). Their outbound POST also
  hit 401 after the rebuild. Rule: **inbound validation and outbound Bearer use the SAME
  shared value on both hosts; rotations go out-of-band via the operator, both sides updated
  atomically.**

## 5. Machinery map + operational gotchas (Windows side)

- Listener: `orchestrator/portal_tls_proxy.py` (8443 → plain 8002 loopback), CA mode over
  `AlphaClawTlsProxy` + `lan_control_plane_pki.py`.
- `pki.ensure()` problem codes: `missing` / `reissued` (wrong CA) / `rotated`
  (remaining < `LEAF_MIN_REMAINING_DAYS`=7) / `san_reissued` (SAN gap or missing SAN ext).
  SANs auto-refresh from `ip_source()` at every ensure (follows DHCP changes).
- Hot reload: the renew loop re-runs ensure() every `pki_recheck_seconds` = 6h and swaps the
  SSLContext when the **on-disk leaf fingerprint** differs from the served one — an external
  reissue IS detected; a restart makes it immediate.
- `LEAF_VALIDITY_DAYS` = **60** as of 2026-11-17 (was 30) — renewal agreement v2.
- **GOTCHA: the uv cpython 3.11 lacks `cryptography`** — the proxy must run on the PT venv
  python (`Perplexity-Tools/.venv/Scripts/python.exe`, cryptography 50.0.2). Launch recipe:
  `cwd=Perplexity-Tools`, env `PORTAL_TLS_ENABLED=1`,
  `<venv-python> -X utf8 -m orchestrator.portal_tls_proxy --listen-port 8443 --upstream-port 8002 --listen-host 0.0.0.0`.
- GOTCHA: `timedelta.days` floors — the T-7 reissue fires when remaining < 7.0 days exactly;
  near the boundary a 'reused' verdict can persist for hours. Don't misread it as a bug.
- `ca-pin.json` pins the CA DER sha256 at first start; a DIFFERENT CA is refused (exit 3).
- Self-check evidence gate: `python -m orchestrator.portal_tls_proxy --self-check` (reads
  public CA only: health 200, protected-unauth 401/403, leaf SAN, expiry ≥7d, upstream
  loopback-only).

## 6. Renewal agreement v2 (2026-11-17) — the 60-day regime

1. Every leaf: **60-day validity**; auto-reissue at T-7; renewal is routine, not deadline-driven.
2. **CSR flow, single key custody:** the CA operator (Windows) holds the CA key; peers send
   CSRs (CN + SAN asserted); the operator signs 60-day leaves. CA private keys never travel.
3. **Staggered renewals** — sibling hosts never renew the same day (channel never double-blind).
4. Every renewal proven by the 4 gates + byte-exact receipt (filename, raw/stored byte
   counts, SHA-256, acknowledged by name + sidecar hash).
5. CA/token rotations: out-of-band operator confirm, both sides updated atomically.
6. Maintain `TRUST-INVENTORY.md`; inventory before claiming any pin "matches nothing".

## 7. Incident rules (earned 2026-11-15 → 11-17)

- SAN in every leaf (`DNS:<host>, IP:<lan-ip>`); assert it in the generator; Gate 2 after
  every re-issue.
- One CA, one pin, one token — per-direction anything is a trap that doubles renewals.
- A component test (`openssl verify`, `/health`) is not a fix; only Gate 4 proves a fix.
- Both sides claimed things from incomplete inventories this cycle; inventory first, then talk.

