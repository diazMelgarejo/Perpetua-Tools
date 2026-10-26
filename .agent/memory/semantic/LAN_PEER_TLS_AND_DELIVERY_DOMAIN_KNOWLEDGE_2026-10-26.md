# Domain knowledge: authenticated peer mesh over TLS, with honest delivery states (2026-10-26)

**Purpose:** a durable reference that other memory, plans and PRs can link to. It states how the
Windows/Mac peer link works, which invariants hold, and which mistakes were made while it was
re-established. Narrative lives in
`SESSION_CHRONICLE_2026-10-26_GRANDFATHERED_FLEET_CONTACT_REESTABLISHMENT_TECHNICAL.md`.
**Status:** record only. No secrets, keys, tokens, network addresses, host names, account
identifiers or workstation paths. Repositories by public `owner/repo`, commits by SHA.

## 1. Topology and vocabulary

* **Grandfathered fleet:** nodes that predate the TLS migration. Plain HTTP bearer traffic is
  historical incident context only, never a supported transport: current peer delivery sends the
  shared bearer only after verified TLS. Docs 49/50 in orama
  (`docs/v2/49-peer-mesh-auth-tls-v2-plan.md`, `50-mesh-security-migration-ladder.md`) preserve
  bearer compatibility while requiring TLS first, with mTLS and rotation deferred to later gates.
* **Nodes:** one macOS node (Ollama, MLX, Portal behind a TLS front end) and one or more Windows
  nodes (LM Studio on :1234, an RTX GPU). Ports: PT 8000, orama 8001, Portal 8002 (loopback when
  TLS mode is on), TLS front end 8443.
* **Two secrets, never interchangeable:** the HTTP bearer and the discovery/gossip shared secret
  (`GOSSIP_SHARED_SECRET`). A 401 after a good TLS health check is a credential mismatch, not an
  offline host; fix it out of band, never by substituting the other secret.
* **Evidence ladder (strongest last):** TCP connect, TLS health 200 with verification on, protected
  endpoint 401 without credentials, authenticated call 200, **receiver-reported receipt**. Each
  step proves only itself. A portal returning `ok:true` proves acceptance, not that the receiver
  stored or can read the file.

## 2. Trust model

| Rule | Mechanism | Where |
| --- | --- | --- |
| One CA per node, private key never leaves it | Local CA, `CA:TRUE` critical, `pathlen 0`, keyCertSign + cRLSign, RSA 3072, 730 days, SKI/AKI | `orchestrator/lan_control_plane_pki.py` (PT) |
| Short-lived leaf, CA stable across DHCP changes | Leaf: RSA 2048, serverAuth, 30 days, reissued on SAN change or when under 7 days remain; never outlives the CA | same |
| Names, not guesses | Leaf SANs: `localhost`, `PORTAL_TLS_SAN_NAMES`, every current local IPv4 address including loopback | `orchestrator/portal_tls_proxy.py` |
| Local CA pin | `private/ca-pin.json`; a different CA than the pinned one exits 3 | PKI + proxy |
| Out-of-band fingerprint | SHA-256 of the **public CA file** is given to the peer operator over a separate channel; the transport carrying the CA file is never the source of the hash | operator procedure |
| Process-scoped client trust | `PEER_CA_FILE` (PEM bundle) and `PEER_PINNED_FINGERPRINTS`, applied per request by `peer_tls.context_for`; `SSL_CERT_FILE` is still honoured by the default context | `peer_tls.py` (orama) |
| Fail closed | `PeerTrustError` (an `OSError`) means no token is sent | `peer_tls.py`, callers |
| No system trust change | Importing a CA into the OS store is a system security setting the operator makes themselves | policy |
| Store outside any checkout and outside AppData | `~/.local/share/oramasys/lan-control-plane` on every OS, `private/` (ca.key, ca.crt, leaf.key, leaf.pem, ca-pin.json) and `public/` (CA PEM, SHA256SUMS), explicit non-inherited ACLs | PT `portal_tls_dir()` |

Verification contexts always use `ssl.create_default_context(cafile=...)`; `-k`, `verify=False` and
`CERT_NONE` are never used. Python 3.13 adds `VERIFY_X509_STRICT` by default, so the CA needs SKI
and AKI and the leaf needs serverAuth plus a matching SAN; a test performs both handshakes.

## 3. Transport rules that were violated once and are now enforced

