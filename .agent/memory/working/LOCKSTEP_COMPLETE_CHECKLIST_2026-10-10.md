# Complete coordinated lockstep checklist

Date: 2026-10-10 Asia/Manila / 2026-10-09 UTC. Current operator instruction:
use Perpetua-Tools #432 as the base and keep #433 stacked on its branch for
memory, procedures and reflections. This additive
record qualifies earlier procedures; it does not rewrite their historical facts.

Companions: [original protocol](LOCKSTEP_PINNING_PROTOCOL_2026-10-09.md),
[R3 procedures](R3_FANOUT_LOCKSTEP_PROCEDURES_AND_LESSONS_2026-10-10.md),
[exact R3 evidence](R3_REGISTRY_REPLAY_REVIEW_2026-10-10.md),
[retrospective](LOCKSTEP_PROCESS_RETROSPECTIVE_2026-10-10.md).

## Authority and both pairs

| Pair | Owns implementation | Owns coordination evidence | Must not happen |
| --- | --- | --- | --- |
| PT / Orama-System, v1 | Each repository's existing runtime and shared contracts, according to its established owner | PT portable memory; Orama canonical decisions and docs/v2 references; both PR handoffs | A documentation update introduces a Core/v2 runtime dependency into PT, or a historical corpus is replaced |
| Perpetua Core / Oramasys, v2 | Core structural GraphSpec and scheduler; Oramasys separately bound restrict-only GraphPolicy and framework bridges | Exact producer/consumer pins, profile snapshots, oracle lock, paired test results, canonical Orama references | Policy changes what the graph computes; a candidate overlay silently becomes the production dependency |

Orama is the normative document owner, not another runtime schema implementation.
Phylax admission, Telos transport and Agate hardware remain their actual owners.
Putting an authority's name in a declaration does not execute its enforcement.

## What every coordinated commit or handoff updates

| Artifact | PT / Orama pair | Core / Oramasys pair |
| --- | --- | --- |
| Exact revisions | Both peer heads, base heads, branch/PR identities and roles | Core candidate SHA, merged production SHA and consumer head; never a branch alias |
| Contract identity | Shared contract version and fixture digests, changed authority and acceptance cells | Structural schema/graph_id, policy schema/policy_id, registry profile and snapshot digests |
| Environment | Interpreter, dependencies, platform-sensitive qualifications and command | Oracle package versions and lock digest; production environment separately from candidate overlay |
| Code and tests | Changes in each actual owner plus paired acceptance evidence | Producer regressions and downstream full suite; real upstream oracle cells and framework-free production tests |
| Public references | Active canonical Orama reference and both PR descriptions | ADR, compatibility matrix and consumer candidate file; canonical docs checkout pinned in CI |
| Durable handoff | PT working state, episodic evidence and warranted semantic lessons | Same evidence mirrored into PT without a new runtime dependency |
| Review and CI | Fixing revision, latest reviewed head, outstanding findings and exact-head status | Candidate, producer and production lanes separately; pending and skipped states named explicitly |
| Promotion/rollback | Next authorized integration step and last validated pair | Upstream merge first, exact merged SHA promotion second, complete downstream requalification third |

Record a digest only when it has actually been computed. Mark unknown environment
or contract digests as missing gates; do not fill them with a plausible value.

## The full execution loop

1. Recall relevant memory, inspect current instructions and re-read the active
   PR list immediately before creating a branch or PR. Honor an explicitly named
   PR. An earlier inventory can become stale while another agent publishes.
2. Freeze the current heads and ownership map. Use isolated worktrees; main is
   not the write target. Read the actual current code before applying bot advice.
3. Cluster findings by invariant. Reproduce each runtime defect with a focused
   regression before fixing the owning abstraction. Distinguish a product bug,
   test weakness, documentation mismatch and environment failure.
4. Integrate relevant sibling/main changes in scratch. Disjoint filenames do
   not imply independence. Run conformance after combination; preserve valid
   parent histories and all prior records when resolving a merge.
5. Strengthen the evidence: adversarial completion order, forbidden duplicates,
   missing registry entries, incorrect owners and actual installed imports.
   A test that only observes its own happy path cannot certify an invariant.
6. Update implementation, docstrings, the active design reference, compatibility
   boundaries and exact fixtures together. Validate before canonicalization or
   indexing can erase an invalid declaration.
