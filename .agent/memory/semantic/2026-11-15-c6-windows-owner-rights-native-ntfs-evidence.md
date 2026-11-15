# 2026-11-15 C6 Windows: owner-equivalent OWNER RIGHTS and native NTFS evidence

This card is the Windows C6 fix only. The coordination story is the other
card, `2026-11-15-lan-inbox-working-fleet-deliberate-stop-missing-port.md`.
Serving stayed off. The numbers below were recorded by the Windows C6
session and were not re-run for this card. They are evidence to read, not a
qualification.

## The failure the fix classifies

The oramasys Windows slice refuses any store whose parent lacks a private
DACL. The Tier 3 harness stopped before it could measure. `os.mkdir` with
NULL security attributes gives the child the process token's default DACL:
SYSTEM, Administrators, and OWNER RIGHTS (`S-1-3-4`). It does not inherit
the parent. The old allow list was the current user, SYSTEM, and
Administrators. It rejected `S-1-3-4`, so every plain `mkdir` failed closed.

## The invariant

`private_acl` returns false unless the owner SID is already the current
user. Only then does `acl_is_private` accept an allow ACE for that user,
OWNER RIGHTS, SYSTEM, or Administrators. Deny ACEs stay acceptable. Unknown
ACE forms fail closed.

OWNER RIGHTS is owner-equivalent, not a wider mask. Windows resolves
`S-1-3-4` to whoever owns the object at access-check time. Because ownership
is pinned to the current user before the allow list runs, that ACE cannot
admit a principal the owner check has not already admitted.

The change is commit `ff81c6d` on branch
`2026-11-15-001-c6-windows-private-dacl-owner-rights`, stacked on the merged
checklist at `56a68d41`. It is open as oramasys draft pull request 100. Two
table rows and a native regression were added first: a tempfile-style root
must pass `private_acl`. The session recorded 29 passed and 19 skipped, with
the POSIX-only skips intact.

## What the native run recorded

With that fix, four cells exited 0. Control A, no refresh: 2400 of 2400
sent, 1 first-try unavailable, zero final errors, scheduled p50 73.8 ms,
p95 139.2 ms, p99 162.8 ms. Three candidate runs used 256 events, 8 senders,
2400 sends, a 15-second refresh, a separate refresher, and 2 retries.

| Run | First-try unavailable | Scheduled p50 / p95 / p99 ms | Refresh hold p95 ms |
| --- | --- | --- | --- |
| 1 | 1 | 73.9 / 138.4 / 164.7 | 9.95 |
| 2 | 2 | 73.6 / 139.1 / 168.5 | 24.2 |
| 3 | 0 | 73.2 / 136.3 / 166.7 | 7.4 |

Lines the session reports as met: first-attempt unavailability under 0.1
percent against a 1 percent budget, zero final errors, refresh p95 near
118 ms against a 1000 ms budget, and zero refresh failures. The line not
met: scheduled p95 136-139 ms against the 60 ms budget taken from the Mac
spread. Windows scheduled p99 162-168 ms sits inside the Mac p99 family and
under the 250 ms p99 budget. Re-ratifying the p95 line for native Windows,
or keeping 60 ms and leaving Windows unqualified on that line alone, is an
operator decision.

## NTFS facts this run depends on

An earlier stdlib pass on NTFS recorded single-writer WAL transaction p50
near 2.7 ms, against about 0.86 ms on APFS. The current design with a
300 ms writer hold failed first-try 33 of 400 times on NTFS. The WAL
read-only lookup with the hold was 0 of 400, p95 8.7-9.6 ms, against a
60 ms budget for that lookup.

`os.replace` onto a closed target needed no retries in 50 attempts. Onto an
open target it raises `PermissionError` with Windows error 5, so the bounded
retry stays required. Junctions are refused. 8.3 names are present when
`disable8dot3` is at its default, so canonical paths matter. Paths over 260
characters fail under a Python without the long-path manifest. Defender
exclusion is not queryable without elevation. Treat the data directory as
not excluded.

## What this card does not close

The adversarial fail-open suite and the service-account run are still owed.
R6, R7, R8, and serving activation stay separate. The Mac three-pass on the
selected interpreter is operator-held. A POSIX mode-bit test does not prove
a Windows DACL. This card does not.
