# Cross-Repository Containment Cycle - 2026-10-02

## Scope

Pre-publication containment hardening for Perpetua-Tools PR #418 and the
matching Orama portal contract work for PR #376.

## Delivered

- PT keeps a registered direct CLI child until its containment annotation is
  durably appended. A failed append cannot reclassify the child as
  `in-process` on a later cleanup.
- PT owns containment cleanup outside the cancelling HTTP request and legacy
  `cancel()` path. A cancellation lifecycle performs at most three annotation
  attempts with a short backoff, and does not begin a duplicate retry cycle
  after the callback-owned cleanup has completed.
- When the durable lifecycle event lacks both containment fields but the
  supervisor still owns a direct child, PT returns `cli` / `unresolved` on the
  cancel response. This is deliberately fail-closed for the portal.
- Orama restores an approval only for `cli` / `verified`,
  `in-process` / `not-applicable`, or a genuine legacy response where both
  fields are absent.
- The Starlette TestClient deprecation was removed by adding the supported
  `httpx2` test dependency without changing application HTTP clients.

## Evidence

| Repository | Commits | Focused verification |
|---|---|---|
| Perpetua-Tools | `d28b1c35`, `a12f2f12`, `33351417`, `305a9661`, `94c65cc0` | `135 passed` |
| Orama | `1f25dd43`, `98232b7d`, `d22c3914`, `609071d5`, `67008f6b` | `54 passed` |

PT pre-commit checks passed for memory records, repository hygiene, script
mode, and episodic append-only rules. The live GossipBus record is
`CONTAINMENT_REMAINS_RESOLVED_20261002`.

## Explicit Deferral

The in-memory jobs-log cache is deferred to v2. It is a scale and event-loop
blocking concern, but it is not required to make the v1 containment contract
safe. Do not fold it into the PR #418 containment fix.

## Publication Order

Push PT PR #418 first, then push Orama PR #376. Re-run the focused suites and
inspect the remote branch tips before publication.
