# SQLite, Verified Feeds and Qualification Evidence

Verified reference facts as of 2026-11-07. Author/actor: codex-reviewer,
self-reported; Claude's C6 controls/profile and independent agent review are
attributed in `working/2026-11-07-c6-runtime-and-review-chronicle.md`.

## Runtime Identity and Durability

- Python's `sqlite3.sqlite_version` is the library loaded by that Python,
  not the separately installed SQLite CLI. Python patch versions alone do not
  determine that library; distributor, platform and build matter.
- WAL-reset fix: mainline SQLite 3.51.3 and later; official backports 3.44.6
  and 3.50.7 require separately checked provenance. A minimum-version gate and
  an exact comparison fingerprint serve different purposes.
- The verified C6 distribution was Python 3.13.18 with SQLite 3.53.1. This is
  dated evidence, not a permanent instruction to choose that exact build.
- WAL allows one writer per database and is not collective cross-database
  atomicity. Busy handling may be bypassed to avoid deadlock. FULL versus NORMAL
  changes power-loss durability; a faster result is not automatically an
  equivalent safety contract.
- The v2 attempt store already enables WAL, so actual-serving-interpreter
  SQLite evidence belongs to C7/C8 on BOTH platforms, not just C6 setup.

Sources: [WAL and its reset fix](https://www.sqlite.org/wal.html#the_wal_reset_bug),
[transactions](https://www.sqlite.org/lang_transaction.html),
[busy handler](https://www.sqlite.org/c3ref/busy_handler.html),
[synchronous pragma](https://www.sqlite.org/pragma.html#pragma_synchronous).

## Trusted Verification Boundaries

- A successful event-signature check is reusable only for the same event
  domain, issuer, key identifier, actual public-key bytes, digest and signature.
  It does not itself establish current trust, freshness or authorization.
- The existing store verifier port is trusted code. A private prepared memo
  is not a deserializable capability token or a new public verified authority.
- Per-event sampling of its own key is linear work; sampling every signing
  key for every event creates N-times-K work inside the lock. Whole-snapshot
  trust checks still apply at preparation/publication boundaries.
- Observed missing/changed/unavailable trust must refuse the current operation.
  Samples cannot detect an unobservable change-and-restore between samples or
  establish an external atomic trust-generation epoch.
- Ordered acknowledgement and freshness commits form a safety protocol across
  files: after interruption, committed denials may lead freshness, never the
  reverse. Clock consolidation must preserve durable observations on refusals,
  including errors first detected during outside-lock prewarm.

## Measurement Is Not Approval

- Sleep-after-service traffic hides queue delay. Absolute schedules and all
  outcomes distinguish scheduled, queue and service latency and achieved rate.
- A completed refresh alone is not evidence of acceptable send availability.
  Direct writer-hold spans explain the bottleneck; cold and steady refreshes
  are different populations. Failure/delay samples need sequence and schedule.
- Zero failures/2400 yields a one-sided 95% independent-binomial upper bound
  near 0.1247%, not <=0.1%. Correlated refresh windows further limit inference.
- A Git tree object can freeze an uncommitted candidate without inventing a
  commit SHA. Final commit tree equality binds later publication to that
  measured candidate; any content/dependency change invalidates the binding.
- GitHub PR workflows may test a synthetic merge tree. Run/head/base revisions
  and tree comparison are needed before calling it exact-accepted-head CI.
- Exported trees do not automatically include Git metadata. Git-dependent
  tests need a scratch repository or another explicitly equivalent precondition;
  absent metadata can create false failures unrelated to the candidate.
- Scheduled and successful-call percentiles are different populations; a
  threshold's ratification cannot silently move between them. Repeated samples
  matter: a single passing diagnostic does not negate an independent failure.
- Agent diagnostics, operator acceptance, native host qualification, deployment
  and activation are separate evidence states. Fresh GitHub login establishes
  procedural account control, not independent review or a second-factor proof.

## Qualification Tooling and Delegated Execution

- A measured virtual environment may intentionally have no pip. Inventory it
  read-only with a tool targeting the exact interpreter; installing pip during
  qualification changes the dependency fingerprint unnecessarily. The observed
  offline uv inventory byte-matched the earlier receipt without installation.
- `umask` governs new entries, not existing directory permissions. Use fresh,
  exclusive private evidence and temporary directories, reject receipt reuse
  and treat failed receipt writes as failures. Do not silently overwrite an
  earlier stopped or failed attempt.
- Bind the helper and judge as well as the benchmark/runtime digests. Check
  the frozen tree before and after measurement; later logical commits must
  preserve that exact tree. A new commit SHA still needs its own C3d review.
- An operator can explicitly delegate benchmark execution while retaining
  separate receipt acceptance. Preserve the original pending receipt and add
  an acceptance record; execution success alone is not operator approval.
- The generic control judge skipped refresh-count/latency expectations. The
  independent audit therefore checked the refreshing one-sender control too.
  An optional control flag must not erase a control's intended observation.
- The 2026-11-07 operator accepted measured Mac budgets only. This is not
  native Windows qualification, a long-run statistical guarantee, a service
  configuration change, or publication/activation authority.

## Derived Memory and Async Identity

- An opaque topology field does not classify every other string in a payload.
  Nested values and keys can retain legacy labels outside that field.
- Known branch tokens are redacted at token boundaries; larger identifiers
  remain intact. Residual labels in any JSON field withhold derived recall or
  export. Raw append-only history remains node-local and unchanged.
- Producer-ID discovery includes filesystem reads, Git commands and sibling
  collision checks. Thread offload changes scheduling, not identity authority;
  a cached result would remove fresh per-call checks.
- The SQLite connection context manager handles transactions, not connection
  closure. A closing context must enclose it when fixture lifetime matters.

Operational tools remain canonical: native lesson/graduation and episodic
writers, portable-memory hygiene, repository commit wrappers and supported
GossipBus emission. This reference is not operator approval or activation.
