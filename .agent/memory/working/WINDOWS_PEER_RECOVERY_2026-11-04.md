# Windows peer recovery — 2026-11-04

Chronicle of the Mac/Windows peer-link outage and its fixes. All times UTC.
No host names, addresses, paths, tokens or fingerprints are recorded here.

## Timeline

1. **Status timeout (late 11-03).** The Mac's authenticated `GET /api/status` to the
   Windows TLS front end timed out. The front end had logged `status=200` after 10.8 s for
   that request. `/api/status` took 8-11 s on Windows: three serial phases (network probes,
   a separate Ollama `/api/ps` probe, synchronous tool checks), a `gemini --version` launch
   (~1.1 s) on every request, and an AlphaClaw port check that spent 1.5 s on each loopback
   address family. Fix: orama PR 467 — CLI `--version` results cached for one hour
   (refresh only on restart or authenticated `POST /api/tools/refresh`), the phases run
   concurrently, and the port check uses one shared budget that also covers name lookup.
   Measured 8.8 s before, 2.3-2.6 s after.
2. **Listener gone (11-04 morning).** The Mac then timed out before TLS. Windows had no
   8443 listener: PT, orama, the Portal and the TLS front end had all died. Firewall rules,
   profile and ARP were fine. The only stack process left was a Portal started with
   `--host localhost`, listening on the IPv6 loopback only, which the IPv4-loopback TLS
   upstream cannot reach.
3. **Root cause.** The stack had been started from an agent shell inside the desktop app's
   job object, which denies breakaway. `spawn_detached` fell back to launching inside the
   job, so the app's restart (an update around 08:58 local) killed every service. Machine
   sleep (02:22-07:47 local) was not the cause. Windows-to-Mac kept working, so the
   asymmetry went unnoticed until the Mac reported it.
4. **Stale code.** The run worktrees were 72-75 commits behind main, which produced a false
   "LM Studio DOWN" in the launcher (fixed on main by an earlier PR).
5. **Recovery.** Run worktrees moved to `origin/main`; the stack relaunched through WMI
   `Win32_Process.Create`, outside the job. Verified over the LAN address with the Windows
   CA: `/health` 200, unauthenticated inbox 401, authenticated inbox 200.
6. **Durable fix.** orama PR 468 — `start.ps1` (service-start modes only) moves clean,
   detached run checkouts that trail `origin/main` to it, probes for a breakaway-denying job
   by actually launching a suspended child with `CREATE_BREAKAWAY_FROM_JOB`, and relaunches
   itself through WMI with the environment passed in the startup block, relaying output and
   exit code. Opt-outs: `ORAMA_START_UPDATE=0`, `ORAMA_JOB_ESCAPE=0`. Verified live from an
   in-job shell: services came up outside the job; LAN checks passed.
7. **Canary and receipt.** The Mac's canary arrived at 01:55:42 with HTTP 200 and was stored
   as 916 bytes; the receiver's metadata recorded 905. The receiver uses `Path.write_text`,
   which turns LF into CRLF on Windows only. Receipt sent with both the stored SHA-256 and the
   LF-normalized SHA-256. Seven more Mac files arrived 02:39:08-02:39:19; the Mac was asked
   to reconcile them against its outbox before sending more.
8. **Convention agreed.** Windows agreed to the Mac's proposal: receivers store the received
   UTF-8 bytes exactly (LF, CRLF and BOM preserved), sidecar metadata records byte count and
   SHA-256, receipts report both hashes. The Mac owns the single orama PR (doc, fix, tests);
   Windows reviews it, runs the tests natively and returns a fresh canary receipt.

9. **Review rounds.** Two Sonnet subagents worked disjoint files on orama 467's follow-ups: stale
   resolver lookups cancelled and capped, the tools-refresh cache clear moved off the event loop,
   refresh rate-limited to 2/min, a fake-clock one-hour test and a resolver-saturation recovery
   test. The fixes were carried up the 467 -> 468 -> 469 stack with merge commits only.
