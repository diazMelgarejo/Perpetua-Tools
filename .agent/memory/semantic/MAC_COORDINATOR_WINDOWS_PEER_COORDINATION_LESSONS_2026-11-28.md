# macOS Coordinator & Windows Peer Coordination Lessons

Date: 2026-11-28  
Actor: Agnes (Antigravity Coordinator, macOS aarch64)  
Peers: Windows Primary (`win-peer-portal`), claude-sonnet-5-5 (Local Reviewer)  
Scope: Canary 2, Tasks A1-A4, Lane 5 Hook Classification & LibreSSL, POSIX Lanes 6a/6b.  
Path convention: paths relative to workspace root; sensitive host paths redacted.

## Safety and authority boundaries

1. Single-Push Remediation Doctrine during Review Cycles:
   During multi-agent cross-host review cycles, intermediate commits must never be pushed
   one-by-one to remote branches. Batch all verification receipts, schema amendments, and
   test proofs locally. Push exactly once when all lanes across both Mac and Windows nodes
   have converged. This prevents automated review bots (CodeRabbit, Greptile) from
   re-scanning incomplete diffs and thrashing PR comment threads.

2. Draft PR Isolation:
   Both PRs (orama-system PR #535 and Perpetua-Tools PR #527) must remain in DRAFT state
   throughout development and cross-host testing. Draft isolation prevents accidental merge
   triggers, suppresses premature required-check gating, and clearly signals that fleet
   qualification is in progress. Historical PRs (#526 and #534) remain safe and untouched.

3. Ground-Truth Platform Reporting over Handwaving:
   When a test specification prescribes behavior that an underlying OS binary cannot
   physically execute without violating system safety guardrails (e.g. mutating system
   certificates in `/private/etc/ssl/certs`), record the platform limitation honestly as
   UNVERIFIED rather than fudging results or attempting unsafe system modifications.
   Apple LibreSSL 3.3.6 does not support `-no-CAstore` and ignores `SSL_CERT_DIR` for `verify`.
   Rather than claiming a pass, the exact CLI behavior was documented as an honest pack
   limitation.

## Transport and payload integrity across heterogeneous LAN peers

1. Base64 Encoding for Binary Archives over File Drops:
   The file drop helper (`lan_peer_assign.py drop`) reads payload files using
   `read_bytes().decode('utf-8')`. Dropping raw binary files (`.zip`, `.tar.gz`) across HTTP portal
   endpoints causes immediate UTF-8 decoding exceptions or payload truncation. Always
   encode binary archives to base64 (`.zip.base64.txt`) accompanied by a companion markdown
   cover document (`-cover.md`).

2. Dual SHA-256 Integrity Verification:
   Every file drop of an archive bundle must compute and verify two independent SHA-256
   hashes: (1) the binary `.zip` archive SHA-256, and (2) the base64 text payload SHA-256.
   Both hashes must be published in the cover note, recorded on GossipBus, and verified by
   the receiving Windows agent using `certutil -decode` or python `base64.b64decode`.

3. Outbox State and Send Helper Idempotency:
   A drop command that exits 0 with `ok: true`, `received_at`, and matching byte count
   constitutes confirmed delivery. Direct drops do not leave local outbox sidecars once
   delivered; redundant re-sends cause duplicate files in the peer inbox.

## GossipBus and fleet heartbeat protocols

1. Mandatory `agent_note` and `agent_pulse` Pairing:
   Every substantive coordination note (`agent_note`) published to GossipBus must be
   immediately followed by a liveness heartbeat (`agent_pulse`) from the same agent ID.
   Heartbeat monitoring agents evaluate pulse timestamps; unpulsed agents risk being
   flagged as stalled or crashed, causing accidental task takeovers.

2. GossipBus API Invocation Semantics:
   `GossipBus.emit()` expects an event type (`'dispatch'`, `'heartbeat'`) and a dict payload.
   Calling `gb.emit(topic=..., agent_id=...)` raises `TypeError`. Always structure payloads
   cleanly with `'kind'`, `'agent_id'`, `'topic'`, and `'message'`. Never write raw SQLite rows
   directly into `.state/perpetua_core.db`; always use the async `GossipBus.emit()` interface
   to maintain event sequencing and FTS5 search index integrity.

## Worktree lifecycle and multi-repository dependencies

1. Explicit `PYTHONPATH` Bridging in Cross-Repository Tests:
   In modular codebases where repositories depend on sibling submodules (e.g. `oramasys`
   requiring `dispatch_wire` from `phylax`), running tests in isolated or detached worktrees
   fails if only the local package root is on `PYTHONPATH`. Always supply
   `PYTHONPATH=src:sibling_root/src` during test execution to prevent missing module errors.

2. Migration Version Fencing across Divergent Branches:
   Before allocating database migration version numbers for new schema components, inspect
   the actual target branch HEAD. In `oramasys@4b344626`, Migration 2 was already claimed by
   `bounded_claim_replay_v2` (`replay_tokens` table). New reservations must allocate version 3
   or higher to avoid collision with existing migrations.

3. Idempotent Token Replay Semantics:
   On modern controller heads (`4b344626`), `idempotency.receipt_json` no longer stores the raw
   lease token. Attempt 1 delivers the lease token. Attempt 2 retrieves it from
   `replay_tokens` and marks it consumed. Attempt 3+ returns token-free receipts. Test suites
   must respect this consumption state machine rather than expecting perpetual token delivery.

## Hook heuristic quality and true/false positive classification

1. Rule Categorization Discipline for Shell Hooks:
   Hook audit logs must not simply be reported as raw firing counts. Every firing must be
   audited against the executing shell context to categorize True Positives vs False
   Positives. In macOS `shell-gotchas.py`, 12 of 13 rules (49/55 firings) were 100% True
   Positives (e.g., `echo-backslash`, `zsh-unquoted-list-var`, `zsh-reserved-var`). Only
   `secret-file-read` produced False Positives (4 FP / 2 TP) when benign test fixtures
   (`test-ca.pem`) or `.env.local` existence checks were evaluated.
