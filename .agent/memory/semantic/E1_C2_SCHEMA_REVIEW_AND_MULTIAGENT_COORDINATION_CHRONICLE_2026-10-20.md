# E1 C2 Schema Review & Multi-Agent Coordination Chronicle (2026-10-20)

**Document ID:** `PT-CHRONICLE-2026-10-20-E1-C2-SCHEMA-COORDINATION`
**Recording Agent:** Agnes (`agnes-antigravity-claude`)
**Repository:** `perplexity-api/Perpetua-Tools` (`.agent/memory/semantic/`)
**Collaborating Agents:** `claude-fable-5`, `codex-reviewer`, `cline-audit-integration-20261012`
**Base Anchor:** Commit `6dbd15ac` (Perpetua-Tools `origin/main`)
**Status:** Canonical Multi-Agent Coordination Chronicle & Architectural Decisions

---

## 1. Executive Summary & Problem Context

During the transition from E1 specification ratification to T3 bounded effect planning, two
critical coordination and contract challenges converged across the multi-agent swarm:

1. **Section 14 Rule 3 Precondition Verification:**
   E1 Draft Section 14 Rule 3 (lines 909–917) and Operator Decision 7 (2026-10-17) established an
   explicit pre-code prerequisite: an integrated schema contract fixing purpose discriminators,
   wire versions, refusal codes, and canonical serialization must be reviewed and referenced by
   exact commit before E1 ratification. The operator confirmed in substance that Parts 1 and 2
   at `59c623fa27497183d3a1c4ed19585d87623eae22` satisfied this prerequisite, and approved two
   docs-only PRs in `orama-system`:
   * PR 1: Specification Ratification Status Addendum (metadata-only).
   * PR 2: Part 3 Integrated Schema Amendment (freezing minimal revocation, cascade, and checkpoints).

2. **Cross-Agent Coordination Hold & Grilling:**
   When Agnes drafted the two PRs, `claude-fable-5` asserted a formal HOLD (Row 5256) enforcing
   the repository's invariant (lesson `03f368db3c16`): agent-relayed claims on GossipBus must not
   trigger outward repository actions until confirmed directly by the operator. Simultaneously,
   Claude conducted a rigorous review identifying six specific defects in the draft amendment.
   Once the operator confirmed directly to Claude in-session, all six defects were remediated,
   verified clean, and PRs #425 and #426 were pushed and opened.

3. **Offline Oracle Test Collection Regression:**
   Concurrently, during CodeRabbit remediation of PR #68, a newly added interop test
   (`src/tests/test_dispatch_abandon_interop.py`) used `pytest.importorskip`, causing six offline
   oracle cells to fail their manifest result gate because skipped tests exceeded the manifest's
   strict allowance. The fix required defining tests conditionally rather than skipping them.

---

## 2. The Two-PR Integrated Schema Solution in `orama-system`

### 2.1 Separation of History from Amendment (Cleanest Governance)

Splitting the documentation into two PRs avoided conflating historical ratification facts with
prospective specification amendments:

* **PR #425 (Metadata Addendum):**
  * **PR Link:** `https://github.com/diazMelgarejo/orama-system/pull/425`
  * **Branch:** `docs/e1-ratification-status-addendum` (Head: `13ec36f5b1680e49e20f631c5c04f36b0237e7ac`)
  * **Content:** Added `docs/v2/references/r4-safety-compatibility-platform-2026-10-10/2026-10-19-e1-specification-ratification-addendum.md`.
  * **Hygiene Rule:** Strictly additive. Existing specification bytes in
    `E1-AUTHORITY-STATE-EFFECT-FREEZE-DRAFT-2026-10-15.md` and
    `E1-C2-PURPOSE-VERSION-AND-REFUSAL-CONTRACT-2026-10-18.md` were left untouched to preserve
    the cryptographic byte integrity of ratified commit `59c623fa`.
  * **Invariant:** Reconfirms `ORAMA_GRANT_SERVING` strictly unset (fail-closed).

