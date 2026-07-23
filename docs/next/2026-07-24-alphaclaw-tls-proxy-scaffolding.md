# AlphaClaw TLS Proxy — Minimum Scaffolding (companion to orama-system PR)

**Status:** minimum scaffolding landed; full plan deferred.
**Date:** 2026-07-24
**Companion orama-system PR:** `security/02-peer-mesh-auth-tls-v2-plan`
(stacked on PR #197), which ingests 3 security-hardening design docs and
records the full plan canonically at
[`orama-system/docs/v2/49-peer-mesh-auth-tls-v2-plan.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/49-peer-mesh-auth-tls-v2-plan.md)
(once merged; branch link until then).

This note is intentionally NOT a new ADR — per `docs/adr/ADR-004`'s own
header, PT's ADR files are generated pointers to orama-system's canonical
`docs/v2/` collection (zero-fragmentation doctrine: one source of truth,
not a parallel PT-side design doc). The full architecture decision lives
in the orama doc above; this file is a working note for the PT-side
implementation only, until/unless the orama doc's own maintainers decide
this warrants a synced ADR pointer.

## What landed here

`orchestrator/alphaclaw_tls_proxy.py` — a local-only (127.0.0.1-bound)
HTTPS reverse proxy that terminates TLS in front of AlphaClaw's existing
HTTP-only gateway, generating a fresh self-signed certificate per run.
Verified end-to-end with a real TLS handshake against a real fake-upstream
HTTP server (`tests/test_alphaclaw_tls_proxy.py`), not just unit-level
mocking.

**Why it lives in `orchestrator/`, not a new `packages/` package:** the
original design sketch (in the 3 ingested plan docs) proposed a standalone
`packages/alphaclaw-tls` package. Checking `orchestrator/alphaclaw_manager.py`'s
own docstring first (its explicit architecture invariant: "PT is
authoritative for gateway discovery, route choice, topology, and
readiness... orama-system makes zero gateway decisions") showed that
invariant would be violated by a separately-versioned package — whether
to run TLS in front of AlphaClaw is exactly the kind of gateway-management
decision that module already owns. Reconciled by placing this module
alongside it instead.

## What's explicitly NOT done yet (see the orama v2 plan for the full list)

- No fingerprint pinning / TOFU persistence across runs (fresh cert every
  process start right now)
- Not wired into `AlphaClawState.gateway_url` / the `--resolve` flow --
  `AlphaClawTlsProxy` is a standalone class today; a caller must construct
  and start it explicitly. Wiring it into the default resolve path is
  deferred, matching the orama plan's own "v1 minimum, not full rollout"
  scope for this PR.
- No certificate rotation policy
- mTLS, audit logging, the pluggable auth-provider architecture (BUZZ/
  Twitter/Google) — all orama-side and PT-side v2 work tracked in the
  companion doc, not started here

## Cross-references (for continuity post-merge)

- Code: `orchestrator/alphaclaw_tls_proxy.py`'s own module docstring
  points back to this file and the orama plan doc.
- Tests: `tests/test_alphaclaw_tls_proxy.py`'s module docstring does the same.
- orama-system side: `docs/v2/49-peer-mesh-auth-tls-v2-plan.md`'s "MVP
  wiring" section names this exact module by its intended path.
