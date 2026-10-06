# Sites readiness and authentication boundaries — 2026-10-06 UTC

## Why and authority

The owner approved the reviewed r2 plan to prevent stale assembled code, unsafe local
runtime publication and false claims of authenticated readiness. PT remains the canonical
compiler/schema/store; Orama owns the snapshot, assembly/verifier, preview and HTTP/UI;
Sites owns identity, access, D1 and deployment. All changes stay in v1. Concrete private
identifiers and host paths belong in the off-repo runbook.

## What happened and how it was repaired

- Source was already refreshed, but the deployed migration still created the old history
  index. A fresh production build had not detected this. The new independent verifier
  applies candidate migrations in memory, compares canonical schema/index semantics and
  captures actual store query plans. It rejected the incomplete candidate before the
  follow-up deployment. Drizzle generated an index-only migration without editing history.
- Wrangler configuration lookup is separate from log/registry paths. A disposable child
  with a regular file as synthetic home reproduced the failure; an explicit XDG config
  directory restored readiness. The opt-in launcher preserves the developer's home,
  proxies and CA settings and resolves dependencies from the Site itself.
- Local runtime storage must be ignored and untracked or external. Symlink ancestors and
  D1/config destinations are resolved before checking containment. Fixture records, logs
  and configuration never become source artifacts. Cancellation stops the exact owned
  Worker process group and removes only the runner's disposable state.
- A UI request parsed gateway 401/403 text as JSON before checking status. The shared
  decoder now handles status first and preserves user input. This prevents opaque parser
  errors; it does not repair a platform OAuth/account denial.
- The remote policy already allowed the owner. Reapplying the owner allowlist preserved
  the audience. Anonymous root/history requests were denied and sign-in redirected to
  platform OAuth. Owner login and native plugin invocation remain unverified.
- A fresh review caught metadata `null` acceptance, partial unique-index equivalence,
  runtime alias containment and smoke cancellation gaps. Regression tests now reject
  those cases. SQLite authorization denies disk attachment during read-only verification.

## Durable rules

1. Local validity, exact assembled bytes, migrated schema, terminal deployment, owner
   login, plugin installation and actual authenticated invocation are separate gates.
2. A verifier never assembles or repairs. Candidate SQL cannot attach a disk database.
   Falsy/non-object metadata fails closed; partial indexes cannot replace unconditional
   idempotency-key uniqueness.
3. Local synthetic identity proves local isolation only. Never send it to a hosted Site,
   use service access as owner identity, broaden sharing or replace the Site to get green.
4. Keep old migrations and memory bytes. Append lessons/status corrections; never rewrite
   historical JSONL. This incident adds a new working note; existing episodic and semantic
   corpora are untouched.
5. Preserve the Site's generated plugin and exact returned identifiers. A widget saying
   installed is not sufficient when the platform still exposes no tools or denies login.
6. First-publication rollback must be established before publication. The earlier release
   predated r2 and lacks that evidence. Later code rollback does not undo D1 migrations.
7. A deterministic prompt-contract MCP does not perform model inference or dispatch.

See Orama `docs/v2/references/SITES-READINESS-R2-IMPLEMENTATION-2026-10-06.md` for the
task/gate map. Pending: actual owner OAuth, plugin connection, original-preserving hosted
prepare and separately approved multiuser testing before any sharing.