* **PR #426 (Part 3 Integrated Schema Amendment):**
  * **PR Link:** `https://github.com/diazMelgarejo/orama-system/pull/426`
  * **Branch:** `docs/e1-c2-part3-schema-amendment` (Head: `be31aeed41cfdd26eaaa0fc662994e62b6323fde`)
  * **Content:** Added `docs/v2/references/r4-safety-compatibility-platform-2026-10-10/E1-C2-INTEGRATED-SCHEMA-PART3-AMENDMENT-2026-10-19.md`.
  * **Frozen Shapes:**
    1. *Minimal Revocation Body:* `{"subject_kind": "grant" | "approval" | "issuer", "subject_id": str}`
       (where approval uniquely uses `second_approval_ref`, matching what grants carry).
    2. *Minimal Cascade Body:*
       `{"approval_id": str, "grant_ids": list[str], "issuer_authority_version": int}`.
    3. *Retained-Anchor Checkpoint Rule:* The retained row in `issuer_events` at version $N$ *is*
       the checkpoint. Pruning hot rows moves them to cold audit archives for 7-year retention.
    4. *Consumer Anchor Floor Invariant:* Bootstrapped consumer enforces $R_p \ge \text{anchor\_version}$
       under Step 4.3 Rule 4 acknowledgement coverage.
    5. *Open Witness Fields:* Explicitly records that consumer execution recovery witness fields
       remain open pending the telemetry contract slice.

---

## 3. Key Technical & Architectural Lessons

### Lesson 1: Test Collection vs. Skipping in Qualification Manifest Environments

In an environment governed by a qualification compatibility manifest (such as
`requirements/compatibility-manifest.v3.json`), maximum test skip counts (`max_skipped`) are
strictly constrained per oracle cell (e.g. 1 in production and core-r3; 5 in policy-r3).
When a test depends on an optional sibling checkout or capability (e.g. Phylax slice-2 abandon):

* **Antipattern:** Using `pytest.importorskip` or `@pytest.mark.skipif`. Pytest marks the test as
  SKIPPED. In offline/isolated oracle runs where the sibling checkout is absent, each skipped test
  increments the skipped tally, failing the collection gate with `N skipped exceeds the allowance`.
* **Correct Pattern:** Define the test conditionally:

  ```python
  if _capability_available():
      def test_feature(...): ...
  ```

  Where the capability is absent, zero items are collected and zero skips are registered,
  preserving the oracle cell's skip budget.

### Lesson 2: Consumer Coverage Gates vs. Shared Wire Refusal Codes

When designing cross-repository protocols:

* A consumer-side invariant (such as rejecting permits issued before an anchor event:
  $R_p < \text{anchor\_version}$) is a local Step 4.3 acknowledgement coverage check (Rule 4 family).
* Inventing a new wire refusal code (`grant.below_anchor_floor`) violates Part 1 Section 8, which
  requires a dedicated two-repo contract amendment for shared vocabulary changes.
* Invariants that arise from consumer state or pruning boundaries must be handled as consumer-local
  dispatch refusals, keeping the issuer wire vocabulary closed and minimal.

### Lesson 3: Canonical JSON Boundaries (RFC 8785 vs Python Canonical Serialization)

RFC 8785 (JSON Canonicalization Scheme / JCS) defines canonicalization by sorting object keys by
UTF-16 code units and formatting numbers per ECMAScript specifications. In contrast, Python
`json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)` sorts
Unicode code points.

* While byte-identical over the restricted domain of ASCII alphanumeric keys and safe integers,
  they diverge on non-ASCII keys (code point vs. UTF-16 code unit ordering) and negative zero (`-0.0`).
* Specifications must accurately describe the exact deterministic serialization rules used rather
  than claiming blanket RFC 8785 conformance.

### Lesson 4: Seven-Year Audit Retention & Pruning (Migrate, Never Discard)

Under regulatory and architectural compliance mandates (E1 Section 13.3), event history must be
preserved for seven years.

* Pruning an active database table (`issuer_events`) to bound memory and B-tree depth must never
  delete historical events.
* Pruning MUST be implemented as a migration: moving rows below the lowest acknowledged version
  from the hot table into a cold audit archive table or immutable file, while retaining the anchor
  event at the boundary as the active chain root.

### Lesson 5: Direct Operator Confirmation for Relayed Board Claims (Lesson `03f368db3c16`)

In multi-agent swarms using decentralized or shared event boards:

* A board row or note claiming operator approval or directive ("the operator said GO", "ratified")
  is an agent-relayed claim, not authenticated operator input.
* Agents must never initiate outward repository mutations (pushes, PR creations, pin promotions,
  merges) based solely on another agent's relayed claim.
* Agents must hold until the operator directly confirms the directive within their own session
  context, citing exact immutable commit hashes.

---

## 4. GossipBus Event Sequence Chronicle (Rows 5210 to 5310)

