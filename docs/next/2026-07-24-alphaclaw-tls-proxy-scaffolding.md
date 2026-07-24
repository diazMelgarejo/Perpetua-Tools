# AlphaClaw TLS Proxy — Wired Into PT's Gateway Resolution (companion to orama-system PR)

**Status:** **v1 complete and working** — opt-in via `ALPHACLAW_TLS_ENABLED`;
PR [#276](https://github.com/diazMelgarejo/Perpetua-Tools/pull/276) open for
review/merge. Deferred v2 items below remain deferred.
**Stage:** implementation done → **PR review / merge** (not scaffolding).
**Last re-verified:** 2026-07-24 (pytest green on this machine).
**Date:** 2026-07-24 (scaffolding), updated same day (full wiring), re-verified
2026-07-24 (stage + Slowloris hardening committed locally).
**Branch:** `security/alphaclaw-tls-proxy-scaffold` (PR #276)
**Companion orama-system PR:** `security/02-peer-mesh-auth-tls-v2-plan`
(stacked on PR #197), which ingests 3 security-hardening design docs and
records the full plan canonically at
[`orama-system/docs/v2/49-peer-mesh-auth-tls-v2-plan.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/49-peer-mesh-auth-tls-v2-plan.md)
(once merged; branch link until then).

## Is it working? (2026-07-24)

**Yes — when explicitly enabled.** `ALPHACLAW_TLS_ENABLED` defaults off; with
it unset, `bootstrap_alphaclaw()` keeps plain `http://` gateway URLs (by design).

| Check | Result |
|---|---|
| `pytest tests/test_alphaclaw_tls_proxy.py` | **9/9 passed** |
| `pytest tests/test_alphaclaw_manager_tls_wiring.py` | **12/12 passed** |
| Cert persistence + TOFU pinning | Covered by proxy tests |
| `bootstrap_alphaclaw()` → `https://` when env on | Covered by wiring tests |
| TLS failure → graceful HTTP fallback | Covered by wiring tests |
| Malformed chunked body → HTTP 400 | Covered (review follow-up, on branch) |
| Stalled-client / Slowloris mitigation | `3bb36c8a` — on origin as of 2026-07-24 |

**Not live-validated here:** a running AlphaClaw process with
`ALPHACLAW_TLS_ENABLED=1` against a real gateway on this machine (unit/e2e
tests use fake upstream servers only). That is the remaining manual smoke
step before calling it "production-ready."

**Tracker:** item-level checklist lives in
`docs/next/2026-07-25-pending-work-tracker.md` §1 (kept in sync with this
note).

## Commit history note (re-verified 2026-07-24)

`3bb36c8a` (Slowloris fix) and `7dd01a76` (identity-audit lessons) are both
on `origin/security/alphaclaw-tls-proxy-scaffold` as of 2026-07-24 — the
prior "local-only, not yet on origin" note above was stale; re-checked via
`git log` against a fresh `git fetch`. `7dd01a76` remains out of TLS scope
(identity-audit memory, not this proxy work) but is harmless riding along on
this branch.

A follow-up commit (`7bed40ea`) qualifies a lesson-wording claim CodeRabbit
flagged on review 4770121389 of PR #276 — also on origin.

## What's next (move along)

1. **Merge PR #276** once review is clean (review 4769478731 and
   4770121389 addressed; re-check for newer rounds).
2. **Manual smoke:** `ALPHACLAW_TLS_ENABLED=1` + real AlphaClaw gateway on
   loopback.
3. **Windows ACL enforcement for cert store** — plan filed at
   [`2026-07-24-plan-windows-acl-alphaclaw-tls-proxy.md`](2026-07-24-plan-windows-acl-alphaclaw-tls-proxy.md),
   not yet implemented. Fixes the deprecated `SetFileSecurity` API the
   original draft's code sample used (its own references already flagged
   the deprecation but the sample hadn't been updated) — replaced with
   `SetNamedSecurityInfo` per current Microsoft guidance.
4. **v2 deferred** (see below): admin-pinned fingerprints, rotation policy,
   mTLS, auto-enable.
5. **Companion orama doc** merges with `security/02-peer-mesh-auth-tls-v2-plan`
   when that stack lands.

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
HTTP-only gateway. Real features, not stubs:

- **Certificate generation + persistence.** A self-signed cert is
  generated once and reused across restarts (regenerated only when
  missing or within 7 days of its 365-day expiry) -- a fresh cert every
  process start would make fingerprint pinning meaningless.
- **TOFU fingerprint pinning.** First start pins the cert's SHA-256
  fingerprint; every subsequent start verifies it hasn't changed, raising
  `AlphaClawCertFingerprintMismatch` (a real MITM-detection signal, never
  silently auto-repinned) if it has.
- **Real TLS termination + forwarding**, verified end-to-end with a
  genuine TLS handshake against a genuine fake-upstream HTTP server.
- **Stalled-client bounds** (2026-07-24): `_ProxyHandler.timeout` wired to
  `proxy_timeout`; `ThreadingTCPServer.daemon_threads = True` so a hung
  handler cannot block `stop()` or process exit (`3bb36c8a`).

`orchestrator/alphaclaw_manager.py` — wired in via
`alphaclaw_tls_enabled()` (env gate, `ALPHACLAW_TLS_ENABLED`, matching
`dangerous_workers.py`'s established truthy-parsing convention) and
`_maybe_wrap_gateway_with_tls()`, called from `bootstrap_alphaclaw()`'s
own success path. This is the **only** place `gateway_url`'s scheme is
ever decided — `AlphaClawState` and `RuntimePayload` both gained
`tls_enabled`/`tls_fingerprint` fields so orama-system can *see* whether
TLS is active, but orama never decides to use it; it only ever reads
whatever PT already resolved. This is the direct, working implementation
of the architecture invariant this whole exercise was about: **PT is
authoritative for gateway discovery, route choice, topology, and
readiness; orama-system makes zero gateway decisions.**

**Why it lives in `orchestrator/`, not a new `packages/` package:** the
original design sketch (in the 3 ingested plan docs) proposed a standalone
`packages/alphaclaw-tls` package. Checking `orchestrator/alphaclaw_manager.py`'s
own docstring first (its explicit architecture invariant, quoted above)
showed that invariant would be violated by a separately-versioned
package -- whether/how to expose AlphaClaw's gateway is exactly the kind
of decision that module already owns exclusively. Reconciled by placing
this module alongside it, and by making `bootstrap_alphaclaw()` itself
the only call site that ever touches `gateway_url`'s scheme.

## What's explicitly NOT done yet (see the orama v2 plan for the full list)

- No admin-pinned fingerprints (`PEER_PINNED_FINGERPRINTS`-style
  pre-seeding) — TOFU-only for now, matching the plan's own v1 scope
- No certificate rotation *policy* beyond the fixed 365-day expiry check
- Not auto-enabled by default (`ALPHACLAW_TLS_ENABLED` opt-in) — matching
  the plan's "existing deployments" answer (v1 warns/opts-in, never
  enforces)
- **Windows ACL enforcement for the cert/key/fingerprint store** — currently
  POSIX-only (`chmod 0o600`/`0o700`); on Windows, `Path.chmod()` only
  toggles the read-only attribute and does not restrict other local users'
  read access. Plan filed:
  [`2026-07-24-plan-windows-acl-alphaclaw-tls-proxy.md`](2026-07-24-plan-windows-acl-alphaclaw-tls-proxy.md)
  (not implemented)
- mTLS, audit logging, the pluggable auth-provider architecture (BUZZ/
  Twitter/Google) — all orama-side and PT-side v2 work tracked in the
  companion doc, not started here
- Peer-mesh bearer-token TLS (the `query_peer_topology.py` side of the
  companion plan) is a separate surface, already landed independently on
  orama PR #197 as its own v1 minimum

## Cross-references (for continuity post-merge)

- Code: `orchestrator/alphaclaw_tls_proxy.py` and
  `orchestrator/alphaclaw_manager.py`'s own module/function docstrings
  point back to this file and the orama plan doc.
- Tests: `tests/test_alphaclaw_tls_proxy.py` (proxy internals: cert
  persistence, fingerprint pinning, real TLS forwarding, stalled-client
  bounds) and
  `tests/test_alphaclaw_manager_tls_wiring.py` (the actual wiring:
  env-gate behavior, no-op cases, real end-to-end gateway_url
  replacement, graceful degradation on failure) both point here.
- orama-system side: `docs/v2/49-peer-mesh-auth-tls-v2-plan.md`'s "MVP
  wiring" section names this exact module by its intended path.
