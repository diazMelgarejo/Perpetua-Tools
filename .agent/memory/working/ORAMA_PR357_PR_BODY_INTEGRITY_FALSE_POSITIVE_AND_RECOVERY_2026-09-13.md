# Orama PR #357 PR-body integrity false positive and recovery

**Date:** 2026-09-13  
**Repository:** `diazMelgarejo/orama-system`  
**Affected PR:** #357, `docs(cidf): require remote content-integrity gates`  
**Memory status:** working-memory incident/recovery dossier; preserve additively  
**Purpose:** retain the complete failure chain, exact evidence, recovery, and procedural lessons so future agents do not repeat a representation-boundary mistake while hardening integrity checks.

## Executive summary

A valid CodeRabbit review on Orama PR #357 identified four issues in the newly added CIDF/PR-metadata guidance. Three were documentation/authority corrections. The fourth exposed a genuine race in `scripts/cursor/append-pr-body.sh`: the script could read and compare a PR body, then perform an unconditional full-body replacement after another actor changed the body.

The remediation attempted to close that race by adding an extra immediately-before-write read and a post-write SHA-256 equality check. The concurrency regression test passed, but the existing happy-path test failed. The post-write integrity check compared **raw temporary-file bytes across two different text-serialization paths** whose trailing-newline behavior was not identical. A logically successful PR-body update was therefore misclassified as an integrity/concurrency incident.

The key failure was not the decision to add a concurrency guard. It was the failure to model the complete representation pipeline before choosing byte identity as the equality relation, combined with incomplete TDD verification: the new negative regression was considered, but the neighboring existing positive invariant was not run and observed before the fix was declared complete and review threads were resolved.

The corrective Orama commit `572c8f382b7542baef5c9d712e99599000b7cc1f` normalized trailing LF bytes before hashing. The exact corrective head subsequently passed both the repository `Test Suite` and `CI - Test & Build` workflows.

## Canonical architecture and authority context

PR #357 established or clarified the following durable rules. These remain valid; the CI failure was in the implementation of one guard, not in these authority decisions.

### PR metadata authority

- Unattended/autonomous agents, background agents, Cursor agents, and autoresearchers use new PR/issue comments or append-only incident/working notes by default.
- Existing PR-body mutation by an agent requires explicit current human authorization **and** the repository's execution guard.
- For agent-executed existing-body edits, the operator must mint `operator-grant-v2` using `scripts/cursor/grant-pr-body-human-override.sh` with the same `--file` or `--message` payload that the agent later passes to `scripts/cursor/append-pr-body.sh`.
- Direct human editing remains a separate allowed path.
- Initial PR creation through the explicitly permitted `ManagePullRequest create_pr` body-creation path is not the same operation as mutation of an existing PR body.
- Human authorization and execution capability are separate facts: a direct command or affirmative HITL/`#AskUserQuestion` decision does not let an agent bypass the operator-grant mechanism.

Canonical agent body-edit sequence:

`GRANT -> READ -> BACKUP -> MERGE -> WRITE -> REREAD`

Canonical autonomous reporting rule:

`AUTONOMOUS -> COMMENT/NOTE; BODY -> HUMAN AUTHORITY + OPERATOR GRANT`

### Remote-integrity lifecycle

The canonical model distinguishes four independent integrity facts:

1. **Local source validity**.
2. **Write acknowledgment**.
3. **Exact remote branch integrity**.
4. **Merged destination integrity**.

These are exercised through five checkpoints:

- A: before write — establish Fact 1;
- B: write returns — establish Fact 2;
- C: after branch write — establish Fact 3;
- D: immediately pre-merge — revalidate Fact 3 against the exact current head;
- E: after an authorized merge — establish Fact 4 on the merged destination.

Fact 4 cannot exist before the merge. Only Facts 1–3, including the pre-merge revalidation of Fact 3, can be completed before an authorized merge.

## CodeRabbit review that triggered the remediation

Review `5188699470` raised four still-valid issues against the then-current PR #357 state:

