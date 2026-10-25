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

Default location, outside any checkout: `%LOCALAPPDATA%/oramasys/lan-control-plane/`
on Windows, `~/.local/share/oramasys/lan-control-plane/` elsewhere. Override
with `PORTAL_TLS_STATE_DIR` (`PORTAL_TLS_CERT_DIR` is accepted as an alias).
A state directory inside a git checkout is allowed but logged as a warning.

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
- The leaf is checked at process start. Restart the proxy after a network
  change to pick up new addresses.

## WebSocket support

A request with `Connection: Upgrade` and `Upgrade: websocket` is forwarded on
a raw TCP connection to the upstream. The request head is re-sent unchanged,
including `Authorization`. The 101 response is relayed, then bytes are pumped
both ways until either side closes or the connection is idle for 300 seconds.
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
