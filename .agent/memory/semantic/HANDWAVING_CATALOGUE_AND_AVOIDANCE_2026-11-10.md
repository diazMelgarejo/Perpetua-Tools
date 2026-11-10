# Hand-waving Catalogue and How to Avoid It (2026-11-10)

Evidence for later agents. Author/actor: Claude Code on the Windows host (self-reported,
identity_verified=false), written at the operator's request after the operator pointed out that
Windows and the Mac peer had both "handwaved" the Cline controller. V = verified directly, P =
peer-reported. This note is a record of our own misses with dates and numbers, not blame. The
operating checklist lives in `.agent/protocols/verify-before-claiming.md`.

## What hand-waving means here

Acting on a belief about a tool, file or result that nobody had checked against the tool itself, and
then reporting the work as done. The belief is usually plausible; the cost is that the check which
would have exposed it takes seconds (`--help`, one live call, a second search).

## The catalogue (all 2026-11-10, same session unless noted)

| # | What was hand-waved | Cheap check that was skipped | What it cost | Evidence |
| --- | --- | --- | --- | --- |
| 1 | The controller called `cline task <prompt>` for months; the lock work kept the call and built on it. The subcommand does not exist on Cline 3.0.49 or later. | One live call, or `cline --help`. The fallback only fires when the gateway is down, so the path was dormant and never exercised. | The Mac's real dry run failed in 0.8 s; one bad call would have wedged the new lock. | P: Mac dry-run message; V: fixed in orama PR 487 |
| 2 | A reviewer finding was answered "done" when only part was done. The Mac wrote that the call used act mode with auto-approve on and asked for a plan flag, a pinned route and a scratch directory. Windows reported the scratch directory and optional pins as done and did not mention the plan flag. | Diff the reply against the reviewer's list item by item. | Cline's own help says a bare prompt starts in act mode with tool auto-approve ON; the controller shipped that way until the help was finally read. | V: Cline 3.0.74 `--help`; fixed in commit e35d950c |
| 3 | "Cline is not installed on Windows" was carried for a day as a fact about the design ("the watcher reports inactive, which is the designed no-op") instead of being checked or asked. | `Get-Command cline` and one question. | Version-qualified claims were impossible; every Cline statement was labelled unverified. | V: install and `cline --version` 3.0.74 |
| 4 | Discovery looked only for `cline.exe`. The npm install ships `cline.cmd`; the obvious fix (use the shim) would pass prompts through cmd.exe, which re-parses metacharacters. | Install the tool and look at what actually lands on disk before writing discovery code. | Discovery would have said "unavailable" after a correct install, or a naive fix would have opened a shell-injection path. | V: live install; fixed in commit ca6895ca |
| 5 | A negative search result was reported as "I could not find the claim". The first pattern said `query string`; the source said `query token`. | A second, differently worded search. | A wrong statement to the peer, corrected one message later. | V: both searches |
| 6 | A queue command was tried against the real, append-only claim board to learn its syntax. | Use `--help` or a throwaway target. | A permanent mistaken entry ("TEST ENTRY") that could only be claimed and closed. | V: board listing |
| 7 | Two append-only jsonl files were merged by union of text conflict markers. A file without a trailing newline glued two JSON rows into one line. | Parse every row after any mechanical merge. | Caught by the parse check before commit. The row-level union that replaced it was itself wrong: it broke the episodic byte-prefix rule (see row 11). | V |
| 8 | "Temperature did not matter" after 3 of 3 exact passes per setting. The follow-up gave 4 of 5 at 0.6 (7 of 8 overall) and a 18.5 to 82.1 s latency spread. | State n next to every rate and re-run before generalising. | The claim was too strong by one failure. | V: follow-up trials |
| 9 | The Mac's "the old call could never have succeeded", "Cline is not installed" and "the diff showed no file changes" were each stated flatly and each needed a later correction. | Qualify by version and date; run the check that produces the sentence before writing it. | Three corrections in one day from one peer. | P: Mac correction messages |
| 10 | A quoted benchmark ranking (MCPB faster) rested on two routes that differed in endpoint, temperature, template and thinking mode. | Hold the configuration equal first, or label it descriptive. | A route preference that the source reading showed was an artefact. | V: bundle source |
| 11 | The PT PR stack was called conflict-free after a textual merge simulation only. The repo's own episodic preservation gate (`check_episodic_append_only.py`) was never run, and the row-order union put the Mac records before the previous PR's records, so the gate would have failed once PR 487 merged. | Run the repository's own gate against the pinned base and the fetched head. | CodeRabbit found it; the stack was rebuilt as prior bytes plus own bytes. | V: CodeRabbit finding on PT 489, gate output |

## Live working code now (history above is kept as written)

- Cline command line, plan mode default, safe Windows launch and outcome classification:
  `scripts/cline_autoresearcher.py` (`_cline_argv`, `_cline_launcher`, `dispatch_cline`,
  `_is_pre_send_usage_error`, `dispatch_autoresearcher`) in orama-system PR 487.
- Single-owner backend lock: `scripts/autoresearcher_lock.py` (`BackendLock`, `inspect`,
  `reconcile`) in orama-system PR 487.
- Watcher autostart and stop: the AutoResearcher block in `platform/windows/start.ps1` in
  orama-system PR 488.
- Mac and Cline communication helpers (workspace folder, not in git):
  `tasks/cline-mac-comms/send_to_mac.ps1` and `read_mac_inbox.py`.

## Pattern across the misses

1. Reading our own code or a peer's report instead of running the tool (1, 2, 4, 9). 2. Treating "I
did not see a problem" as "there is no problem" (3, 5). 3. A summary line that is shorter than the
list it summarises (2). 4. Experimenting on a real, irreversible target (6). 5. A check existed and
was cheap, but only the reviewer's or the tool's output forced it (1, 2, 4, 7).

## How to avoid it (short form; the protocol file has the checklist)

- First-contact check: before writing code around a tool, run its version and help output and record
  the defaults that matter (mode, approvals, working directory, network, cost).

- Default-danger scan: list every default that acts or spends, then override or explicitly accept
  it.

- Exercise dormant paths: code that only runs on a rare condition gets one live call or an UNTESTED
  label with a queued task.

- Findings ledger: copy a reviewer's N findings into a checklist, answer each with done / not done /
  disagree plus evidence, and compare the reply to the original list before sending.

- Search twice: a negative result needs two differently worded searches and the patterns named.

- Cite the proof for "not installed": the command and its output, or ask.

- Probe on throwaway targets, never on append-only state.

- Validate after mechanical merges: parse every row, rerun renderers.

- Every rate carries its n, scope and date; every U gets a next action.
