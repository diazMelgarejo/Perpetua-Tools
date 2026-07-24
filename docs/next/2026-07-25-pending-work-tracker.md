# Pending & Partially-Implemented Work — Perpetua-Tools

**Purpose:** a single place to find every unfinished or partially-landed
plan across recent sessions, so the next agent (human or AI) doesn't have
to reconstruct status from commit archaeology. Cross-linked with
[`orama-system/docs/next/2026-07-25-pending-work-tracker.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/2026-07-25-pending-work-tracker.md)
— check both; several items span both repos.

**Last updated:** 2026-07-25, from the branch each item's code actually
lives on (never a summary written from a different branch — see the
"lessons and action must land on the same branch" rule in `SECURITY.md`).

---

## 1. AlphaClaw TLS proxy — mostly done, small gaps remain

**Branch:** `security/alphaclaw-tls-proxy-scaffold` (PR #276)
**Companion:** orama-system `security/02-peer-mesh-auth-tls-v2-plan`
(stacked on orama PR #197) — canonical design doc:
`orama-system/docs/v2/49-peer-mesh-auth-tls-v2-plan.md`

- [x] Real TLS termination + forwarding (`orchestrator/alphaclaw_tls_proxy.py`)
- [x] Certificate persistence across restarts
- [x] TOFU fingerprint pinning with mismatch detection
- [x] Wired into `alphaclaw_manager.py`'s `bootstrap_alphaclaw()` via
      `_maybe_wrap_gateway_with_tls()`, gated by `ALPHACLAW_TLS_ENABLED`
- [x] Chunked request-body decoding, hop-by-hop response-header stripping,
      streamed (not fully-buffered) response forwarding, configurable timeout
- [x] File permissions (0600/0700) explicit, not umask-dependent
- [x] Previous proxy instance stopped before replacing (no socket/thread leak)
- [x] TLS failures populate the resolved state's `error` field, not just logs
- [ ] **Not started:** admin-pinned fingerprints (`PEER_PINNED_FINGERPRINTS`
      pre-seeding) — TOFU-only today
- [ ] **Not started:** certificate rotation *policy* beyond the fixed
      365-day expiry check
- [ ] **Not started:** mTLS
- [ ] **Not started:** auto-enabling by default — `ALPHACLAW_TLS_ENABLED`
      is opt-in; no auto-detection of fresh-vs-existing install
- [ ] PR #276 itself: open, not yet merged. Review 4769478731's 4 findings
      all addressed; check for newer review rounds before assuming clean.

---

## 2. Identity audit consolidation — Phase 1 only

**Branch:** orama-system `2026-07-19-002-fleet-mesh-oob-fixes` (PR #197)
**Plan doc:** `orama-system/docs/plans/2026-07-24-unified-identity-audit-integrated-plan.md`
**PT impact:** Phase 3 of that plan is a dedicated PT sync PR, not yet opened.

- [x] Phase 1 — `identity-policy.json`, `identity-policy.schema.json`,
      `audit_engine.py` (17 passing tests). Fail-closed, no vendor-domain
      wildcard, no universal bot wildcard, private identities excluded
      from the tracked file.
- [ ] **Not started:** Phase 2 — wire `repo_hygiene.py`, `check_identity.sh`,
      `audit_attribution.sh` through the engine, one consumer at a time
      (plan section 10, Phase 2). Currently these three still run fully
      independent logic; the engine exists but nothing calls it yet.
- [ ] **Not started:** Phase 3 — cross-repo sync into a clean PT checkout,
      a dedicated PT synchronization PR (plan explicitly says NOT PR #276
      — keep that PR's TLS scope focused).
- [ ] **Not started:** Phase 4 — remove the 3 old hardcoded identity lists
      once all consumers are green.
- **For a PT agent picking this up:** nothing to do here yet. Phase 1 must
  land and Phase 2 must be green in orama-system first; Phase 3 is the
  trigger for PT-side work, and it gets its own PR, never bundled into an
  unrelated PT branch.

---

## 3. Peer-mesh TLS + pluggable auth (BUZZ/Twitter/Google) — plan only

**Branch:** orama-system `security/02-peer-mesh-auth-tls-v2-plan`
**Canonical doc:** `orama-system/docs/v2/49-peer-mesh-auth-tls-v2-plan.md`
**PT impact:** none yet — this is entirely orama-side (`src/secure_transport.py`,
`src/peer_cert_manager.py`, `src/auth/`), separate from AlphaClaw's TLS
(item 1 above), which already works.

- [x] v1 minimum: bearer tokens never sent over unauthenticated HTTP, in
      both `query_peer_topology.py` and `lan_peer_assign.py`
- [ ] **Not started:** everything else — see the plan doc's own "Decisions"
      table for the full v1/v2 split, 13 open questions all pre-answered
      but none implemented.

---

## How to use this file

Before starting work referenced here, verify the branch tip matches what's
listed above (branches move) and check for review comments newer than
what's summarized. Update this file's checkboxes in the same commit as
the work that completes them, on the same branch — never a separate
tracking-only commit on a different branch.
