# Portal TLS front end (Track B, T2)

**Status:** implemented, opt-in, off by default.
**Date:** 2026-10-25
**Code:** `orchestrator/portal_tls_proxy.py` (CLI and configuration),
`orchestrator/lan_control_plane_pki.py` (CA, leaf, pin, store), built on the
generalized `orchestrator/alphaclaw_tls_proxy.py`.

## Purpose

The orama Portal speaks plain HTTP. A LAN peer cannot safely send an
authenticated request to it. This front end terminates TLS on a LAN-facing
port and forwards to the Portal on loopback. It is transport only: every
header, including `Authorization`, is forwarded untouched, nothing about a
request is logged, and the listener is https only.

## What changed in the shared proxy

`AlphaClawTlsProxy` gained optional fields: listen host, upstream host,
certificate directory, file basename, log label, common name, SAN names, SAN
addresses, a SAN-reissue switch, a `pki` object (CA mode), a WebSocket
pass-through switch and its idle timeout. Every default reproduces the
previous AlphaClaw behaviour (self-signed leaf, loopback only, no WebSocket
tunnel), and the AlphaClaw tests are unchanged and pass.

## CA model

The Portal runs its own local CA, so the certificate a peer trusts does not
change when this host's address changes.

| Item | Value |
| ---- | ----- |
| CA | `CN=Orama LAN Control Plane CA (<hostname>)`, CA:TRUE critical, pathlen 0, keyUsage keyCertSign + cRLSign critical, SubjectKeyIdentifier, about 2 years |
| Leaf | CA:FALSE critical, keyUsage digitalSignature + keyEncipherment critical, EKU serverAuth, SKI + AuthorityKeyIdentifier, 30 days |
| Leaf SANs | `localhost`, `PORTAL_TLS_SAN_NAMES`, every current local IPv4 address including loopback |
| Served chain | leaf followed by the CA |

Certificates verify with `ssl.create_default_context(cafile=<ca.pem>)` and
with `VERIFY_X509_STRICT` added (Python 3.13 default behaviour); a test does
both against a live handshake.

## Store layout

Default location, outside any checkout: `~/.local/share/oramasys/lan-control-plane/`
on every OS, the same layout as the Mac peer. Override with
`PORTAL_TLS_STATE_DIR` (`PORTAL_TLS_CERT_DIR` is accepted as an alias).
A state directory inside a git checkout is allowed but logged as a warning.

Windows does not use `%LOCALAPPDATA%`. A process started from an
MSIX-packaged desktop app (an agent host, for example) has its AppData writes
redirected into that package's private store. A CA created there is invisible
to a launch from an ordinary terminal, which would then mint a second CA and
break the trust the peer pinned. The user profile outside AppData is not
redirected, so every launch context shares one CA. A store created at the old
location can be moved here as a whole directory while the proxy is stopped;
the CA, its pin and its fingerprint are unchanged by the move.

```text
private/   ca.key  ca.crt  leaf.key  leaf.pem (leaf + CA)  ca-pin.json
public/    orama-lan-ca-<hostname>.pem   SHA256SUMS
```

`private/` and every file in it are restricted with the shared secure-path
helpers (POSIX modes, or an owner plus Administrators DACL on Windows).
`public/` holds only the public CA certificate and a `SHA256SUMS` line for
that exact file; no private key is ever written there.

## Rotation and pinning

- The leaf is reissued automatically, with a log line, when fewer than 7 days
  remain, when its SANs no longer cover the configured names or the current
  addresses (for example after a DHCP change), or when it was not issued by
  the current CA. The CA is untouched and no re-pin is needed.
- The first start pins the CA certificate fingerprint in `private/ca-pin.json`.
  A later start with a different CA, or with the CA files gone while the pin
  exists, is refused with exit code 3 and nothing is regenerated. A CA change
  is an explicit two-sided migration: verify out of band, remove the pin and
  CA files, start, then give peers the new public CA and hash.
- The CA is not renewed automatically. A warning is logged under 60 days left.
- The leaf is rechecked at start and then every 6 hours while the proxy runs
  (current local addresses are re-read each time). A reissued leaf is applied
  to new TLS handshakes without a restart; a failed recheck is logged and the
  current certificate keeps serving.
