# Migration-debt, AFRP, and CIDF status — 2026-09-12

**Status timestamp (UTC):** 2026-09-12T05:18:23Z
**Scope:** the verified Tripwire-to-Telos authority restoration, the Agate
hardware-policy remediation, Core graph integrity, Oramasys consumer alignment,
and the operating-procedure correction caused by a stale GitHub-state decision.

This is a working-status record, not a release assertion.  It separates facts
verified from current remote state from pending work and from work that requires
physical hardware.

## Executive status

The code-and-documentation migration deltas named in this program are integrated
into their destination `main` branches.  No new pull request was created during
the final live sweep: every candidate branch either had already been merged or
had no unique delta relative to `main`.  Creating a new PR in that situation
would be duplicate noise rather than progress.

The authority model is now coherent:

| Concern | Sole/current authority | Consumer rule |
| --- | --- | --- |
| Endpoint security (identity, SSRF/DNS rebinding, pinning, redirects, proxy, TLS, endpoint-use authorisation) | `oramasys/telos` | No consumer reimplements a raw network/security path. |
| Application gateway/model-server dialing | Oramasys delegates to `telos.SecureDialer` | Gateway contains no parallel DNS/IP/SSRF/redirect policy. |
| Core discovery health probe | Perpetua Core routes endpoint handling through Telos | The Core branch is now in `main`; do not revive a separate raw `httpx` probe. |
| Hardware detection/selection/model eligibility | `oramasys/agate` | Profiles are data-driven and validated; policy is not duplicated/hardcoded in consumers. |
| Historical v1 evidence and recall | Perpetua-Tools `.agent` memory | PT is evidence/learning authority, not a v2 runtime security dependency. |

## Remote evidence and disposition