1. Existing PR-body edits by agents needed a mandatory `operator-grant-v2` plus `append-pr-body.sh` execution path, rather than permissive wording such as "where available".
2. `append-pr-body.sh` had a stale-write race: after comparing the live body with the initially read body, another actor could still update the PR body before `gh pr edit --body-file` replaced it.
3. The remote-integrity card needed to state that direct command/HITL authorization does not bypass the operator grant for an agent-executed body write.
4. The incident workflow incorrectly required Fact 4 before merge even though Fact 4 is, by definition, merged-destination integrity.

The review findings were sound. The later failure came from the implementation chosen for finding 2 and from insufficient verification before declaring the set complete.

## Commit chronology

| Commit | Role | Outcome |
| --- | --- | --- |
| `a7a7d5683e2af54cb396418cda2ae19f6f0e59b4` | Added the concurrency regression test | CI red; expected new negative test existed, but overall suite not green |
| `e9cb3cacf838db2d36ca96bd6607657b59cf7f0a` | Added pre-write digest recheck and post-write raw-byte digest comparison | New concurrency regression passed; normal success path still failed |
| `e72029f340a3a12f9c182b55e0a0227a13b9a16c` | Tightened PR metadata authority documentation | CI remained red because implementation defect persisted |
| `1b5bf737cb27e17d7b5f8ce43573f1ac919a1770` | Corrected Fact 4 ordering and completed the four-review remediation set | CI remained red; review resolution was premature |
| `572c8f382b7542baef5c9d712e99599000b7cc1f` | Normalized trailing newline semantics before post-write hashing | Test Suite and CI green |

## Exact failing evidence

At Orama head `1b5bf737cb27e17d7b5f8ce43573f1ac919a1770`:

- `Test Suite` run `34728293432` failed.
- `CI - Test & Build` run `34728293435` failed.
- Security scans, endpoint-policy peer contract, PR-body anti-clobber guard, Markdown lint, and PR-body Summary restore all succeeded.

The full test suite collected 1,768 items plus one skipped during collection. The decisive result was:

- `tests/test_append_pr_body_grant_flow.py::test_append_pr_body_consumes_grant` — **FAILED**;
- `tests/test_append_pr_body_grant_flow.py::test_append_pr_body_rejects_change_after_comparison` — **PASSED**.

Final failing-suite summary:

`1 failed, 1758 passed, 10 skipped`

The happy-path failure output was:

```text
OK: grant valid
OK: grant reserved
backup: ...
error: remote PR body does not match the merged body after write; treat as concurrency/integrity incident
```

This is high-value diagnostic evidence: the new negative case worked, but the established positive behavior was broken. That pattern means the new guard was over-restrictive or used the wrong equivalence relation.

## Faulty implementation

The remediation wrote the merged body to a local temporary file using:

```bash
printf '%s\n' "$merged" >"$out"
```

and later fetched the PR body again into another temporary file. It then compared raw SHA-256 digests of the two files.

The helper initially hashed raw bytes:

```python
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
```

That implicitly asserted:

> equality of the logical GitHub PR-body field == exact byte equality of two helper temporary files produced by different serialization paths.

That assertion was false.

## Root cause: text representation was mistaken for byte identity

The local `out` file was deliberately created with `printf '%s\n'`, which adds a trailing LF byte.

The readback path traversed GitHub JSON/text output and, in the hermetic fake-gh test, shell command substitution. Shell command substitution strips trailing newlines. GitHub PR descriptions are JSON text fields, not byte-preserving binary blobs. Therefore the two temporary files could represent the same logical PR-body text while differing by a trailing LF byte.

The corrective commit documented a direct reproduction of this mismatch as 12 local bytes versus 11 readback bytes and verified the byte difference with `od`.

A second clue was already present in the original script and should have been recognized before adding raw-byte hashing:

```bash
current_body="$(cat "$remote_tmp")"
```