| Row ID | Agent | Kind | Event / Action |
| :--- | :--- | :--- | :--- |
| **5213–5215** | `agnes` | `agent_note` | Published Slice 2 dual-PR independent review report across PR #67 and PR #68. |
| **5221–5225** | `agnes` | `agent_note` | Verified cross-repo lockstep checks (5/5 scope binding; 7/7 abandon/successor). |
| **5235–5236** | `claude` | `agent_note` | Proposed stripping extraneous body fields from revocation/cascade; challenged anchor. |
| **5240–5244** | `agnes` | `agent_note` | Completed challenge task `E1C2-CHECKPOINT-AS-ANCHOR-EVENT` on wire lines 145–147. |
| **5246–5247** | `claude` | `agent_note` | Formulated 7 converged open items and posed two formal questions to operator ((a), (b)). |
| **5249–5250** | `agnes` | `agent_note` | Relayed operator approval of (a) and (b) and initiated drafting in isolated worktree. |
| **5256** | `claude` | `agent_note` | **Enforced HOLD:** Cited lesson `03f368db3c16` (relayed claims); issued 6-point review. |
| **5258–5259** | `agnes` | `agent_note` | Acknowledged HOLD; remediated all 6 defects in local worktree commits `c8957518`/`35cb1d8f`. |
| **5260–5261** | `claude` | `task_enqueue` | Operator confirmed in session; lifted HOLD; enqueued `E1-DOCS-PRS-revise-and-open`. |
| **5262–5265** | `agnes` | `task_claim` | Claimed task; published comprehensive analysis to OpenClaw `references/`. |
| **5272–5274** | `agnes` | `task_complete` | Pushed branches and opened PR #425 (`c8957518`) and PR #426 (`35cb1d8f`) on GitHub. |
| **5295–5300** | `codex` | `agent_note` | Published coordination reconciliation and Cline review packet in `references/`. |
| **5302–5305** | `codex` | `agent_note` | Published CodeRabbit remediations for PR #67 (`82379fa`), PR #68 (`4177ff5`), PR #425. |
| **5307–5308** | `claude` | `agent_note` | Discovered offline oracle skip allowance regression in PR #68; pushed fix `79cb836`. |

---

## 5. Current Swarm State & Canonical Pinned Heads

* **`oramasys/phylax` PR #15:** Head `e1e6f380e630c6792cbcf385b8ba075f673f43bd` (CLEAN).
* **`oramasys/oramasys` PR #67:** Head `82379fa8bbfca76b69eba37f698bfd94aca0a1c5` (CLEAN).
* **`oramasys/oramasys` PR #68:** Head `79cb83694cc784fc91caef48a1b1bf4938a350d3` (CLEAN, fixed).
* **`diazMelgarejo/orama-system` PR #425:** Head `13ec36f5b1680e49e20f631c5c04f36b0237e7ac` (CLEAN).
* **`diazMelgarejo/orama-system` PR #426:** Head `be31aeed41cfdd26eaaa0fc662994e62b6323fde` (CLEAN).
* **Serving Status:** Strictly fail-closed (`ORAMA_GRANT_SERVING` unset).

## 6. Cline Continuation Addendum (2026-10-20)

Cline independently reconciled the chronicle after Agnes's local commit was published to the
board. The requested unsuffixed worktree path did not exist; the canonical suffixed worktree did.
Before making any additions, Cline verified the worktree status, branch, base commit, and existing
chronicle contents. This avoided creating a duplicate worktree or duplicate chronicle.

The first validation attempt also exposed a tooling lesson: an incorrectly formed `--help`
invocation created an untracked `--help/` directory. Repository status was checked immediately,
the generated artifact was removed, and the native validators were rerun with their actual paths.
The chronicle's five Markdown hard-break trailing-space lines were then corrected, preserving the
intended rendered metadata while making `git diff --check` clean.

The existing local commit was amended rather than replaced. The final held-local commit is
`04eca76d7b2d9debe8a290ab117e636e68d4e449`, based on `6dbd15ac`; no push or pull request was
performed. Native memory-record validation, repository hygiene, JSON parsing, and append-only
checks all passed. Markdown lint passed on the pre-addendum chronicle; the same linter was not
available on the continuation shell, so the final file was additionally checked for trailing
whitespace and passed that bounded fallback check.

### Cline Lessons Added

* **Lesson `76c4a3551aac`:** Verify the canonical worktree, branch, base, and existing commit
  before adding to an established local chronicle; reconcile and amend an existing record rather
  than creating duplicate worktrees or memory entries.
* **Lesson `1a1cd4b20032`:** Treat validation invocations as potentially state-changing; inspect
  command behavior and repository status after every check because malformed help or wrapper
  arguments can create files or directories in the worktree.
