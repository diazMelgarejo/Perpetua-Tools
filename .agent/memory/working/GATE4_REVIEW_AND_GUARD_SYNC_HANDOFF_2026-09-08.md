# Gate 4 Review and Guard-Sync Handoff

**Recorded:** 2026-09-08  
**Reconciled:** 2026-09-10  
**Scope:** Gate 4 review remediation, guard synchronization, and the published
PT PR #382 verification boundary. This is not a claim about unrelated fleet
activity.

## Confirmed Outcomes

1. PT PR #382 uses a resolve-once, IP-pinned HTTP transport for model-server
   probes. Regression coverage directly verifies that the request URL retains
   the configured origin hostname and that the HTTP `Host` header retains the
   configured authority while the TCP connection is pinned to the classified
   address. The current fake-pool regression does **not** directly observe
   `server_hostname`, so this handoff does not claim a transport-level TLS SNI
   assertion.
2. LM Studio credentials are attached only for HTTPS. Cleartext HTTP probes
   omit the bearer token, so a secured endpoint remains unavailable instead of
   receiving a credential over the network.
3. The legacy validation-only resolver API remains compatible for callers that
   do not immediately dial a target. Dialing paths use the richer pinned-target
   representation.
4. The PT lockfile explicitly records the direct `httpcore` runtime dependency
   used by the pinned transport.
5. Orama PR #347 documentation distinguishes completed prerequisites
   (`oramasys/oramasys` PRs #2 and #3, PT PR #380) from PT Half B PR #382.

## Guard Authority and Synchronization

- `scripts/git/check_file_deletion_guard.sh` is a canonical Orama guard mirrored
  downstream through the manifest-driven sync tool. PT changes to that mirror
  must be reconciled back to canonical ownership rather than silently diverging.
- The deletion guard disables rename detection before filtering D-status paths,
  so delete-plus-similar-add changes cannot hide whole-file deletion.
- Two-dot restore guidance uses the range's left boundary.
- Triple-dot restore guidance now resolves the actual merge base and omits a
  fabricated restore source when merge-base resolution fails.
- Initial pushes with no remote ref and no usable upstream now scan from Git's
  empty tree to the pushed tip. That covers root, one-commit, and multi-commit
  initial pushes instead of comparing the committed tip against the working
  tree.

## Verification Evidence

The earlier generic "31 passing" resolver count is intentionally superseded by
commands/suites that are traceable to the published PR evidence:

- `pytest -q tests/test_agent_launcher_resolve.py` — 26/26 at the recorded
  implementation verification point.
- `pytest -q tests/test_agent_launcher_resolve.py tests/test_hardware_routing.py`
  — 61/61 at the recorded combined verification point.
- Full PT suite at the recorded implementation head: 2143 passed, one unrelated
  pre-existing isolation flake, five skipped; the isolation flake passed alone.
- Exact-head Git hygiene attribution audit subsequently passed after
  `github-actions[bot]` was added as an explicit Perpetua-Tools repo-scoped bot
  identity; the bot-authored memory commit was preserved without history
  rewriting.

Current Actions status must always be read from the exact PR head before any
completion claim; this handoff records commands and historical evidence rather
than freezing a moving CI status into permanent prose.

## Operational Lessons

1. Before publishing a PR repair, fetch its source branch again. If it advanced
   during review work, rebase a clean local branch and synthesize overlapping
   changes rather than publishing a stale fork.
2. A DNS classification check alone is insufficient: the connection must be
   bound to the address that was classified while the HTTP origin semantics are
   preserved.
3. Guard parity is a content-authority process, not a file-copy operation. A
   divergence failure is evidence to investigate and promote, not permission to
   force a downstream overwrite.
4. Keep mirror synchronization and functional remediation auditable by failure
   class, and re-sweep review threads after every published remediation.
5. Legitimate GitHub automation identities must be explicitly repo-scoped; do
   not replace that with a wildcard `*[bot]` trust rule.

## Published State

- PT PR #382 branch: `gate4/halfb-dialer-adoption-20260907`.
- Durable semantic memory:
  `.agent/memory/semantic/TRIPWIRE_TELOS_ENDPOINT_SECURITY_AUTHORITY_2026-09-10.md`.
- Canonical graduated lesson: `lesson_5efb8cefb8af`.
- Tripwire/Telos coordination board:
  `.agent/memory/working/2026-09-10-tripwire-telos-restoration-coordination-board.md`.
- No merge is authorized by this handoff. Human review remains required.
