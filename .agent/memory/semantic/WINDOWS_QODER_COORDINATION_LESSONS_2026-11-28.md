# Windows Qoder Coordination and Native Verification Lessons

Date: 2026-11-28  
Actor: `qoder-main` (self-reported; `identity_verified=false`)  
Scope: Canary 2, seven-agent consolidation, Windows v4 lanes 7-10, and Qoder lanes 1/2a/2b.  
Path convention: artifact paths below are labels relative to the ultrathink workspace root, not absolute workstation paths.

## Safety and authority boundaries

1. A later explicit process constraint overrides an earlier permission. The instruction "do not stop any" meant no engine, service, worker, or process stop; earlier permission to stop engines was not used.
2. Isolate tests from model engines without changing engine state. Test shells used `OLLAMA_BASE_URL=http://localhost:9`; no engine was started, installed, called, or stopped.
3. Coordination signals are not authorization. A GossipBus message, queue claim, handoff, or LAN file does not grant permission to push, mutate a PR, change trust, activate serving, or cross a closed gate.
4. Preserve secrets by construction. Use dummy bearer values in tests, inspect process arguments for those dummy values, and never print real tokens, credential files, private keys, or environment contents.
5. Never claim a platform pass from a different platform. Windows evidence remains Windows evidence; Mac/POSIX runtime qualification stays open when no POSIX runtime is available.

## Coordination and GossipBus

6. Read both local GossipBus boards and the LAN inbox before dispatch. One host can carry two coordination boards, and a stale HOLD can conflict with a newer operator GO. Reconcile by source, timestamp, version, and explicit operator authority; do not guess.
7. Keep channels distinct. GossipBus is the intra-host event bus, the Job Claims Board is the task-claim ledger, and the LAN peer inbox is a file-transfer channel. A message on one channel is not proof of state or delivery on another.
8. When Mac queue rows are absent from every local replica, do not create duplicate queue tasks. Publish exact task-ID claims through `GossipBus.emit`, state the local absence, and deliver the same exact-ID notice to Mac.
9. Publish substantive `agent_note` events with a paired `agent_pulse`. Include author, actor, endorsement, and takeover provenance; self-reported identity remains `identity_verified=false`.
10. Use `GossipBus.emit`, never direct SQLite inserts into a GossipBus store. Verify each returned UUID with a read-only query before reporting publication.
11. A queued outbox record is not delivery. For direct LAN drops, capture the helper's complete JSON output once: `ok=true`, `received_at`, and a byte count equal to the source file. Receiver-computed SHA-256 is additionally required for a byte-identity claim.
12. Do not tail a send helper's output and then rerun because the result was hidden. Direct drops leave no outbox sidecar, and a second run can duplicate a file that already arrived.

## Worktrees, subagents, and attribution

13. Capture each worktree's branch, pinned base, and pre-existing status before spawning. Keep pre-existing uncommitted changes separate from worker changes; never clean, reset, or overwrite unfamiliar work to make attribution easier.
14. Snapshot interim worker output outside the worktree with byte counts and SHA-256. Label it interim, list final outputs as pending, and do not treat a test-first patch as an implementation receipt.
15. A background subagent has no result until its completion notification arrives. Do not fabricate progress, completion, test counts, or artifact paths while it is running.
16. Verify worker commits by ancestry and content, not by branch name or summary. For Lane 8, `4fead2e` was directly based on `0b07d5a`, exactly one local commit ahead, with four test files and +16/-14; independent replay then passed 105 tests.
17. Freeze the source tree before final verification. Any later tracked edit invalidates earlier full-suite evidence for that head; rerun affected tests and bind receipts to the exact tree.
18. For canary experiments, change one variable at a time, save diffs outside the disposable worktree with SHA-256, restore the tree after each variant, rerun the final baseline, and classify KILLED/SURVIVED/INCONCLUSIVE strictly.

## Native Windows execution

19. Select an existing Windows virtual environment that actually contains the test dependencies. A bare interpreter or unrelated venv can turn missing FastAPI or pytest into misleading product failures; record interpreter, pytest, and dependency versions.
20. Avoid the Windows Store Python stub and unsupported interpreter flags. Verify the executable and version before relying on an edit or test command, and read back a silent tool failure before publishing its output.
21. A POSIX-only import guard is a real platform boundary. The private-authority core raises on non-POSIX hosts; no WSL distribution was installed, so Windows could not supply true POSIX runtime qualification.
22. Windows `st_mode` can report `0o777` where a POSIX test expects `0o700`. Reproduce and document the platform difference instead of weakening the security assertion or calling it a POSIX pass.
23. Windows symlink creation can fail without the required privilege. Keep that qualification gate open and report the exact privilege failure rather than silently skipping the security behavior.
24. Deterministic subprocess tests should launch `sys.executable`, not a hardcoded `python3`, and pass an explicit readiness file instead of inferring readiness from `proc.pid == os.getpid()`.

## Schannel, PowerShell, and secret-safe TLS tests