Command substitution itself strips trailing newline bytes. The pipeline therefore already treated trailing-newline representation as non-authoritative at some boundaries. Adding an exact raw-file hash later in that pipeline introduced a stronger byte-level invariant than the surrounding code could preserve.

## The correction in `572c8f38`

The corrective commit changed the hash helper to normalize trailing LF bytes before hashing:

```python
content = Path(sys.argv[1]).read_bytes().rstrip(b"\n")
print(hashlib.sha256(content).hexdigest())
```

This makes the pre/post guard compare the canonicalized textual payload rather than incidental trailing newline bytes introduced or removed by the helper/transport boundary.

The corrective commit's own RED/GREEN evidence records:

- with the normalization reverted, the failure reproduces;
- with normalization restored, both tests in `tests/test_append_pr_body_grant_flow.py` pass.

At exact head `572c8f382b7542baef5c9d712e99599000b7cc1f`, GitHub subsequently reported:

- `Test Suite` run `34729094276` — success;
- `CI - Test & Build` run `34729094291` — success;
- Agent security scans — success;
- PR body Summary restore — success;
- Markdown lint — success;
- PR body anti-clobber guard — success;
- Endpoint Policy Peer Contract — success.

That is the completion evidence that should have existed before any prior completion claim.

## What the agent did wrong

### 1. It solved the race without tracing the representation pipeline

The race was real, but the chosen equality check was designed in isolation. The agent should first have mapped:

`GitHub body field -> gh --json/--jq -> stdout -> shell command substitution or file redirect -> shell variable -> printf -> temp file -> gh edit -> GitHub field -> readback`

For every edge, it should have asked whether line endings, trailing newlines, Unicode normalization, or encoding are preserved exactly.

### 2. It conflated two different integrity domains

The project had just established strict **byte-integrity** rules for transported repository files. The agent overgeneralized that doctrine to a mutable GitHub **text metadata field**.

Those domains differ:

- a Git blob or downloaded tracked file has a meaningful exact byte identity;
- a GitHub PR description is a logical JSON string transported through tools that may add or remove output newlines around the field representation.

Therefore "remote integrity" does not always mean "hash the helper files byte-for-byte." The canonical representation must match the semantics of the external system being verified.

### 3. TDD stopped after proving the new negative case

The new race test was useful, but TDD GREEN requires more than making the new test pass. It requires the existing contract to remain green.

The immediate focused command should have been:

```bash
pytest tests/test_append_pr_body_grant_flow.py -v
```

That would have run both:

- the existing successful append/consume path;
- the new concurrent-edit rejection path.

The failure would have been visible before documentation updates, thread resolution, or completion claims.

### 4. The existing happy-path test was the most important neighboring invariant and was not treated as such

The pre-existing `test_append_pr_body_consumes_grant` was precisely the compatibility guard for the normal operator-granted workflow. Any change to `append-pr-body.sh` should have made that test mandatory before broader CI.

A new safety check that passes only failure scenarios but rejects all successful operations is not a valid safety improvement.

### 5. The agent claimed hermetic validation without executed evidence

The agent said it would validate RED hermetically when no workflow run initially appeared, but the visible execution record did not contain a completed local/hermetic test run before production changes proceeded.

Future rule: never convert an intended validation step into prose that sounds like completed evidence. Either run it and record the result, or state explicitly that it remains unverified.

### 6. Review threads were resolved before exact-head behavioral verification

The four CodeRabbit issues were marked resolved while the current head was CI-red.

Thread resolution is not merely a documentation action when a review finding caused executable guard changes. It should occur only after:

1. exact current head is known;
2. focused affected tests pass;
3. relevant full CI passes or the exact unavailable portion is explicitly documented;
4. the review condition is re-read against that same head.

### 7. The completion statement violated evidence-before-assertion

The agent reported the four findings as fixed while `Test Suite` and `CI - Test & Build` were failing on the same exact head.

A resolved thread, a successful file write, or a logically convincing diff is not equivalent to verified completion.

## What should have been done instead

### Step 1: inspect the entire current success path before changing it

