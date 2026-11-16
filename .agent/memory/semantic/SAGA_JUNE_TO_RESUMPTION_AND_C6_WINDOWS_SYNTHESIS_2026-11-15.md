# The Long Arc: June Co-Orchestration to the C6 Windows Qualification (2026-06-24 to 2026-11-15)

Written 2026-11-15 by the Windows Cline session (win-cline-20261115), self-reported,
from the LAN peer inbox record, the PT .agent/memory corpus, and live evidence runs.
Purpose: the complete narrative plus the durable technical lessons, so a future agent
never has to rediscover why the v2 oramasys surfaces look the way they do.

## Part I - The saga

### Act 1: The co-orchestration founding (June 24-28)

PT memory shows the era's shape: BRANCH_CATALOG_COMPLETE and BRANCH_COMPARISON
(2026-06-27) inventoried every branch; VITEST_TDD_SESSION proved the TDD harness;
CODEX_V142_DISPATCH brought Codex onto Windows; COORDINATED_CYCLE_002 through 019
(06-28 to 06-29) ran the joint Mac/Windows cadence. The June 28 card
(WIN_CO_ORCHESTRATOR_WHERE_TO_LOOK) fixed the platform affinity that still governs us:
Mac = OpenClaw + AlphaClaw + cursor-agent; Windows = Hermes-only + cursor-agent/Codex/AGY.
Rule: no remote agent RPC - coordination is a FILE INBOX (lan_peer_assign.py) plus git
pull on both repos. Joint auth = PT .state token + orama env lanes. Portal / 500 root
cause (orama 435d27a) taught: /health can pass while / fails on a stale process.

### Act 2: Healthy idle and the last July handshake (July 3-8)

win_next_action_2026-07-03: co-orchestration healthy, queues idle, accepting jobs via
broadened win_job_queue.py, awaiting Mac assignment / H6 real-task on Win 27B LM Studio,
cursor standalone validation deferred to 2026-08-02. July 8 (session-transition-fable5):
the cross-platform line-endings fix landed live (.gitattributes eol=lf + renormalize,
verified lossless on both repos) and ClineBot was moved to an isolated detached worktree
after operating in-place on a live checkout caused observed HEAD flicker. The card warns:
do not trust a stale v1 DONE snapshot - re-orient from docs/LESSONS.md first.

### Act 3: The prolonged break (July 3 -> October 23 in the inbox)

The LAN peer inbox record goes silent for 112 days. PT memory proves the break was in
CROSS-HOST COORDINATION ONLY - local Windows work never stopped: July 15-16 agentic-stack
upstream contribution plan and the learn-py manual; July 18 the CLINEPASS DeepSeek Flash
route and privacy-memory opsec cards; July 26 merge10 memory-pipeline proof; July 29-31
commit-clean merge-aware TDD, append-PR-body atomic sync, and the week retrospective that
codified the doctrine: verification has to be real and specific, never assumed. August
continued solo: CI tool-version and gitleaks remediation (08-02), the dispatch-race
deferral postmortem (08-02), vendor-blend upstream retrospective (08-07), interrupted
reasoning recovery (08-10), the oramasys apprentice voice memories (08-10), MCP remote
supply-chain pinning debate (08-22), costguard and SSRF split-identity remediations
(08-23). September: tripwire-telos endpoint security authority (09-10), the cross-repo
gate4 dialer cycle (09-25), PT399-orama366 staged private-range gate (09-26), the three-
day PR404/408/410/413 synthesis (09-30). October opened with containment (10-02), sites
MCP (10-05), lockstep gates and T2 review (10-14), the stacked-PR C2 chronicle (10-18),
clean-rollback preflight (10-19), and the AntiGravity ratification reconciliation
(10-23) which locked the three cryptographic boundaries: P5 human-approval receipts
(consumed atomically, 300 s window), Phylax adjustment grants (Ed25519ph, seed-free,
freshness < 60 s), and E1 dispatch permits (port-injected issuer signer). No new JTI
scheme was needed - server-minted opaque IDs already supply identity.

### Act 4: Resumption (October 23-28)

The inbox wakes on 10-23 with the /gossip skill announcement and the AntiGravity cross-
check. October 25-28 rebuilt the LAN fabric: dual-monarchy launch fixes, peer TLS with
pinned Caddy on 8443, and the four-day recovery synthesis whose spine is: pin types are
not interchangeable (PEM-file hash vs certificate fingerprint vs SPKI fingerprint -
label and verify the exact type); bearer-over-verified-HTTPS stays enforced (a TLS health
result says nothing about bearer agreement); obtain destinations from CURRENT evidence;
retry only explicitly selected durable work; keep operator-only hardware confirmation
separate from software probes; an authenticated CLI session with empty output is not a
completed review.

