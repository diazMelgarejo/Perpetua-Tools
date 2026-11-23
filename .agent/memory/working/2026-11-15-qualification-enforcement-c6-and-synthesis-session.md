# Session chronicle 2026-11-15 - qualification enforcement, C6 Windows evidence, CI synthesis

Actor: win-cline-20261115 (Windows Cline session). Self-reported, identity_verified=false.
Evidence and status only; not an approval to merge or deploy. Serving OFF all day; lanes UNQUALIFIED pending operator gates.

## Timeline (all verified unless marked U)

1. Q-SQLITE compliance sweep COMPLETE: every functional Python bundle at SQLite 3.53.1 (floor 3.51.3). PT venv rebuilt 3.13.14/3.53.1 with 110/110 L-1a + coordination tests; cpython-3.14.7 installed (3.53.1); cpython-3.12.13 (3.50.4) uninstalled; 13 worktree venvs compliant; no Program Files Python. One unreferenced broken 3.14.5 orphan remains undeletable (WinError 5, no admin) and is neutralized. Local work committed in three batches, pushed once per remote (7 branches).
2. /gossip all + LAN two-way reconcile: 322 items (4 local notes, 314 inbox items, 4 outbox drops).
3. C6 Windows qualification evidence run (operator-authorized), evidence in tasks/c6_run/evidence-2026-11-15/:
   - Tier 0 runtime receipt PASS (3.13.14 / SQLite 3.53.1 / PyNaCl 1.6.2 / cffi 2.1.1, Windows 11 26200).
   - Tier 1 stdlib lock experiment x3 on NTFS PASS: WAL read-only lookup with 300 ms writer hold 0/400 first-try failures in all runs, p95 8.7-9.6 ms (budget 60 ms); current-design failure mode reproduces (8.2 percent with hold) exactly as on APFS.
   - Tier 2 import confirmation PASS at frozen pins Oramasys f33d809 / Phylax 2c11d15: revocation_publication, dispatch_retention, platform_fs and the benchmark harness all import on Windows (fcntl blocker from 1d2f2bb fixed; both remaining fcntl uses guarded; no stubbing).
   - Tier 3 BLOCKED by a new finding: the harness directories carried a protected DACL of SYSTEM, Administrators and OWNER RIGHTS S-1-3-4 with no inherited ACEs (observed in this test environment only; parent inheritance state not recorded); acl_is_private rejected S-1-3-4 so every harness cell refused pre-measurement. Corrected 2026-11-16 (review 5915346045): a directory created with NULL security attributes may inherit the parent's inheritable ACEs and uses the token default DACL only when none are inherited; this ACE set matches CPython 3.13 `os.mkdir(mode=0o700)` on Windows, which the harness uses ([benchmark_revocation_availability.py](https://github.com/oramasys/oramasys/blob/main/scripts/benchmark_revocation_availability.py)), so the creation mode is the better-supported cause. The fail-closed private_store slice worked as designed.
   - DURABLE FIX (oramasys PR 100, draft, stacked on merged PR 99): OWNER RIGHTS classified owner-equivalent - Windows resolves S-1-3-4 to the object owner at access-check time and ownership is already pinned to the current user. RED-first tests (two policy-table rows + native Windows regression); 34 passed / 21 skipped. Follow-up: the native regression moved to tests/windows/ per the f6295a1 isolation pattern (oracle skip allowance preserved) and gained an elevated-runner skip after GitHub windows-latest failed it (default owner is Administrators there).
   - Post-fix native harness end to end: control A + three candidates all 2400/2400 sent, zero final errors, first-try 0-2 of 2400, refresh lock hold p95 7.4-24.2 ms (zero-hold architecture reproduced on NTFS), refreshes 9/9 ok. Only scheduled p95 (136-139 ms) exceeds the 60 ms budget ratified from Mac spread; p99 162-168 ms sits inside the Mac p99 family and under the 250 ms budget. OPERATOR DECISION POINT: re-ratify p95 for native Windows or keep 60 ms.
   - PS 5.1 encoding rules confirmed empirically on 5.1.26100.9818 (all three): ASCII needs no BOM; non-ASCII needs UTF-8 BOM + real 5.1 parse; process bytes must never pass PowerShell redirection (UTF-16LE re-encode, 10 bytes to 22) or Out-File utf8 (BOM+CRLF, 10 to 16).
   - NTFS specifics: os.replace onto an OPEN target raises winerror 5 (bounded retry REQUIRED); junctions refused fail-closed; 8.3 aliases present.