10. **CodeQL on 469.** Three py/path-injection alerts failed the check. They were first answered
    as false positives, then fixed: the containment guard `full_path == base or startswith(...)`
    became a single `startswith(base + os.sep)`; CodeQL then reported no new alerts. The same
    commit accidentally carried a PowerShell module cache (only a public module's command names);
    it was removed in a follow-up commit through the repo's audited deletion override.
11. **469 review follow-ups.** The outbox duplicate check now accepts the exact UTF-8 size, so a
    mixed-ending body can match its byte-exact remote copy. Guard tests for `extra` precedence
    and BOM-preserving `drop` were proven by mutation checks.
12. **Portal Restart route (orama 470).** Windows Portal restarts go through
    `start.ps1 --restart-portal`; direct restarts bind the IPv4 loopback, never `localhost`.
13. **Merged and live.** The operator merged orama 467, 468, 469 and 470. The run checkout was
    moved to main by hand once (the old script could not self-update); an ordinary `start.ps1`
    run from an in-job agent shell then escaped the job through WMI. All four services UP, all
    launchers outside any job, Portal on IPv4 loopback, TLS front end on all interfaces.
    Authenticated `/api/status` over the LAN: 2.4 s (was 10.5 s).
14. **Fixed receiver verified.** A self-test through Windows' own 8443 stored LF, CRLF, BOM and
    mixed-ending files byte-exact. The Mac was asked for one fresh canary so Windows can return
    the fixed-receiver receipt.
16. **Operator restart from main.** After the operator reported all work done, a second ordinary
    `start.ps1` run escaped the job again and brought all four services up. Both run checkouts
    already matched `origin/main` (orama with 467-470; PT unchanged), because the PT memory PR was
    still open, so the update step had nothing to do. LAN checks repeated: `/health` 200, inbox
    401 unauthenticated and 200 authenticated, `/api/status` 2.4 s. A PowerShell 5.1 quoting
    failure in a status query (jq template with embedded quotes) was caught and the check redone.
17. **Waiting on the Mac.** No fresh Mac canary had arrived by then; the inbox held only Windows'
    own self-test files and the canary request. The receipt stays pending, and Windows does not
    claim it from its own self-test.
15. **Attribution.** Windows notes, reviews and PR comments carry the repo's core envelope
    (`agent_id`/`executor_id: claude`, harness, host role, model).

## Still open

- The fixed-receiver canary receipt for the Mac's next canary (raw SHA-256 should now equal the
  source SHA-256).
- Mac backlog delivery after reconciling the seven files received 02:39:08-02:39:19.
- The second Windows node (RTX 5080) is unreachable and has no TLS front end; nothing is queued.
- Merge of this memory PR is the operator's; after it merges, the next `start.ps1` run moves the
  PT run checkout to the new main by itself.

See also `2026-11-04-lan-recovery-byte-contract-and-stack-chronicle.md` (the Mac/Codex view).

## Lessons recorded

`lesson_e93d89b467e5` (job object), `lesson_56e02b427400` (read the front-end log before
blaming tokens; one CLI launch per hour), `lesson_c7b9ff133ee2` (check both directions; no
listener first), `lesson_9724fce46927` (test breakaway, WMI escape, explicit script path),
`lesson_9de1acef9727` (byte-exact peer files), `lesson_a67ff4fe246d` (localhost is IPv6-only
on Windows), `lesson_730bdf7693ba` (keep the TLS and credential gates during outages),
`lesson_6740f3c55485` (CodeQL sanitizer shape), `lesson_32e4248a3949` (stage explicit paths;
stray files removed by follow-up commit), `lesson_ba2f996e4225` (mutation-check guard tests),
`lesson_8c587f1048f7` (revisit size and hash consumers when a storage contract changes),
`lesson_1b7659a17ce7` (merge-commit PR stacks, launcher bootstrap, confirm GitHub writes).
After the operator restart: `lesson_2d8daa78832b` (self-test the receiver through its own front end),
`lesson_887a8c7414b1` (verify remote state before a restart; an open PR means main has not moved),
`lesson_52d2417cf893` (PowerShell 5.1 strips quotes in native-exe arguments such as gh jq templates).
