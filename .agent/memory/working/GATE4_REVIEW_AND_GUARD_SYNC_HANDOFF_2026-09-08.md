# Gate 4 Review and Guard-Sync Handoff

**Recorded:** 2026-09-08
**Scope:** verified Gate 4 review remediation and guard synchronization work
completed in the recent handoff window. This is not a claim about unrelated
fleet activity.

## Confirmed Outcomes

1. PT PR #382 review remediation uses a resolve-once, IP-pinned HTTP transport
   for model-server probes. The configured hostname remains the HTTP Host and
   TLS SNI origin; only the TCP peer is pinned to the classified address.
2. LM Studio credentials are attached only for HTTPS. Cleartext HTTP probes
   omit the bearer token, so a secured endpoint remains unavailable instead of
   receiving a credential over the network.
3. The legacy validation-only resolver API remains compatible for callers that
   do not immediately dial a target. Dialing paths use the richer pinned-target
   representation.
4. The PT lockfile explicitly records the direct `httpcore` runtime dependency
   used by the pinned transport.
5. Orama PR #347 documentation now distinguishes completed prerequisites
   (`oramasys/oramasys` PRs #2 and #3, PT PR #380) from the still-open PT
   Half B implementation PR #382.

## Guard Authority and Synchronization

- `scripts/git/check_file_deletion_guard.sh` is a canonical Orama guard,
  mirrored downstream through the manifest-driven sync tool. It must not be
  hand-edited in PT.
- A PT-side improvement correctly stopped synchronization because its blob was
  newer than canonical history. The safe sequence was: promote the change to
  canonical Orama, add regression tests there, then run the downstream sync.
- The promoted guard disables rename detection while listing deletions, so a
  delete-plus-similar-add pair cannot hide a whole-file deletion. For a
  multi-commit push range, its restoration hint uses the range's left boundary
  rather than `HEAD^`.
- The final canonical-to-PT parity check passed with all manifest guard paths
  byte-identical in the target checkout.

## Verification Evidence

- PT resolver regression suite: 31 passing tests.
- Orama documentation contract suites: 146 passing tests.
- Canonical file-deletion guard suite: 10 passing tests; Bash syntax check
  passed.
- PT dependency lock consistency and diff whitespace checks passed.

## Operational Lessons

1. Before publishing a PR repair, fetch its source branch again. If it advanced
   during review work, rebase a clean local branch and synthesize overlapping
   changes rather than publishing a stale fork.
2. A DNS classification check alone is insufficient: the connection must be
   bound to the address that was classified, while preserving hostname-based
   HTTP and TLS semantics.
3. Guard parity is a content-authority process, not a file-copy operation.
   A divergence failure is evidence to investigate and promote, not permission
   to force a downstream overwrite.
4. Keep mirror synchronization and functional remediation as separate commits
   so reviewers can audit authority provenance independently from behavior.

## Local Commit Map

- PT repair branch: guard mirror synchronization and pinned model-server dial
  remediation are committed locally after rebasing on the latest PR #382 head.
- Orama documentation branch: Gate 4 status reconciliation is committed
  locally after rebasing on the latest PR #347 head.
- Orama canonical guard branch: the deletion-guard promotion and tests are
  committed locally. It must be reviewed and merged before any future
  downstream guard synchronization sourced from `origin/main`.

No branch was pushed by this handoff. Re-check remote PR state, CI, and clean
worktree status before publication.
