# Portal TLS front end (Track B, T2)

**Status:** implemented, opt-in, off by default.
**Date:** 2026-10-25
**Code:** `orchestrator/portal_tls_proxy.py`, built on the generalized
`orchestrator/alphaclaw_tls_proxy.py`.

## Purpose

The orama Portal speaks plain HTTP. A LAN peer cannot safely send an
authenticated request to it. This front end terminates TLS on a LAN-facing
port and forwards to the Portal on loopback. It is transport only: every
header, including `Authorization`, is forwarded untouched, and the listener
is https only.

## What changed in the shared proxy

`AlphaClawTlsProxy` gained optional fields: listen host, upstream host,
certificate directory, file basename, log label, common name, SAN names, SAN
addresses and a SAN-reissue switch. Every default reproduces the previous
AlphaClaw behaviour (loopback only, `alphaclaw` store, `localhost` SAN, no
reissue), and the existing AlphaClaw tests are unchanged and pass.

## Configuration

| Variable | Meaning | Default |
| -------- | ------- | ------- |
| `PORTAL_TLS_ENABLED` | opt-in gate (`1`, `true`, `yes`, `on`) | off |
| `PORTAL_TLS_SAN_NAMES` | comma list of DNS names for the certificate | empty |
| `PORTAL_TLS_LISTEN_HOST` | bind address | all interfaces |
| `PORTAL_TLS_CERT_DIR` | key and pin store | `.state/portal_tls` under the PT root |

The store is separate from AlphaClaw's. The private key is created with the
restrictive permissions of the shared secure-path helpers and never leaves
the node.

## Certificate and pin behaviour

- The leaf SANs are the configured DNS names plus `localhost` plus this
  host's current local IPv4 addresses.
- The leaf and its SHA-256 fingerprint persist across restarts (TOFU pin).
- If the address or name set is no longer covered (for example after a DHCP
  change), the leaf is reissued, a warning is logged and the pin is updated
  explicitly. Give the new public certificate and fingerprint to peers.
- If the certificate files vanish while a pin exists, start is refused with a
  fingerprint mismatch. Delete the pin file only after verifying out of band.

## Running

```text
python -m orchestrator.portal_tls_proxy --listen-port 8443 --upstream-port 8002
python -m orchestrator.portal_tls_proxy --print-fingerprint
```

The first form runs until stopped and logs one line with its pid, listen URL
and fingerprint. The second prints `sha256:<hex>` and the PUBLIC certificate
in PEM form so the operator can hand both to a peer. It never prints the key.

Exit codes: 0 normal, 2 cannot start (bind failure or missing `cryptography`),
3 fingerprint mismatch.

## Dependency note

`alphaclaw_tls_proxy.py` imports `cryptography`, but the PT package manifest
does not declare it. Without it the proxy raises a clear unavailable error.
Declaring it is a separate, deliberate change and is not part of this one.

## Not covered here

Launching and stopping the proxy from the orama start script, peer-side
verification (`PEER_CA_FILE` and pins), a shared CA and mTLS belong to the
other Track B steps.