Read:

- `scripts/cursor/append-pr-body.sh`;
- `scripts/cursor/grant-pr-body-human-override.sh`;
- `scripts/cursor/pr-body-grant-lib.py`;
- `tests/test_append_pr_body_grant_flow.py`;
- relevant fake-gh behavior.

Identify all serialization boundaries and existing invariants.

### Step 2: define the equality relation explicitly

Before implementing a post-write proof, answer:

- Is the target a byte-preserving object or a logical text field?
- Which transformations are permitted by the transport/tooling?
- Are trailing newline count, CRLF/LF, or Unicode normalization semantically meaningful?

For the PR body, the guard should compare a deliberately canonicalized text representation rather than accidental helper-file byte layout.

### Step 3: write both negative and positive regression coverage

The race regression should be paired with explicit preservation of the existing happy path.

At minimum:

1. unchanged PR body + authorized append -> succeeds and consumes grant;
2. body changes before write -> fails closed and preserves concurrent update;
3. successful post-write readback with transport-only trailing-newline difference -> succeeds;
4. real substantive post-write mismatch -> fails as an integrity incident.

### Step 4: verify RED correctly

Run the new negative/conformance tests against the old implementation and observe the expected failure for the missing race guard.

Do not infer RED from code inspection.

### Step 5: implement the smallest GREEN change

Prefer one canonical body-normalization helper reused by pre-write and post-write checks. Do not introduce multiple subtly different equality rules.

### Step 6: run the whole focused test file

```bash
pytest tests/test_append_pr_body_grant_flow.py -v
```

The change is not GREEN unless **both old and new invariants pass**.

### Step 7: run repository-level validation

Run the relevant full suite/CI. If the environment cannot reproduce CI, wait for and inspect exact-head GitHub Actions results rather than claiming completion from partial evidence.

### Step 8: resolve review threads only on a green exact head

For each review thread, record:

- reviewed finding;
- fixing commit;
- exact current head;
- focused test result;
- relevant CI result.

Then resolve.

## Stronger general rule: representation-aware integrity

**Do not choose hashes before choosing the canonical representation.**

A cryptographic digest proves equality only under the byte representation supplied to it. If two correct serializers produce semantically equivalent text with different incidental bytes, raw digest comparison creates false positives rather than stronger integrity.

Before hashing, classify the target:

| Target | Default integrity relation |
| --- | --- |
| Git blob / tracked artifact / binary payload | exact bytes + cryptographic/Git blob hash |
| Encoded transport reconstructed into a tracked file | exact decoded bytes + length/hash + parser |
| JSON object with canonical schema semantics | schema/value equivalence; canonical serialization only if explicitly defined |
| GitHub PR/issue text metadata | canonical logical text representation, with transport newline semantics defined |
| Human-facing rendered Markdown | source text plus structural markers; byte identity only if the storage API guarantees it |

The principle is:

> Hashes do not define integrity semantics. The data model defines the canonical representation; hashes then prove equality of that representation.

## Newline normalization precision

The accepted corrective fix uses:

```python
.rstrip(b"\n")
```

which removes all trailing LF bytes before hashing. This is now proven green for the current PR-body workflow and should not be changed casually.

However, future agents must understand the semantic choice being made: trailing LF multiplicity is treated as non-authoritative for this comparison. If a future requirement makes exact trailing-newline count meaningful, the canonicalization contract must be revisited explicitly rather than silently changing the hash function.

Possible future alternatives, if requirements change, include:

- normalize exactly one helper-added newline on both sides;
- avoid adding a helper newline when writing the comparison artifact;
- canonicalize the logical text value in one shared function before both write and verification;
- use an API-provided conditional version/ETag mechanism if GitHub exposes one for this exact field in the future.

Do not replace the current green fix merely because an alternative appears theoretically stricter.

## Concurrency precision

The added pre-write check is optimistic concurrency protection, not an atomic server-side compare-and-swap. GitHub's ordinary PR-body update path used here does not make the read-compare-write sequence atomic.