25. Native Windows curl 8.22.0 uses Schannel. A private test CA can be accepted yet fail revocation checking with exit 60; `--ssl-revoke-best-effort` is a scoped test option, not a production trust waiver.
26. Keep negative TLS cases strict. Mismatched CAs and missing trust must still fail when best-effort revocation is enabled, and root-store fingerprints must be unchanged before and after the test.
27. PowerShell 5.1 source syntax and low-level Windows argument strings are different layers. Preserve `--header '@-'` in PowerShell source, but pass `--header "@-"` through `ProcessStartInfo.Arguments`; literal single quotes in the low-level string prevented curl from reading stdin.
28. Verify the security property, not just process completion. The Lane 7 server checked `auth_matches_dummy`, and both curl and parent PowerShell command lines were inspected to prove the dummy bearer never appeared there.
29. Expected failed TLS handshakes can emit reset noise from the test server. Suppress only expected `ConnectionResetError` and `ssl.SSLError` in the handler so negative tests do not look like harness failures.

## Gates and reporting

30. The newer v4 pack plus explicit operator GO superseded the older v3 HOLD for Windows lanes 7-10. Superseded packs must not be run, and the authority/version reconciliation belongs in the receipt.
31. Lane 3 remains closed until Lane 1 schema review is accepted. Do not enqueue the V1-3 recovery design spec merely because Lanes 1/2a/2b are active.
32. Report independent replays as observed counts, including failures and skips. Do not convert a reproduced Windows failure into a pass, and do not generalize one host's result into fleet qualification.
33. Memory writes under concurrency must preserve existing edits. Inspect the diff first, use the repository's locked append/candidate tools, and never hand-edit rendered `LESSONS.md`.
34. The memory renderer's `fcntl` lock is unavailable on Windows. Treat its warning as a real concurrency limitation: serialize memory-tool invocations, preserve append-only evidence, and do not claim cross-process locking that the host cannot provide.
35. Before sending an interim bundle, list the authenticated remote inbox and filter by exact filename. A local assumption that a file is pending is not remote evidence, and a preflight prevents avoidable duplicate drops.
36. Prefer the supported `lan_peer_send.py` wrapper over a bare drop. It forwards only an environment allowlist, masks addresses and token-like strings, and judges delivery from the drop's own JSON; never open credential files to construct the send environment.
37. Inspect a Python tool's entry point before assuming it supports `--help`. The memory renderer has no argument parser and treated `--help` as an output directory, creating scratch artifacts that had to be removed.
38. Do not pack multiword command arguments into one shell scalar and expand it unquoted. Embedded quote characters can become literal condition values; pass arguments directly or use a real argument array.
39. After batch memory writes, parse every JSONL row, resolve latest-by-ID, verify each new lesson's evidence timestamps and graduated candidate file, and recompute artifact hashes before publishing a memory receipt.
40. A background completion notification is a claim, not verification. Read the returned artifact, confirm its pinned base and stated counts, and inspect relevant source evidence before marking the task complete or updating the consolidated report.
41. When a pending subagent artifact arrives, rebuild the interim manifest and report before delivery. Do not send a stale report that still labels the new artifact as pending.
42. Keep underlying model and inference-provider identity confidential. Persist only the self-reported agent ID, actor instance, endorsement, takeover state, and `identity_verified=false`; runtime identity is not coordination provenance.

## Evidence anchors

- Windows lane 7 reproducer: `wave1-win-20261128-evidence/lane7-tls-verification/verify_lane7_tls.py`, SHA-256 `0790dff0af1887461c2f6dfeedc06d40d2e30facdde3f311e1397d835785baa0`.
- Windows lane 7 summary: `wave1-win-20261128-evidence/lane7-tls-verification/summary.json`, SHA-256 `eb422beb14d04e044caf186a57dde13398c30220d511f4023fd26a61d0f60f63`.
- Lane 8 worker commit: `4fead2e21a76e9357f5358029a89ab20307d3940`, parent `0b07d5ad83d36991e53aaa2d307711dfa418791f`.
- Qoder PT pinned base: `8fd6f2e9bb66787cdeb12c8bb7b187888643a61a`.
- Qoder Orama pinned base: `0b07d5ad83d36991e53aaa2d307711dfa418791f`.
- Interim artifact manifest: `test-tmp/2026-11-28-qoder-interim-artifact-manifest.json`, SHA-256 `da08003bba5f5ba1ecb4f02af6ab05a2b94813b2eedf43ebb15ae8a9c3be60ce`.
- Interim Lane 1 patch: `wave1-win-20261128-evidence/qoder-interim/qoder-lane1-interim.patch`, SHA-256 `f2d1454da3c71fba5fa00a9faac06903bbe37649f354dedb7dab93c5a6f7f067`.

## Open gates at time of writing

- Qoder Lane 1 final implementation receipt and Mac/POSIX runtime qualification.
- Qoder Lane 2a PT caller ledger final receipt.
- Qoder Lane 2b Orama caller ledger final receipt.
- Lane 1 schema review acceptance before Lane 3 V1-3 design work.
- No push, merge, PR mutation, production activation, or fleet qualification is implied by this record.