### Act 5: The November convergence (11-03 to 11-15)

November 4 is the Windows peer recovery chronicle: /api/status took 8-11 s (three serial
phases, a gemini --version launch per request, an AlphaClaw port check per loopback
family) fixed by orama PR 467 (cache CLI versions one hour, parallelize phases); then
the whole stack died - root cause: the stack was started from an agent shell inside the
desktop app's JOB OBJECT which denies breakaway, so an app restart killed every service.
Durable fix (orama PR 468): start.ps1 detects a breakaway-denying job by launching a
suspended child with CREATE_BREAKAWAY_FROM_JOB and relaunches itself through WMI
Win32_Process.Create outside the job; opt-outs ORAMA_START_UPDATE=0, ORAMA_JOB_ESCAPE=0.
Same day: the byte-exact peer-file contract agreed (receivers store received UTF-8 bytes
exactly; sidecar records byte count and SHA-256; receipts report raw and LF-normalized
hashes; Path.write_text turning LF into CRLF was the caught defect). November 6-7:
K1-K4 closure chronicle, the C6 runtime and review chronicle, and the C6/SQLite domain
knowledge card (sqlite3.sqlite_version is the library loaded by that Python, not the
CLI; WAL-reset fix is mainline 3.51.3+; backports need separately checked provenance;
zero failures in 2400 sends gives a 95 percent upper bound near 0.1247 percent, not a
0.1 percent guarantee; agent diagnostics, operator acceptance, native qualification,
deployment and activation are separate evidence states). November 10-11: the Q-SQLITE
census (26 interpreters, floor enforced), the venv upgrade to 3.13.14/3.53.1 with
110/110 L-1a tests, D-0 gate proposals, and the task division. November 13-14: Mac C6
Phase 4 agent-complete (inert smoke 6/6, NOT qualification), the Windows C6 draft review
(topic WINDOWS_C6_PS51_REVIEW_20261114, request-changes), the PS 5.1 encoding question,
and the W&B/Cline identical-prompt probe (Cline 4/4 correct and faster; not a benchmark
score). November 15: under explicit operator authorization the Windows C6 evidence run
executed - and this document's Part II records what it taught.

## Part II - The durable technical weave (v2 oramasys lessons)

### 1. The revocation availability architecture, now proven on two filesystems

The Mac C6 found the cause: the revocation cache write lock was held 0.3-0.6 s by an
in-lock signature pass, so lookups waiting over 100 ms failed closed. The candidate
prepares signatures OUTSIDE the locks and reads via a WAL read-only lookup path. The
2026-11-15 Windows Tier 1 run (stdlib-only, three consecutive passes on NTFS) recorded,
not predicted: single-writer WAL/FULL txn p50 2.7-2.8 ms (APFS 0.86 ms - NTFS is ~3x,
expected); the CURRENT design (write2) with a 300 ms writer hold fails first-try 33/400
(8.2 percent) on NTFS, reproducing the macOS failure mode; the WAL read-only lookup
with hold is 0/400 in all three runs at p95 8.7-9.6 ms against the 60 ms budget. The
architecture is now filesystem-portable evidence, not a macOS anecdote.

### 2. The private-DACL slice and the OWNER RIGHTS invariant (the 2026-11-15 fix)

