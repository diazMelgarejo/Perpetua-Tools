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

## Still open

- Review and native Windows test of the Mac's receiver PR, then the fixed-receiver receipt.
- The Portal dashboard's restart route still launches with the `localhost` default and a plain
  `Popen`; restart through `start.ps1 --restart-portal` until it is fixed.
- Merges of orama 467 and 468 and of this memory PR are the operator's.

## Lessons recorded

`lesson_e93d89b467e5` (job object), `lesson_56e02b427400` (read the front-end log before
blaming tokens; one CLI launch per hour), `lesson_c7b9ff133ee2` (check both directions; no
listener first), `lesson_9724fce46927` (test breakaway, WMI escape, explicit script path),
`lesson_9de1acef9727` (byte-exact peer files), `lesson_a67ff4fe246d` (localhost is IPv6-only
on Windows), `lesson_730bdf7693ba` (keep the TLS and credential gates during outages).
