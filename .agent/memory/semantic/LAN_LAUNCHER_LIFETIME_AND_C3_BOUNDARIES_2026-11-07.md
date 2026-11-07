# LAN Launcher Lifetime and C3 Boundaries

Author/actor: codex-reviewer; identity_verified: false. Takeover: none.
Scope: verified local observations and authenticated receiver readback, not fleet
consent, native Windows qualification, C3 completion or serving authorization.

## Verified Chronicle

- Orama PR478 production CA repair b63f3625 reads a single certificate once,
  verifies its DER fingerprint and builds trust from those same bytes. Regression
  db16eb6e proves real OpenSSL accepts an additional TRUSTED CERTIFICATE root in
  an unpinned bundle while the pinned loader refuses it. Python3.13.18,
  OpenSSL3.5.9; combined focused suite79passed. Inline reply4500491073 cites
  the production fix and regression separately; the existing thread is resolved.
- Startup safety commit a5730db0 adds explicit controls for outbox auto-flush
  and research auto-dispatch. A single authorized push published both commits
  to existing PR478 at db16eb6e. No new PR, merge or force-push was performed.
- A tool-run launcher briefly started PT8000, Orama8001, Portal8002 and TLS8443,
  but its children disappeared when the command runner exited. User-authorized
  v1 restoration was moved under a user launchd job. The fixed launcher exited
  successfully; services remained listening afterward. Portal stayed loopback;
  Caddy exposed HTTPS only. Existing CA and credentials were unchanged.
- Local CA-verified HTTPS health200, unauthenticated inbox401 and authenticated
  inbox200 passed. These are local checks, not an independent remote receipt.
  Research dispatch and bulk outbox flushing stayed disabled for restoration.
- Windows received full packet `2026-11-07-c3abc-full-source-packet.md` once:
  116116bytes, rawSHA256
  `aa19a7b6829df2aea2890706f70b65ca12830370fe88372800456c08f630e668`.
  Authenticated receiver readback matched exactly. The packet contains seven
  canonical source documents, their commit/hash manifest and ordered checklist.
  A Mac-only interpreter assignment is explicitly marked as a portable derived
  transformation; source and delivered hashes are both retained.
- Windows also received the targeted restoration/receipt request:2114bytes,
  rawSHA256 `e409adbffad9f71e13097bec17ad8ac2e1425c48bed43262fc116aa10518944b`.
  Individual agent acknowledgements and independent reverse receipts remained
  pending. No old canary or historical ambiguous backlog was resent.
- Core's new opt-in header module passed60focused tests. Phylax's local registry
  verifier passed the full1015test suite with1skip and92.70percent total statement
  coverage. Controller integration reached216passing tests before subsequent
  hardening. Those counts refer to intermediate local states, not final heads.
- Review reproduced a registry-removal race between capability verification and
  the write transaction. A fresh local-registry check was added before locked
  task/idempotency lookup. A separate regression caught unknown nested outbox
  fields accepted after recomputing a plain hash; recursive allowlist validation
  was added. Final integration and exact-head review remained open at recording.

## Reusable Domain Knowledge

1. A successful launcher exit and an open port observed during that command do
   not prove persistent service lifetime. Verify again after the parent runner
   exits. Use the platform service owner, preserving the explicit stop path.
   A one-shot launchd submission survives the runner, not necessarily a reboot;
   reboot persistence requires a separately reviewed service installation.
2. Scheduler installation, one-shot dispatch, background research watchers and
   outbox flushing are distinct side effects. Disabling a scheduler does not
   disable the other three. Listener restoration must explicitly select them.
3. A public CA path may change or contain several files. Validate the configured
   chain and use the already approved pin; never promote a newly observed pin
   from an inbox message into trust. File-byte hashes and DER fingerprints are
   different evidence. Child clients must receive the normalized pin too.
4. Tests must not infer that familiar service ports are unused. Give fixtures
   isolated ports and state; a production listener can otherwise turn a negative
   startup test into a false success. Do not stop live services to make tests pass.
5. A matching plain digest detects accidental alteration, not an authenticated
   source. Enforce nested field allowlists independently before observability
   export. Gossip observations remain separate from authoritative claim state.
6. Capability decisions are point-in-time observations. Recheck the current
   trusted local registry at the write boundary; do not perform remote calls
   while holding the SQLite writer lock. No topology or event creates authority.
7. Preserve three distinct delivery claims: sender attempted, authenticated
   receiver readback matched, and an independent receiving agent acknowledged.
   Only the second was established for these two packets. A blank summary or a
   successful file POST is not proof of every agent's agreement.

## Pending Gates

The accepted C6 Mac tree and receipt remain unchanged. New C3 work requires its
own exact-tree verification; Windows, longer-run confidence, operator new-head
C3d acceptance, publication and activation are separate. Three additional
PR478 review repairs are local follow-up work after the authorized single push;
do not describe them as published until a verified remote commit includes them.