- A corrupt or invalid `ca-pin.json` is refused with exit code 3 (it is never
  treated as "no pin"). PKI state changes run under an exclusive lock in
  `private/` with atomic file replacement, so concurrent first starts end up
  with one CA.
- The TLS handshake runs in the per-connection thread with a 10 second bound,
  so an idle or slow TCP client cannot block other clients. Upstream redirects
  are relayed to the client, never followed, and upstream error responses keep
  their headers.

## WebSocket support

A request with `Connection: Upgrade` and `Upgrade: websocket` is forwarded on
a raw TCP connection to the upstream. The request head is re-sent unchanged,
including `Authorization`. The 101 response is relayed, then bytes are pumped
both ways until either side closes or the connection is idle for 300 seconds.
A slow-reading peer does not end the tunnel; only idleness or a close does.
Other requests use the normal streaming forwarder.

## Configuration

| Variable | Meaning | Default |
| -------- | ------- | ------- |
| `PORTAL_TLS_ENABLED` | opt-in gate (`1`, `true`, `yes`, `on`) | off |
| `PORTAL_TLS_SAN_NAMES` | comma list of DNS names for the leaf | empty |
| `PORTAL_TLS_LISTEN_HOST` | bind address | all interfaces |
| `PORTAL_TLS_STATE_DIR` | state directory (alias `PORTAL_TLS_CERT_DIR`) | see Store layout |

## Running

```text
python -m orchestrator.portal_tls_proxy --listen-port 8443 --upstream-port 8002 [--listen-host H]
python -m orchestrator.portal_tls_proxy --print-fingerprint
```

The first form runs until stopped and prints one line:
`portal-tls-proxy pid=N listening https://H:P upstream=U ca_sha256_file=<hex>`.
The second creates or reuses the CA and leaf, starts no server, and prints
exactly two lines: `ca_sha256_file=<64 hex>` (the SHA-256 of the public CA
file bytes, equal to `Get-FileHash` or `sha256sum`) and
`ca_public_path=<absolute path>`.

Exit codes: 0 normal, 2 cannot start (bind failure, missing `cryptography`,
unusable state), 3 CA pin mismatch.

## Self-check (evidence gate)

```text
python -m orchestrator.portal_tls_proxy --self-check [--listen-port P] [--upstream-port U] [--host H]
```

Run this against the running endpoint before peers are told to trust it.
Defaults: P 8443, U 8002, H the first non-loopback local address (loopback
when there is none). It reads only the public CA file from the store, never a
private key, and creates, reissues or rotates nothing; a missing store or CA
is a FAIL. Verification uses that CA alone (no system roots, no environment
override, hostname or address checked against H). Every network call is
bounded to 5 seconds or less, and no token is read or sent.

| Line | PASS when |
| ---- | --------- |
| `check_tls_health` | `GET /health` returns 200 |
| `check_protected_unauth` | `GET /api/peer-inbox` with no `Authorization` returns 401 (403 also passes) |
| `check_leaf_san` | the presented leaf's SAN contains H (IP SAN or DNS SAN) |
| `check_leaf_expiry` | more than 7 days remain; WARN within 7 days; FAIL expired; notAfter printed as UTC ISO-8601 |
| `check_upstream_loopback_only` | a 1 second TCP connect to the upstream port fails on every non-loopback local address |

Each prints `check_<name>=PASS|WARN|FAIL <detail>`, followed by
`ca_sha256_file=<hex>` and `self_check=PASS|FAIL`. Exit 0 when nothing FAILs
(WARN allowed), 1 on any FAIL, 2 on a usage error (an older build prints
"unrecognized arguments").

## Operator exchange

1. Run `--print-fingerprint` on this node.
2. Send the public CA file (`ca_public_path`) to the peer over one channel and
   the `ca_sha256_file` value over a separate channel.
3. The peer checks the hash of the file it received, then uses the CA for its
   own processes only (for example a per-process CA file setting). Nothing is
   added to a system trust store by this code, and no private key leaves
   the node.

## Dependency

`cryptography` (>=42) is declared in `pyproject.toml`, and `uv.lock` was
regenerated to include it.

## Not covered here

Launching and stopping the proxy from the orama start script, peer-side
verification, a fleet CA with name constraints and mTLS belong to the other
Track B steps.