| Repository | Evidence | Live disposition at this sweep |
| --- | --- | --- |
| `oramasys/perpetua-core` | `main` is `68420bae…`; its log contains `Merge fix/route-health-probe-through-telos (PR #3 + PR #4) into main`. The former branch `fix/route-health-probe-through-telos` equals that merged history. | No PR possible or needed: zero unique commits/diff versus `main`. |
| `oramasys/oramasys` | [PR #11](https://github.com/oramasys/oramasys/pull/11) merged as `7a3e352…`. It pins the validated Core `717f975…`, tests required `graph_id`, and records the outbound authority ledger. | Integrated. No open migration PR. |
| `oramasys/agate` | [PR #3](https://github.com/oramasys/agate/pull/3) merged. It retains `config/model_hardware_policy.yml` as a documented relative symlink to `src/agate/data/model_hardware_policy.yml`, with regression coverage. | Integrated. No open migration PR. |
| `oramasys/telos` | Main is `b214308…`; prior migration PR #1 merged. | Integrated. No open migration PR. |
| `oramasys/phylax` | Prior migration PR #1 merged. | Integrated. No open migration PR. |
| `oramasys/Claude-Desktop-LLM` | Prior migration PR #1 merged. | Integrated. No open migration PR. |
| `diazMelgarejo/orama-system` | `main` is `39988ce…`, `docs(afrp): require live authority checks before writes (#356)`. | AFRP correction is merged. The only currently open PR found is unrelated Dependabot PR #353. |
| Perpetua-Tools | PT evidence PR #382 is recorded as merged in the current workspace status. | No new migration/debt PR created in this sweep. |

## What changed and why

### 1. Agate owns hardware truth as editable, validated data

The prior risk was divergent, hardcoded profile/model lists and a misleading
top-level policy path.  The implemented direction keeps a portable plaintext
policy dataset under Agate's data directory, validates it in the code path, and
exposes `config/model_hardware_policy.yml` only as a **relative symlink** to the
canonical file.  The README and regression test make the indirection explicit.

This preserves contributor editability while preventing two writable sources of
truth.  Hardware discovery must feed that data-driven policy layer (for example,
portable JSON mappings for shell/Python paths or `systeminformation` when an
installer is Node-based), rather than embedding individual machine names in
consumer code.  Agate remains the future decision authority for supported,
preferred, forbidden, too-large/crashing, and wastefully-small models per
verified hardware profile.

### 2. Validated GraphSpec deserialisation now requires identity

Perpetua Core's validated `GraphSpec.from_dict()` now rejects a missing or
non-string `graph_id`; it computes the identity and rejects a supplied mismatch.
This closes the integrity gap where modified serialized content could otherwise
be accepted as a fresh identity.  Identity-free reconstruction, if ever needed,
must be a deliberately separate trusted path rather than an accidental property
of public validated deserialisation.

Oramasys pins the Core revision containing that rule, has a regression that
removes `graph_id`, and describes the boundary in its outbound-consumer ledger.
The pin does not create a new network authority: it is a graph-integrity
dependency boundary.

### 3. Telos is the restored, unified endpoint-security authority

The migration removed the split/duplicated Tripwire-era ownership assumption.
Telos is the reusable v2 endpoint-security authority; it owns canonical endpoint
processing, SSRF and DNS-rebinding resistance, all-answer resolution, pinned
transport/peer checking, redirect/proxy/TLS restrictions, and purpose
authorisation.  Oramasys's gateway now delegates dialing to `telos.SecureDialer`;
Perpetua Core's discovery probe delegates endpoint handling through Telos.

The migration invariant is stronger than "tests passed": source scans and the
outbound authority ledger must continue to show that consumers contain no
parallel raw HTTP/socket/network-command path.  PT records evidence and lessons
but is not imported as a v2 runtime authority.

### 4. AFRP/CIDF remediation: stale authority is an operational safety defect

The failure prompting this work was an incorrect claim that a new PR would be a
duplicate without first checking live GitHub state: the cited Agate PR had
already merged.  The correct response was not to infer intent from stale memory
or a branch name; it was to query the remote state, classify it, and compare the
exact branch delta against the exact current base.

AFRP is now documented to require a fresh authoritative read immediately before
a consequential remote decision or write.  Its Failure Mode 10 and supporting
references cover:

1. Treat history, cached output, a handoff, or a prior PR lookup as non-authority
   for mutable state.
2. Query PR state, `mergedAt`, base/head ref and SHA, and source repository
   identity; a null/missing/truncated result is not proof that no PR exists.
3. Define duplicates by the exact source repository, head SHA, target/base, and
   remaining semantic delta—not merely a matching branch name.
4. Distinguish open, merged, and closed-unmerged PRs.  After merge, re-check the
   branch's unique delta before opening a replacement PR.
5. Re-read preconditions after a race or retry; never force/retry blindly.
6. Re-read the destination after a write.  Creating a PR does not authorise a
   merge, direct-main write, branch deletion, deployment, or any other side
   effect.

CIDF remains the complementary content-insertion gate: before adding a record,
read the destination's instructions, use the explicit user target, verify the
current branch/tree against origin, retain portable paths, and write canonical
source data rather than a rendered derivative.  The root `bin/orama-system/
SKILL.md` already installs both AFRP and CIDF as active subskills and gates; no
duplicate installation was necessary.

## Verification performed

- Fetched the Core and Orama remotes immediately before the decision.
- Compared `origin/main...origin/fix/route-health-probe-through-telos`; there
  are zero candidate commits on the branch and its merge is visible in Core
  `main` history.
- Queried open PRs in Core, Agate, Oramasys, and Orama System.  There are none
  in the first three; Orama System has only unrelated Dependabot PR #353.
- Verified Orama System `main` contains the #356 merge commit (`39988ce…`).
- Read PT's canonical recall results and the memory/skill rules before writing
  this record.  No rendered lessons file was edited by hand.

## Remaining migration debt

### Ready once a new scoped change is authorised

1. **Agate profile implementation completion.**  Keep the portable hardware
   mapping database and editable policy variables as the sole model-selection
   source; add/adjust profiles only from evidence of actual runs.  Do not
   hardcode profile logic into Oramasys, Core, or installers.
2. **Core scheduling/reducer/resume scope.**  Core contains checkpoint/resume
   mechanisms, but further reducer/scheduler work needs a separate explicit
   contract, tests, and PR; it was not implied by the security migration.
3. **Consumer conformance maintenance.**  Keep the Telos source scan, gateway
   conformance tests, and ledger current whenever a new outbound-capable
   consumer is introduced.

### External, non-substitutable gate

4. **Physical three-profile canaries.**  Cloud/container verification cannot
   prove the exact Mac MLX and Windows GGUF capability/affinity behavior.  Run
   the agreed canaries on the three proven hardware profiles, capture UTC
   evidence, and feed their results into Agate's data policy.  Until then, do
   not claim a hardware release gate is closed.

### Explicitly not remaining debt

- Do not open empty/replacement PRs for already merged migration branches.
- Do not create a second writable model-policy file behind the symlink.
- Do not reintroduce endpoint security logic in consumers because Telos is
  available.
- Do not use PT v1 memory as a runtime v2 endpoint/security dependency.

## Operating rule for the next agent

Before any PR/branch/merge conclusion, run the live-authority sequence:

1. Fetch/authoritatively read the exact destination state.
2. Capture base SHA, branch SHA, PR state, merge timestamp, and source-repo
   identity in UTC.
3. Compute the branch's unique delta versus that base.
4. Act only if a non-empty, authorised delta remains.
5. Re-read the remote state after the write and report the resulting authority.

This rule is the durable prevention for the stale-state failure; it applies to
GitHub actions, remote configuration, deployment gates, generated artifacts, and
any other mutable external authority.