7. Keep the production dependency unchanged while testing the immutable producer
   candidate. Install pinned dependencies first, then use the explicit no-deps
   candidate overlay when necessary; run pip check afterward. Record which code
   and package versions the interpreter actually imported.
8. Publish the canonical Orama target once the target contract is concrete and
   reviewed. Verify its remote tree. Bind consumer CI to that immutable revision
   and advance only the candidate Core pin to the published producer fix.
9. Revalidate the complete producer suite, complete downstream candidate suite,
   actual offline oracle cells and framework-free production suite. Required
   candidate capabilities fail when absent; only intended production gates skip.
   Registry byte comparison must run in both CI lanes, not silently skip.
10. Before publication, inspect the staged diff, identity, hygiene and memory
    gates. Use the mandatory stage/verify/commit sequence. Publish one coherent
    batch per affected branch; an expected-head check accompanies a normal fast
    forward. Never use force merely to evade a stale-head rejection.
11. After publication, fetch each remote commit and compare its tree with the
    tested local tree. Re-poll CI on that exact head and re-read new review
    threads. Commit metadata may differ after authenticated API publication;
    tree equivalence is the proof of identical tested files.
12. Reply on the original review thread with the fixing revision, regression and
    result. Correct stale PR descriptions as metadata while retaining clearly
    labeled historical evidence. Preserve required PR-body sections.
13. Publish PT memory last. Preserve the existing JSONL prefix byte for byte;
    append only new valid records. Graduate justified lessons through tools and
    render LESSONS.md from semantic JSONL. Update working pointers, both-pair
    procedures, exact evidence and unfinished work. Do not store private paths,
    identities, credentials or machine-specific layout.
14. Hand off the current result once. Published, reviewed, CI-green, merged and
    production-promoted are distinct states. No merge follows from authorization
    to fix, push or answer reviews. A subsequent producer/consumer change starts
    a new qualification loop rather than borrowing the previous green run.

## Pin promotion and failure handling

Promotion sequence for R3: canonical design/profile review, Core integration,
then update Oramasys to the exact merged Core SHA and rerun downstream/oracle
qualification. Advance the production baseline registry and pin together only
after those gates. Retain the candidate profiles as historical evidence.

On a failed gate, keep the production pin and effects boundary intact. Diagnose
the failure instead of weakening assertions, hiding import failures or skipping
conformance. Reproduce environment failures using the locked environment; do not
count unexecuted tests as passing. If a published producer needs a new fix,
advance the candidate SHA and repeat the affected consumer gates.

On an unexpected remote head, fetch and inspect the delta before publishing.
Synthesize additive changes with parent history intact. History rewrites require
their own explicit authorization and preservation procedure; they are not the
ordinary lockstep path. Rollback restores the last validated artifact pair and
matching contract/profile evidence through a reviewed change, retaining history.

## Current facts and procedure qualifications

- Production Core remains `04759a50c748444ff97136ea95c1e1289eac3a1a`.
- Core candidate: `34e4a8d22212d38d6ab100c1ad7fb2b19f56cb68` (#9).
- Oramasys: `48715ff237f72235d31f75238239c8f491c9951b` (#25).
- Canonical Orama: `7b7f9d84e43f0709115588a95b13a78badb8369f` (#390).
- Oramasys #24 is merged. Orama #391 merged into #390, not main. The older
  R3 record's open-PR count is a historical checkpoint, not current status.
- Registry baseline is preserved. Both explicit candidate profiles and their
  consumer snapshots/digests exist; both consumer CI lanes pin canonical docs.
- Capability tooling is session-specific. REST replies worked here; available
  thread-resolution tools may use GraphQL internally. Do not teach REST-only
  routes as a universal requirement or claim an unavailable route works.
- A missing optional fixture is an environment limitation until reproduced.
  It is not grounds to waive a required suite. This review installed the actual
  external Agate fixture and ran the full Core suite.
- No system/VM restart is evidenced by this work. Missing CLI Git credentials
  and a hanging execution surface are different diagnoses.
- PT #432 is the base memory PR. Keep #433 open, targeting
  `docs/r3-lockstep-memory`; preserve both parent histories. No closure or branch
  deletion is authorized. Reuse existing PRs for subsequent pending work.