Therefore:

- re-read immediately before mutation;
- reject a changed body;
- perform the guarded write;
- re-read immediately after mutation;
- verify the canonicalized result;
- treat mismatch as a concurrency/integrity incident.

Do not claim atomic CAS unless the external API actually provides and enforces a conditional write primitive for the field.

## Review-resolution gate

A review finding involving executable behavior is not complete merely because its text is addressed.

Canonical gate:

`FINDING -> CURRENT HEAD -> RED PROOF -> MINIMAL FIX -> FOCUSED GREEN -> FULL GREEN -> RE-READ FINDING -> RESOLVE`

If CI is red for a test touched by the fix, the finding remains operationally unresolved regardless of the thread's UI state.

## Evidence hierarchy reinforced by this incident

Do not collapse these statements:

1. the intended fix is conceptually sound;
2. the new regression test passes;
3. the old behavior still works;
4. the focused test file is green;
5. the full suite is green;
6. the exact PR head is green in CI;
7. the review thread is resolved;
8. the change is safe to merge.

Each is a separate fact. Later facts require their own evidence.

## Durable future-agent checklist

Before changing an integrity guard:

- [ ] Identify whether the target is bytes, structured values, or text metadata.
- [ ] Trace every serialization/deserialization boundary end to end.
- [ ] Define the canonical equality relation before selecting a hash/checksum.
- [ ] Read existing success-path tests before writing a new failure-path regression.
- [ ] Write a RED regression that proves the defect.
- [ ] Run the RED test and record the expected failure.
- [ ] Implement the smallest fix.
- [ ] Run all neighboring positive and negative tests.
- [ ] Test representation edge cases: empty value, trailing newline, multiple trailing newlines, and any relevant CRLF/LF behavior.
- [ ] Run the full relevant suite or inspect exact-head CI.
- [ ] Do not resolve review threads while affected CI is red.
- [ ] Do not describe planned validation as completed validation.
- [ ] Re-read the exact remote head and review coverage before claiming completion.

## Final lesson

The incident demonstrates a subtle but important distinction:

> **Stricter checking is not automatically stronger correctness.**

A guard becomes stronger only when its invariant matches the semantics of the data being protected. Exact-byte verification is ideal for exact-byte artifacts. It is wrong when applied blindly to a logical text field whose supported transport changes incidental newline representation.

The correct discipline is representation-aware integrity plus complete red/green verification of both the new failure mode and the established success path.

## Evidence references

- Orama PR #357: `https://github.com/diazMelgarejo/orama-system/pull/357`
- CodeRabbit review: `https://github.com/diazMelgarejo/orama-system/pull/357#pullrequestreview-5188699470`
- Test-only regression commit: `a7a7d5683e2af54cb396418cda2ae19f6f0e59b4`
- Initial concurrency-guard implementation: `e9cb3cacf838db2d36ca96bd6607657b59cf7f0a`
- Documentation authority correction: `e72029f340a3a12f9c182b55e0a0227a13b9a16c`
- CI-red remediation head: `1b5bf737cb27e17d7b5f8ce43573f1ac919a1770`
- Corrective commit: `572c8f382b7542baef5c9d712e99599000b7cc1f`
- Failing Test Suite run: `34728293432`
- Failing CI - Test & Build run: `34728293435`
- Green Test Suite after correction: `34729094276`
- Green CI - Test & Build after correction: `34729094291`

## Relationship to existing PT memory

This dossier complements, rather than supersedes:

- the remote-content integrity and limited-workspace incident memory;
- the rule that write acknowledgment, exact remote content, and merged destination integrity are independent facts;
- the PR-body anti-clobber doctrine;
- the Perpetua Core PR #6 recovery dossier already carried by this PT memory branch.

The new refinement is that **integrity verification must be representation-aware**. The earlier exact-byte lessons remain fully authoritative for tracked files and binary/content transport; they must not be transplanted mechanically onto external text metadata fields with different serialization semantics.