The oramasys Windows slice (PR 98) refuses any store whose parent lacks a private DACL.
The Tier 3 harness blocker was real and instructive: the harness directories carried a
protected DACL of SYSTEM, Administrators and OWNER RIGHTS (S-1-3-4), and icacls showed no
(I) flags. That is an observation from the tested environment, not a general creation
rule (corrected 2026-11-16, review 5915821862). A directory created with NULL security
attributes inherits the parent's inheritable ACEs and uses the creator token's default
DACL only when none are inherited
([CreateDirectoryW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createdirectoryw)).
The observed ACE set matches CPython 3.13 `os.mkdir(mode=0o700)` on Windows, which
applies the protected DACL `D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)`
([os.mkdir](https://docs.python.org/3/library/os.html#os.mkdir)); the C6 harness creates
its attempt roots with `mkdir(mode=0o700)`
([benchmark_revocation_availability.py](https://github.com/oramasys/oramasys/blob/main/scripts/benchmark_revocation_availability.py)),
so the creation mode is the better-supported cause (reviewer inference). The parent
directory's inheritance settings were not recorded in the run evidence. The former
acl_is_private whitelist {user, SYSTEM, Administrators} rejected S-1-3-4 and therefore
failed closed on every directory created that way. The durable fix classifies
OWNER RIGHTS as OWNER-EQUIVALENT, not foreign: Windows resolves S-1-3-4 to the object
owner at access-check time, and _check_windows_ownership already pins ownership to the
current user, so an OWNER RIGHTS ACE cannot widen access to any principal the owner
check has not admitted. The invariant is now expressible in one sentence: every allow
ACE must belong to the owner (directly or via the OWNER RIGHTS alias), SYSTEM, or
Administrators; deny ACEs always acceptable; unknown ACE forms fail closed. RED tests
were written first (two unit rows in the existing acl-policy table plus a native
Windows regression that creates a tempfile-style root and asserts private_acl passes);
29 passed, 19 skipped after the fix, with the POSIX-only oracle skips intact.
Lesson: when a security predicate fails closed on a DEFAULT shape, classify the shape
before widening anything - here the correct classification was owner-equivalence,
not a mask relaxation or a harness stub.

### 3. NTFS specifics the Mac cannot show

os.replace onto a CLOSED target needed zero retries in 50 attempts; onto an OPEN target
it raises PermissionError winerror 5 - the bounded jittered retry in the slice is
REQUIRED, not optional. Junctions are refused fail-closed by prepare_private_store
(must not be a symlink). 8.3 aliases are present on the volume (disable8dot3=2 default)
so path canonicalization matters. Long paths over 260 chars fail under a plain python
without the longPathAware manifest. Defender exclusion state is not queryable
non-elevated; treat data dirs as NOT excluded.

### 4. Interpreter and runtime truths

Python's sqlite3.sqlite_version is the library LINKED into that interpreter; the CLI
version proves nothing. The Q-SQLITE floor is mainline 3.51.3+ (WAL-reset fix) checked
by receipt (scripts/c6_runtime.py with -I), which also fingerprints compile options and
crypto build hashes. On this host the serving interpreter is CPython 3.13.14 / SQLite
3.53.1 / PyNaCl 1.6.2 / cffi 2.1.1. Every functional interpreter and all 13 worktree
venvs sit at 3.53.1 after the 11-15 compliance sweep; one broken unreferenced 3.14.5
orphan remains undeletable (WinError 5, no admin) and is neutralized.

### 5. Process lifecycle and transport on Windows

Service starts must escape job objects: test breakaway with a suspended child and
CREATE_BREAKAWAY_FROM_JOB, relaunch via WMI Win32_Process.Create with the environment
passed in the startup block. On the tested host, an IPv4-loopback TLS upstream could not
reach the application's --host localhost listener; the exact bind address was not
recorded. This is a host and application observation, not a Windows rule: Windows does
not make localhost IPv6-only, getaddrinfo returns the loopback addresses for it
([getaddrinfo](https://learn.microsoft.com/en-us/windows/win32/api/ws2tcpip/nf-ws2tcpip-getaddrinfo)),
and which one a listener binds depends on the application (corrected 2026-11-16, review
5915821862). PowerShell 5.1 strips quotes in
native-exe arguments. Byte fidelity rules (verified 2026-11-15 on 5.1.26100.9818):
ASCII scripts need no BOM; non-ASCII .ps1 needs a UTF-8 BOM and a real 5.1 parse
(without BOM the same script prints mojibake); process bytes must never pass through
PowerShell redirection (re-encoded to UTF-16LE, 10 bytes became 22) or
Out-File -Encoding utf8 (BOM plus CRLF added, 10 became 16). Peer files are stored
byte-exactly with SHA-256 sidecars, receipts report raw and LF-normalized hashes.

### 6. Governance invariants that held all the way through

Serving stayed OFF in every command this arc; ORAMA_GRANT_SERVING unset. Agent
diagnostics are not operator qualification; a completed refresh is not evidence of send
availability; three consecutive operator passes with controls A/B are the Mac gate and
the Windows native tiers are the separate Windows gate - neither substitutes for the
other (decision D3). Frozen identities bind the evidence: Oramasys f33d809, Phylax
2c11d15; the C6 checklist PR 99 merged into main at 56a68d41. Fixes land as reviewed
slices with RED tests first (Phylax PR 32 killed the top-level fcntl imports by routing
through platform_fs; the 11-15 OWNER RIGHTS fix followed the same shape). Push once,
commit in logical batches, append-only lessons, and never paste a credential into a
commit, lesson, review or board note - an unpublished secret is removed by REPLACING
the commits that contain it, because redaction leaves the patch.

### 7. What remains open after 11-15

Windows Tier 3 p95/p99 numbers await: (a) the OWNER RIGHTS fix reaching main (branch
2026-11-15-001-c6-windows-private-dacl-owner-rights, stacked locally on the merged PR 99
tip, committed but NOT pushed per operator instruction), then (b) the three candidate
runs plus controls under the runbook as the service account. R6, R7, R8 and serving
activation stay separate. The Mac three-pass on the selected interpreter is
operator-held. PR 80 (grant/effect lane) remains open on oramasys and does not contain
the Windows slice; the fix branch touches files disjoint from it and will rebase
trivially when 80 lands.

## Part III - What the PT memory corpus says about all of this

The .agent/memory tree carries this whole arc in three layers: working/ holds 130+
session cards from the June coordinated cycles through today (the CO_ORCHESTRATOR_LAN_PEER
platform-affinity card, the fable5 transition warning against stale snapshots, the July
week retrospective, the August remediation postmortems, the October recovery syntheses,
the November LAN/byte-contract and C6 chronicles); semantic/ holds the graduated domain
knowledge (DOMAIN_KNOWLEDGE, LAN_PEER_TLS_AND_DELIVERY, C6_SQLITE_AND_VERIFIED_FEED,
LAN_COORDINATION_WINDOWS_C6_AND_FLEET_SYNTHESIS, MAC_POSIX_EVIDENCE_AND_LOCK_BOUNDARIES,
BOARD_48H_2026-11-14) plus lessons.jsonl, the append-only graduated record whose entries
are superseded, never edited. The BOARD_48H card also warns: cheaper sessions produced
fluent-but-wrong notes (team_broadcast is not GossipBus; PR 498 called complete before its
review thread was answered; one lesson pasted a live credential and was expunged by
history replacement) - the price of a cheap completion is a second pass that checks the
file, the review thread and the runbook before treating a note as done. This document is
written in that spirit: every number above comes from a file in tasks/c6_run/
evidence-2026-11-15 or a cited memory card, and every governance boundary is stated as
the runbook states it, not as any agent wishes it were.

## Part II addendum (same day, after the fix landed) - Tier 3 measured on native Windows

With the OWNER RIGHTS fix applied (commit ff81c6d, branch
2026-11-15-001-c6-windows-private-dacl-owner-rights, LOCAL ONLY - not pushed per operator
instruction), the harness ran natively end to end. All four cells rc=0. Control A (no
refresh): 2400/2400 sent, 1 first-try unavailable, zero final errors, scheduled p50
73.8 / p95 139.2 / p99 162.8 ms. Three consecutive candidate runs (256 events, 8 senders,
2400 sends, 15 s refresh, separate refresher, retries 2): run1 2400 sent, 1 first-try,
p50 73.9 / p95 138.4 / p99 164.7 ms, refresh lock hold p95 9.95 ms, 3/3 refreshes ok;
run2 2400 sent, 2 first-try, p50 73.6 / p95 139.1 / p99 168.5 ms, hold p95 24.2 ms, 3/3
ok; run3 2400 sent, 0 first-try, p50 73.2 / p95 136.3 / p99 166.7 ms, hold p95 7.4 ms,
3/3 ok. Budgets met: first-attempt unavailability under 0.1 percent (budget 1 percent),
zero final errors (0.1 percent line), refresh p95 about 118 ms (budget 1000 ms), zero
refresh failures, and the zero-hold architecture reproduced on NTFS in the live harness
(Mac hold up to 6.9 ms; Windows hold p95 7.4-24.2 ms). The one budget line exceeded:
scheduled p95 136-139 ms against the 60 ms budget re-ratified from Mac spread (Mac
candidate p95 47.6-57.7 ms); Windows scheduled p99 162-168 ms sits inside the Mac p99
family (132-209 ms) and under the 250 ms p99 budget. Operator decision point: re-ratify
p95 for native Windows scheduling (stable across three runs and the control - a platform
characteristic, not noise) or keep the 60 ms line, on which alone Windows stays
unqualified. Adversarial fail-open suite and service-account context still owed; serving
OFF; R6/R7/R8 unchanged. Gossip note c7f3890fdc9145e893de2f1b44e6879e, pulse
a0ec4fb2428748f8938f7822d4068b9d.