4. PR 508 (orama-system) MERGED as 0e6fdb1: contains the port-fidelity fix (b8763ca), models_port (90108d9), stale test expectations (4b92735), RECOVERY_SOURCE_TXT redirect (2f490f0), and the route-mechanics policy isolation. CodeRabbit review round triaged: 9 inline already fixed by the PR (SHAs mapped and replied inline), 2 outside-diff fixed.
5. PR 509 and PR 511 RETIRED at operator direction after classification: PR 511 fully superseded (its assertion fix = merged 4b92735); PR 509 absorbed into the SYNTHESIS PR 516.
6. SYNTHESIS PR 516 (trial branch fix/ci-pip-install-retry-synthesis, built on main in a worktree): one shared env-tunable pip_install_retry helper (linear per-attempt backoff) applied to ALL 6 pip call sites in [scripts/ci/run_agent_security_scans.sh](https://github.com/diazMelgarejo/orama-system/blob/main/scripts/ci/run_agent_security_scans.sh) - the call-site census found 4 uncovered sites neither fix touched (skill-scanner and mcp-scanner upgrade + package installs). Verified: bash -n clean, smoke test (recovery on third attempt, env-tunable attempts, backoff logs), workflow suite 12 passed / 1 skipped. CI: 31 checks settled ALL GREEN (30 SUCCESS, 1 skipped, 1 neutral, 0 failures). Full report: [SYNTHESIS-REPORT-CI-PIP-RETRY-2026-11-15-CROSSLINKED.md](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/.agent/memory/semantic/SYNTHESIS-REPORT-CI-PIP-RETRY-2026-11-15-CROSSLINKED.md) (in-repository copy; counts corrected 2026-11-16 from 8 and 5).
7. PT #510 review P1 CLOSED on this branch (PR 514): the free-first qualification gate is now enforced in the production candidate path. Round 1: _resolve_candidates consults candidate_dispatch_allowed for catalog-listed candidates; blocked candidates excluded from resolved AND the probe-failure fallback; 503 on fully gated-out chain; autoresearch keeps needs_user_action; uncataloged candidates keep registry trust rules; no caller-settable dispatch_mode; policy read per request. Round 2 (second review): P1 fail-open fixed - _load_policy_snapshot returns (policy, reason), handler loads ONE validated snapshot BEFORE route assembly and refuses 503 on failure, sharing it with ModelRegistry.route_task via a new additive keyword-only policy argument (registry re-reads only for legacy callers); P2 fixed - gate-denied candidates skip the availability probe entirely. Failing-first regressions in tests/test_production_qualification_gate.py (9 tests total). 137 passed / 0 failed across eight suites.
8. Saga synthesis written to semantic/SAGA_JUNE_TO_RESUMPTION_AND_C6_WINDOWS_SYNTHESIS_2026-11-15.md (committed 2e0b299a) and published to the board and LAN.
9. Broadcasts: full-day state broadcast (LAN 2026-11-15-win-cline-broadcast-all.md + board), synthesis report broadcast (LAN 2026-11-15-win-cline-synthesis-report-ci-pip-retry.md full report + board full text).

## Remaining owner-held

- Live provider qualification for the free-first lane, then set qualification_status=qualified and open the lane in bigmodel-free-first-policy.json (the code path now enforces whatever the catalog says).
- Native Windows scheduled p95 budget decision (re-ratify vs keep 60 ms).
- oramasys PR 100 review; adversarial fail-open suite + service-account context for full Windows C6; R6-R8.
- PR 514 review and merge (this branch).

## Dated correction (2026-11-16, append-only)

The timeline above is preserved as written. Live state checked 2026-11-16:

- [oramasys PR 100](https://github.com/oramasys/oramasys/pull/100) is MERGED (2026-11-15 20:33
  UTC, head `64afce32`, merge `4ecdfef8`), not draft. Its native-private-store jobs ran on
  `64afce32` and passed on 3.11, 3.12 and 3.13.
- [Perpetua-Tools PR 514](https://github.com/diazMelgarejo/Perpetua-Tools/pull/514) is MERGED
  (2026-11-15 19:52 UTC, head `250d079c`, merge `5bca2748`); the "PR 514 review and merge"
  owner-held item is done.
- Native Windows scheduled p95 budget: the operator decided 150 ms for native Windows only on
  2026-11-16. Mac and POSIX keep 60 ms (ratified 2026-11-07 in the oramasys budget proposal).
  The value is provisional until re-measured in the service-account context, and it qualifies
  no run.
- Still open: the adversarial fail-open suite's native Windows cases and the service-account
  context run (Windows-held), the live free-first provider qualification (needs a bounded,
  approved run), and R6-R8.

## Decision lookup and receipt reconciliation (2026-11-23, append-only)

- Consult the dated operator decision above before asking again or forwarding a
  generic 60 ms summary. Native Windows scheduled p95 is provisional at 150 ms;
  successful-send p95 stays 60 ms and scheduled p99 stays 250 ms. A historical
  measurement below the provisional value is not service-account qualification.
  The evidence-only correction sent to Windows supersedes the conflicting metric
  language in the November 23 coordination notes. It authorizes no new run.
- The historical 87 was a cumulative Mac-to-Windows sender count, not the
  separate 47-row Windows sender index. Current authenticated Windows inbox
  readback found all 87 filenames: 25 exact bodies and 62 matching only after
  CRLF-to-LF normalization. Report current text presence separately from raw
  receipt evidence, historical arrival, and ownership. Do not replay these items.

## Chronology of the Windows scheduled p95 budget (2026-11-23, append-only)

Both limits below were decided on their dates and neither is invalid. This is development through
time, not a supersession of the earlier record.

| Date | Source | Native Windows scheduled p95 |
| --- | --- | --- |
| 2026-11-08 | Windows dry-run handoff (`docs/next/windows-dryrun-20261108/HANDOFF.md`) | 60 ms |
| 2026-11-16 | Operator decision, recorded above | 150 ms, provisional |

The 2026-11-16 decision is the later one and the current policy for native Windows scheduled p95,
service-account runs included. The handoff is a dated record and stays unedited; its 60 ms is
still the figure for Mac and POSIX (ratified 2026-11-07). Successful-send p95 (60 ms) and
scheduled p99 (250 ms) are the same in both. The 150 ms value stays provisional until it is
re-measured in the service-account context, and it qualifies no run.
