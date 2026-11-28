# Local model loads on 2026-11-28: every occurrence

Recorded at the operator's request. Times are local (UTC+8). One agent session caused all three.

## Occurrences

| Time | Model | Approved by a person | What happened |
|------|-------|----------------------|---------------|
| 06:57:11 | `qwen3.5:9b-mlx`, 8.9 GB files, 16 GB host | A test was asked for; no check that it fitted | Watchdog panic and reboot within about three minutes |
| 12:17:19 | `bge-m3`, 0.69 GB resident | No | A first-run test executed code not yet behind the gate |
| 12:18:50 | `bge-m3`, 0.69 GB resident | No | A run reported as engine-blocked; the new gate approved it |

The operator's verdict on the first unapproved load: very wrong.

## 1. 06:57, the freeze

- Launched a live load about when free memory read 42 percent (about 7 GB) for an 8.9 GB model.
- An earlier test run had not been confirmed finished.
- Evidence: boot time 06:59; panic report says no watchdog check-ins for 90 seconds. The report names
  no process, so the cause rests on timing and memory figures and is not proven.

## 2. 12:17:19, a red test ran real code

- The test was expected to fail. It executed memory-embedding code that did not yet ask the gate.
- The runner pointed one endpoint variable at a dead port. The code reads another, which defaults to
  the local engine.
- Evidence: two embedding requests in the engine log; a vector store written into the worktree.
- Unloaded at 12:17:41.

## 3. 12:18:50, the gate itself loaded it

- The run started at 12:18:47 and was described as unable to reach the engines. That was not checked.
- The block was a fixture in one test directory. The run's first file lives in another directory and
  starts a child process; it is the likely caller.
- The request sequence in the engine log matches the gate's own load call. The gate treated any local
  address as its engine and loaded automatically onto an empty host.
- Found 12:20 in the engine log, run stopped, unloaded at 12:21:22.

## Ruled out

Search tools that also use `bge-m3` did not cause these: the engine logged none of the request type
they use that day. They can still load it directly, without passing the gate.

## Fixes, same day

1. A load needs a person's approval for that model, typed in a terminal, with an expiry.
2. A request for any other local port than the engine's own is refused.
3. While a test runs, the real engines refuse every request, in child processes too.
4. A root `conftest.py` refuses connections to the engine ports for every test directory.
5. The agent's own test runner blocks both ports in a kernel sandbox, verified before use.

After these, a sandboxed run of 84 files (2,066 tests) caused no model start and no model request.

## Still open

- The OpenClaw gateway, gbrain and code-review-graph call engines directly, with no approval.
- A process that writes the approval file itself bypasses the terminal check.
- Windows nodes have no gate probes.