* A token travels only over an authenticated transport. `probe_lan_peer.run_checks` derives the
  scheme from `PEER_PORTAL_TLS_ENABLED` and refuses (`SECURITY_STOP`) to send candidates to an
  `http://` status URL (orama #446, test `tests/test_probe_status_transport_guard.py`).
* Scheme is part of identity: reconstruction layers must never hardcode `http://`.
* The TLS proxy is transport only: it forwards every request header, including Authorization,
  untouched; it logs nothing about requests; WebSocket upgrade is a byte pass-through so `wss`
  gossip works through it; TLS handshakes run off the accept thread so one stalled client cannot
  block `accept`.
* The Portal binds loopback whenever TLS mode is on, even if the config says LAN bind; only the
  TLS port faces the LAN. `--lan-peer` must not force a LAN bind of the Portal in that mode.

## 4. Delivery semantics

States per outbox record: `queued` (accepted locally, not proven sent), `sent` (the remote returned
success), `delivered` (the destination's inbox listing contains the file **and** the stored content
hash matches the local content, compared after LF normalisation). `queued` is never reported as
delivered. Commands (`lan_peer_assign.py`): `outbox-status` (read-only), `outbox-resolve` (mark one
item with evidence), `outbox-resubmit --only <name>` (same remote filename, history kept; explicit
selection only), `receipt <name>` (local, read-only: filename, bytes, SHA-256 of stored bytes,
LF-normalised SHA-256, received UTC time). There is deliberately no bulk retarget: a historical
record keeps its stored destination because the topology that produced it may have changed
(DHCP drift, port moved from plain HTTP to TLS).

Canary protocol: one unique, non-sensitive file per direction; the receiver independently reports
filename, received-byte SHA-256, LF-normalised content SHA-256 and UTC time. A sender records
`delivered` only when the receiver's normalised hash matches its local normalised hash; otherwise
the record remains `sent` or `queued` for investigation. Duplicate protection: the destination's
existing content hash is compared before any resubmit.

## 5. Windows service lifecycle

* Services are spawned by `scripts/lib/spawn_detached.py`: `Popen` with
  `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB` (falls back without
  breakaway when the job forbids it), stdin to NUL, stdout appended to `.logs/<svc>.log`, stderr
  merged, `PYTHONUNBUFFERED=1`, PID written to `.logs/<svc>.pid`. Secrets reach services through
  the environment, never the command line. Logs survive the launcher exiting.
* `Wait-ForPort` polls loopback and fails fast when the PID is gone, printing the log tail. The
  launcher exits non-zero when a core service fails. `--stop` kills only PIDs it can prove it owns
  (pid file plus command-line match), never by process name.
* `--restart-portal` restarts only the Portal and its TLS proxy; PT and orama keep running.
* A venv `python.exe` is a launcher on Windows; the listener is its child. PID files hold the
  launcher, port ownership shows the child, and a job object can kill children with the parent.
* After the TLS front end is up the launcher runs `portal_tls_proxy --self-check`: TLS health 200,
  unauthenticated protected request 401, leaf SAN covers the address, leaf expiry, upstream not
  reachable on any non-loopback address. Only an explicit `ConnectionRefusedError` counts as
  proof for the last check; a timeout or having nothing to probe is `WARN` (not established).

## 6. Platform pitfalls (Windows PowerShell 5.1 and Python)

* 5.1 reads a BOM-less UTF-8 script as ANSI. An em dash (bytes E2 80 94) then contains a byte that
  becomes a right double quote and ends the string, so the script fails to parse. Any `.ps1` with
  non-ASCII text needs a UTF-8 BOM; tests assert this and parse every tracked script.
* Under `$ErrorActionPreference='Stop'`, native stderr (pip's notices) becomes a terminating
  error when output is redirected. Wrap native calls with `Continue` and check `$LASTEXITCODE`.
* A PowerShell function emits every uncaptured expression: probe stdout plus `$false` is a
  truthy array. Capture native output and return a scalar.
* `localhost` resolves IPv6 first on Windows (about 2 s); probe IPv4 loopback with short timeouts.
* Not available in 5.1: `??`, `?.`, ternary, `&&`, `||`, `-AsHashtable`, the backtick-e escape.
* `curl.exe` on Windows (schannel) tries certificate revocation and cannot reach a private CA's
  (nonexistent) revocation endpoint, so it fails on a valid private chain. Verify with Python's
  `ssl` instead of weakening verification.
* A process started from an MSIX-packaged app has `%LOCALAPPDATA%` writes redirected into the
  package's private store. State shared with ordinary terminals must live outside AppData.
* `fcntl` does not exist on Windows; a cross-platform lock uses `msvcrt.locking` on one byte.
* NTFS directory listings can show 0 bytes for a log another process holds open.
* `pip install -r <other repo>/requirements.txt` containing `-e .` installs the current
  directory, not the other repo.

## 7. Discovery rules

* Candidate evidence tiers for the Mac: strong = MLX markers or a model that exists only on the
  Mac; weak = an embedding model or an Ollama-only port. Known Windows addresses are excluded from
  every Mac candidate (explicit setting, cache, scan and last-good back-fill), otherwise a second
  Windows node can be mislabelled as the Mac forever.
* Sibling nodes that cannot be identified are reported unknown and not probed; a stale configured
  address that matches no local interface produces a warning and never decides locality.
* PT `/health` budget: six backend probes run concurrently on a bounded module-level executor
  with a 1.5 s deadline, 1 s IPv4-loopback local probes, a cloud-only single-flight cache (60 s on
  success, 15 s on failure). Never wrap `backend_health_map` in a cache; the Portal's timeout is 3 s.

## 8. Coordination rules that proved necessary

* Every board note carries author, actor, identity_verified, endorsement and takeover; where two
  sessions post under one agent id, add a session label. Endorsement is never merge approval.
* Payloads must not contain host names or LAN addresses (the board is append-only; correct by
  redaction with an index-aware update and a recorded correction, never by quoting the value).
* Do not write into another agent's worktrees; claim a lane on the board first. One branch and
  one PR per repository ends merge sequencing arguments.
* Do not delete a stacked PR's base branch after merging it: GitHub auto-closes the PRs on top.
* "Merged" is not "content on main": diff the PR's file list between the branch and main.

## 9. Open decisions (owners)

Operator: rotate the control-plane bearer on both hosts together (one candidate once travelled in
cleartext); stable names or DHCP reservations (certificates should carry names, with addresses as
fallback); a fleet CA with name constraints and signing-request issuance (T4); the ai-cli-mcp
readiness gate policy (P1); shutting down any temporary public download listener. Mac lane:
`start.sh` parity (fail fast, honest fallback status), `load-local.sh` handling of `#` in quoted
values, independent receipts for every Windows delivery.
