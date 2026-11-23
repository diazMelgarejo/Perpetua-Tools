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

1. Chain: `openssl s_client -connect <host>:8443 -CAfile <ca> -verify_return_error -brief
   </dev/null` → `Verification: OK` (non-zero exit on failure). Then compare the supplied CA with
   the recorded pin: `openssl x509 -in <ca> -outform DER | openssl dgst -sha256` must equal the
   pin in `ca-pin.json`. PASS only when both hold. Checked on OpenSSL 3.0.13 with a second CA in
   the default trust directory: `s_client -CAfile` alone replaces the default trust, but
   `openssl verify -CAfile` does not (it said OK for the wrong CA); add `-no-CApath -no-CAstore`
   there. Re-check the flags on other builds (for example LibreSSL) before relying on them.
2. Address: the peer dials a raw IP, so verify the IP SAN with `-verify_ip <addr-peer-dials>
   -verify_return_error` → OK. `-verify_hostname` matches DNS names only and rejects a valid IP
   SAN with "hostname mismatch".
3. Bearer: `curl --cacert <ca> -H "Authorization: Bearer $TOKEN"
   https://<host>:8443/api/peer-inbox` → 200 + JSON
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
- `LEAF_VALIDITY_DAYS` = **60** as of 2026-11-17 (was 30) — renewal agreement v2; the leaf is
  capped at its CA's expiry (`min(now + 60 days, CA not_after)`). See section 8.
- **GOTCHA: the uv cpython 3.11 lacks `cryptography`** — the proxy must run on the PT venv
  python (`Perplexity-Tools/.venv/Scripts/python.exe`, cryptography 50.0.2). Launch recipe:
  `cwd=Perplexity-Tools`, env `PORTAL_TLS_ENABLED=1`,
  `<venv-python> -X utf8 -m orchestrator.portal_tls_proxy --listen-port 8443
  --upstream-port 8002 --listen-host 0.0.0.0`.
- Reissue threshold: the check compares whole days (`timedelta.days`, floored) with 7, so a leaf
  is due as soon as less than 7.0 days remain; at 6d21h it IS due (pinned by
  `test_reissue_threshold_applies_to_whole_days_remaining`). Flooring never defers a reissue. A
  'reused' verdict below 7 days is unexplained (chronicle item 11); candidates, unverified: a stale
  running revision or the `ensure()` path.
- `ca-pin.json` pins the CA DER sha256 at first start; a DIFFERENT CA is refused (exit 3).
- Self-check evidence gate: `python -m orchestrator.portal_tls_proxy --self-check` (reads
  public CA only: health 200, protected-unauth 401/403, leaf SAN, expiry ≥7d, upstream
  loopback-only).

## 6. Renewal agreement v2 (2026-11-17) — the 60-day regime

1. Every leaf: **60-day validity**; auto-reissue at T-7; renewal is routine, not deadline-driven.
2. **CSR flow, single key custody:** the CA operator (Windows) holds the CA key; peers send
   CSRs (CN + SAN asserted); the operator signs 60-day leaves. CA private keys never travel.
   This is an operator procedure: the code has no CSR path and issues leaves only from the CA key
   it holds locally.
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

## 8. Policy lineage: later decisions, not contradictions

[The 2026-10-26 record](LAN_PEER_TLS_AND_DELIVERY_DOMAIN_KNOWLEDGE_2026-10-26.md) described the
first model. The 2026-11-15 to 11-17 outage showed its cost (two same-subject CAs, per-direction
pins and tokens, doubled renewals), and renewal agreement v2 (2026-11-17) is the later decision
and the current policy. Both records were correct for their date; neither is invalid.

| Topic | 2026-10-26 (earlier) | 2026-11-17 (later, current) |
| --- | --- | --- |
| Leaf validity | 30 days | 60 days, reissued at T-7, capped at the CA's expiry |
| CA custody | One CA per node | One CA, one pin, one token; Windows signs peer CSRs |
| CA key rule | A CA key never leaves its node | Unchanged: CA private keys never travel |

In code today: `LEAF_VALIDITY_DAYS = 60`, with `not_after = min(now + 60 days, CA not_after)`, so a
leaf never outlives its CA (`test_leaf_never_outlives_a_short_lived_ca`). There is no CSR path in
`orchestrator/lan_control_plane_pki.py`; CSR signing is an operator procedure.

Trade-off: a stolen leaf key is usable for up to 60 days instead of 30. Mitigations in the code:
the key store sits outside any checkout, the proxy pins the CA, and a CA change is refused.
Revert path: set `LEAF_VALIDITY_DAYS` back to 30; the tests derive their numbers from it.
