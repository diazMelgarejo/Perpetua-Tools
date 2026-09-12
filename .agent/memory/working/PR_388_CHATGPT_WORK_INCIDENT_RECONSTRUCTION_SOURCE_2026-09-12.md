# Reconstruction of Perpetua-Tools PR #388
## What most likely happened in ChatGPT Work, based on the live GitHub record and surviving project context

**Repository:** `diazMelgarejo/Perpetua-Tools`  
**Pull request:** https://github.com/diazMelgarejo/Perpetua-Tools/pull/388  
**PR title:** `docs(memory): record the memory-corruption incident arc and remote-content-integrity gates`  
**Reconstruction date:** 2026-09-12  
**Current PR head reviewed:** `3a4b711189ad3d3594a8dd263adcd0750aec6b6e`  
**Base reviewed:** `main` at `8eacb65f9953957fd39c896ca77056888e1d5fb4`

---

## Executive reconstruction

PR #388 is best understood **not as the incident itself**, but as the surviving forensic record of a multi-session incident arc that unfolded between September 10 and September 12, 2026.

At least three distinct integrity failures were involved:

1. **PT memory deletion at commit `294f5ec9`** — an intended one-record lesson change net-deleted 34 lines from `.agent/memory/semantic/lessons.jsonl`, of which 31 were legitimate accepted lesson records. During repair, a second latent gap was discovered: 21 accepted graduated candidates had never been written to the canonical lesson store at all.
2. **A separate earlier PT wholesale corruption at `f1408af1`** — `lessons.jsonl` fell from 1,226 valid records to a 493-physical-line damaged blob containing only 492 valid JSON records plus one malformed binary-prefixed line, while `AGENT_LEARNINGS.jsonl` ballooned from 782 to 2,273 lines. The immediately following commit `5c97b162` had already repaired that incident before the PR #388 reconstruction session found it.
3. **A different repository suffered binary replacement at `ae52aff`** — in `oramasys/perpetua-core`, a commit claiming a small dependency-name normalization change replaced the entire 179-line `src/tests/test_policy.py` with binary garbage. The file was restored from the last known-good commit and later superseded by a correct normalization implementation.

These incidents were connected by a common operational lesson: **a successful tool call, commit, API response, returned SHA, CI step, or local parse does not prove that the bytes at the remote branch head—or later at the merged destination—are correct.**

A separate ChatGPT Work session apparently diagnosed the third incident as involving a **chunked Base64 publication path** and reported a local repair/memory commit `e494e85`. That session later became unreachable, and `e494e85` was not found in any clone reachable by the later reconstruction session. Therefore PR #388 correctly labels that portion **relayed** rather than direct evidence.

The later session independently reproduced the underlying Base64 boundary mechanism, but CodeRabbit correctly forced an important correction: the safe rule is **not** “all Base64 chunks must always be multiples of three” and the reproduced decoder did **not** silently truncate. The actual rule is narrower:

- if raw chunks are independently Base64-encoded,
- then their encoded forms are concatenated,
- and the concatenation is decoded once,
- non-final raw chunks should be 3-byte aligned to avoid interior Base64 padding;
- APIs that decode each part separately do not require this;
- decoder behavior varies;
- Python `base64.b64decode(..., validate=True)` rejects the malformed concatenated stream;
- final decoded length and cryptographic hash must still be independently verified.

The PR then added durable PT memory lessons and a long-form incident article so future agents would not repeat the same failure class.

---

# 1. What PR #388 itself contains

The PR is currently open, non-draft, mergeable, and targets `main`.

The branch is:

```text
docs/memory-corruption-incidents-remote-integrity-20260912
```

The latest reviewed head is:

```text
3a4b711189ad3d3594a8dd263adcd0750aec6b6e
```

The PR adds or updates:

- two graduated PT memory candidate records;
- episodic memory entries;
- semantic lesson records;
- rendered semantic memory;
- a detailed working-memory incident article:
  `.agent/memory/working/MEMORY_CORRUPTION_INCIDENTS_AND_REMOTE_INTEGRITY_GATES_2026-09-10_TO_2026-09-12.md`.

The two durable lessons are:

### `lesson_2d3ced9f9317`

Scoped Base64/chunking rule:

> Only when independently Base64-encoded chunks are concatenated for one final decode, use a multiple-of-3 raw chunk size (for example 12,288 = 4,096 × 3) to avoid interior padding. Per-part decoding does not require this. Record the producer/decoder contract and verify final decoded length and cryptographic hash.

### `lesson_d7a13d8bc5fb`

Four-level remote-integrity rule:

1. local intended file validity;
2. API/write acknowledgement;
3. actual remote object integrity at the exact branch head;
4. merged destination integrity.

None of these implies the next.

---

# 2. The most likely chronological sequence

## Phase A — PT memory damage was noticed and reconstructed

### Incident 1: `294f5ec9`

A commit intended to add one lesson instead caused a destructive rewrite of the canonical semantic JSONL store.

The later reconstruction session performed an **ID-set before/after comparison** against the commit parent and concluded:

- 34 lines were net-deleted;
- 31 of those represented legitimate previously accepted lesson records;
- this was not merely formatting churn or harmless deduplication.

During restoration, the agent did something more important than simply reverting the missing lines: it cross-checked **every graduated candidate file** against the canonical `lessons.jsonl`.

That revealed an independent, older graduation-pipeline gap:

- 21 candidate records were already marked `accepted`;
- but no canonical semantic lesson record existed for them.

The repair therefore consisted of two classes:

1. restore the 31 accidentally deleted accepted lessons;
2. reconstruct the 21 accepted-but-never-written lessons through the canonical memory write path.

The reconstruction also uncovered:

- five duplicate semantic IDs with identical claim text but divergent condition tags;
- one candidate with a two-element `supersedes` list that violated the renderer's expected schema.

The duplicates were merged by preserving the union of tags rather than discarding either source.  
The invalid supersession representation was narrowed to the actual single superseded target, while retaining the weaker relationship as metadata instead of silently losing it.

A new regression test was added:

> every graduated candidate with `status == accepted` must have a corresponding canonical `lessons.jsonl` entry.

The PR narrative states this test failed RED with 44 missing records before repair and returned GREEN afterward.

That test directly addresses PT memory-store completeness, but **not arbitrary file corruption**.

---

## Phase B — the agent searched history for more examples

### Incident 2: `f1408af1`

Because the operator explicitly asked whether anything else had been lost, the later agent scanned recent history for other large unexplained memory swings.

It found a second, independent destructive event:

Before `f1408af1`:

```text
lessons.jsonl = 1,226 valid JSON records
```

At `f1408af1`:

```text
493 physical lines total
492 valid JSON records
1 malformed first line with a binary prefix
735 lesson IDs missing relative to the parent
```

At the same time:

```text
AGENT_LEARNINGS.jsonl
782 lines -> 2,273 lines
```

The next commit:

```text
5c97b162
fix(memory): preserve canonical JSONL blobs
```

had already restored the state.

The reconstruction session did **not** simply trust the follow-up commit message or restored line count. It verified:

- no pre-incident lesson IDs were still missing;
- `AGENT_LEARNINGS.jsonl` after repair was byte-for-byte identical to its pre-incident version.

This matters because the operating failure being documented is precisely the danger of equating metadata or “success” with content integrity.

### Important correction made during PR review

The first incident write-up described this event imprecisely. CodeRabbit re-ran the history and pointed out that:

- `735` was the **missing-ID count**;
- `493` was the physical-line count of the damaged blob;
- only `492` lines were valid JSON;
- one surviving physical line was malformed because of a binary prefix.

PR #388 was amended to preserve those distinctions.

---

## Phase C — a corruption in `perpetua-core` exposed the remote-publication problem

### Incident 3: `ae52aff`

The work context had moved into a related architectural migration involving Agate and `perpetua-core`.

The intended architectural invariant was:

```text
perpetua-core should not acquire an upward dependency on the external
hardware-policy layer it is being decoupled from.
```

A preceding commit, `02ab8e1`, removed Agate from declared `perpetua-core` dependencies entirely.

Then commit:

```text
ae52aff
test(policy): normalize dependency names in boundary check
```

claimed a small test normalization.

But the actual committed blob for:

```text
src/tests/test_policy.py
```

was not a small source edit.

The later reconstruction reports that it was:

- binary data;
- the former 179-line test file was effectively gone;
- Python parsing failed;
- both Python 3.11 and 3.12 CI jobs were failing against the actual live tip.

The repair session restored the file from the last known-good commit and then addressed a separate dependency/test-environment issue.

The dependency solution evolved from:

```text
bare workflow-level pip install
```

to a more controlled optional dependency group:

```text
test-agate-compat
```

This preserved the intended boundary:

```text
plain .[dev] => no Agate dependency
.[dev,test-agate-compat] => compatibility tests may exercise Agate
```

A subsequent commit:

```text
9b64569
test(policy): preserve canonicalized dependency boundary guard
```

implemented the original intended normalization correctly using parsed package metadata and normalized dependency names.

The later session independently reproduced the resulting test file's:

- byte size: 6,601 bytes;
- Git blob SHA:
  `604d45ecebe653fe7463a9d7d422edff10d3e0ad`.

That independent hash match is much stronger evidence than the earlier “API returned a SHA” reasoning.

---

# 3. What appears to have happened specifically inside ChatGPT Work

This is the part that requires the most careful distinction between **observed** and **reconstructed** behavior.

## Directly observed in the follow-up ChatGPT Work session

The final PR commit added an explicit section documenting remote-workspace behavior that the follow-up session actually observed.

### A. Split authentication planes

The local shell did not have usable Git HTTPS credentials:

```text
git push
-> could not read Username for 'https://github.com'
```

At the same time, the connected GitHub integration **could**:

- read PR #388;
- write to the existing remote branch;
- return commit/blob identifiers.

Therefore ChatGPT Work effectively presented two different authority planes:

```text
local Git transport
!=
connected GitHub app/API transport
```

This is a critical root condition.

An agent seeing “local git push unavailable, but remote write API works” is strongly incentivized to reconstruct publication through API operations rather than through an ordinary local Git push.

That does not itself cause corruption, but it creates the environment in which an unsafe reconstruction path becomes tempting.

---

### B. Partial/no-checkout state briefly looked like mass deletion

The follow-up Work session also directly observed a misleading local repository state:

- the clone/worktree was not fully materialized;
- a large number of tracked files appeared deleted;
- after explicitly fetching the exact PR ref and checking out the exact SHA, the apparent deletions disappeared.

This led to another durable rule:

> In ephemeral or partial Work sandboxes, `git status` is evidence about the current checkout, not an oracle about repository truth.

Before “repairing” mass deletions, an agent should:

1. identify the exact requested ref;
2. fetch it;
3. detach at the exact SHA;
4. then inspect status/diffs/file counts.

Otherwise the attempted “repair” itself can become destructive.

---

### C. The connected GitHub path accepted direct UTF-8 writes

The follow-up Work session did **not** need to reproduce content through the earlier Base64 mechanism.

The GitHub integration accepted direct UTF-8 text writes.

This is why the final report explicitly says:

> the follow-up session did not reproduce the earlier binary corruption.

What it reproduced was the same **constraint boundary**:

```text
local Git transport unavailable
+
remote API writes available
```

So the safest reconstruction is:

- the environmental pressure was real and independently re-observed;
- the exact implementation used by the earlier lost session is not recoverable;
- the earlier claim that a Base64 chunked path caused the 79-byte result is therefore not promoted to direct fact.

---

# 4. The lost/no-longer-reachable agent session

One prior ChatGPT Work agent apparently produced a detailed incident diagnosis and claimed to have recorded PT memory locally in commit:

```text
e494e85
```

But the later session could not reach that object from any available fresh clone:

```text
git cat-file -t e494e85
-> not a valid object name
```

The surviving operator report from that earlier session stated, in substance:

- local file validity had been verified;
- a remote/API write returned success/SHA;
- that success was mistakenly treated as proof of remote branch integrity;
- the result was merged without an independent branch-head content read;
- no independent post-merge destination verification was performed;
- the `test_policy.py` binary corruption reached `main`;
- the publication path involved chunked Base64;
- 12,288-byte raw chunks were later chosen because the size is divisible by three;
- the incident motivated remote fetch-and-parse/hash gates;
- Orama PR #357 was opened to document the failure mode.

Because the underlying session and local commit are gone, those details are appropriately classified as:

```text
RELAYED
```

except where independently corroborated by reachable GitHub artifacts or reproduced behavior.

This is one of the strongest aspects of the final PR #388 write-up: it does **not** pretend that all surviving narrative has equal epistemic status.

---

# 5. What the Base64 mechanism really proves

The initial memory lesson was too broad.

CodeRabbit identified three important defects:

1. it implied that the 3-byte alignment rule applied more broadly than it actually does;
2. its “good” reproduction originally did not even cross a 12,288-byte chunk boundary;
3. it failed to name and characterize the decoder actually used.

The corrected experiment uses input longer than two 12,288-byte chunks.

For the “good” path:

```python
raw chunks
-> independently Base64 encode each chunk
-> concatenate encoded chunks
-> decode once with Python base64.b64decode(..., validate=True)
```

When every non-final raw chunk is divisible by three, it produces no interior `=` padding and round-trips correctly.

For a 7,000-byte raw chunk size:

- 7,000 is not divisible by three;
- a non-final independently encoded chunk ends with Base64 padding;
- concatenating additional encoded data after that padding creates an invalid single Base64 stream;
- Python's strict decoder rejects it.

Therefore the final, supportable rule is:

> 3-byte raw chunk alignment matters when independently encoded Base64 chunks are concatenated and later treated as one Base64 stream.

It is **not** required when an API independently decodes each uploaded part.

And decoder behavior should never be generalized from one implementation.

Most importantly:

> 3-byte alignment is not an integrity check.

The real integrity check remains:

```text
expected byte length
+
cryptographic hash / Git blob SHA
+
fresh exact-ref remote read
```

---

# 6. Why the original process failed

The most useful reconstruction is not “Base64 was buggy.”

The deeper process failure was **verification collapse**.

The earlier session appears to have treated this chain as though each step proved the next:

```text
local file looked valid
        ↓
API accepted write
        ↓
API returned SHA
        ↓
remote branch must contain intended bytes
        ↓
merge must be safe
        ↓
merged destination must contain intended bytes
```

That implication chain is false.

The correct model is four independent gates:

## Gate 1 — intended local content

Verify:

- file type;
- parseability;
- exact byte length;
- expected structural checks;
- local cryptographic hash.

## Gate 2 — write acknowledgement

Record:

- API success/failure;
- returned object/commit/blob identifiers.

But treat this only as:

```text
the server accepted the request
```

not:

```text
the remote repository now contains the bytes I intended
```

## Gate 3 — exact remote branch-head integrity

Freshly read the path from the exact PR head/ref and verify:

- content bytes;
- parseability;
- expected byte length;
- cryptographic/Git blob SHA.

Only this proves the branch actually has the intended file.

## Gate 4 — merged destination integrity

After an authorized merge, repeat the same check on the destination ref.

A correct PR head does not prove the eventual merged branch still contains those bytes.

---

# 7. Why this incident was unusually difficult to reconstruct

Several Work-environment properties compounded the problem.

## Ephemeral agent sessions

One important session was no longer reachable.

That meant:

- its local filesystem was gone;
- its exact shell command history was gone;
- its claimed local commit was not on a reachable remote ref;
- only operator-relayed statements and surviving remote artifacts remained.

## Multiple repositories were involved

The arc crossed:

- `diazMelgarejo/Perpetua-Tools`;
- `oramasys/perpetua-core`;
- `diazMelgarejo/orama-system`.

This increased the chance that one agent would treat a locally valid state in one repo as evidence about a different remote mutation.

## Multiple state authorities existed simultaneously

The agents had to reason about:

- local workspace;
- partial checkout;
- local Git object database;
- GitHub connected-app/API state;
- branch head;
- PR head;
- merged `main`;
- rendered PT memory;
- canonical PT JSONL memory;
- graduated candidate files.

Without explicit authority boundaries, “I see the file” or “the tool succeeded” can refer to the wrong state surface.

---

# 8. What PR #388 got wrong initially, and how it was corrected

The initial commit was:

```text
13dd7f1d63aa41cf6d3af0d86d65f75cd4803de1
docs(memory): record the memory-corruption incident arc and remote-content-integrity gates
```

CodeRabbit reviewed that version and raised substantive documentation-integrity issues.

The follow-up commits included:

```text
80059e97c2c442d0ca00fc4d27a3f53baee64900
docs(memory): scope Base64 integrity guidance

6936b8398b23bb81807e91a3860220291376fd1e
docs(memory): scope Base64 integrity incident guidance

3a4b711189ad3d3594a8dd263adcd0750aec6b6e
docs(memory): add Work sandbox publication constraints
```

The CodeRabbit threads were resolved after the fixes.

The corrections did four important things:

1. scoped the Base64 claim to the actual producer/decoder contract;
2. made the “good” reproduction actually cross a chunk boundary;
3. named Python's strict decoder and documented rejection rather than claiming universal silent truncation;
4. reconciled the `f1408af1` counts correctly.

The final commit then added the directly observed ChatGPT Work constraints so future readers would understand **why agents might end up using API publication paths at all**.

---

# 9. Relationship to Orama PR #357

The surviving PT record says a separate, no-longer-reachable agent session opened:

https://github.com/diazMelgarejo/orama-system/pull/357

as the broader procedural remediation.

That Orama work reportedly added:

- remote-content-integrity requirements to CIDF;
- a dedicated remote-content-integrity reference card;
- the 79-byte binary-file incident as an anti-pattern/worked example;
- exact remote verification requirements.

PR #388 does not duplicate all that detail into every PT lesson. Instead it cross-references the Orama documentation and stores the durable generalized lessons in PT memory.

That split is sensible:

```text
Orama/CIDF
= procedure/reference-card authority

PT .agent memory
= reusable learned operational rules and incident memory
```

---

# 10. What can be treated as verified fact

The following are strongly supported by reachable GitHub artifacts and/or the final reviewed PR record:

## Verified

- PR #388 exists, is open, and has the stated branch/head.
- `294f5ec9` caused a destructive semantic-memory delta.
- 31 legitimate accepted PT semantic records were restored.
- an additional accepted-candidate/canonical-store completeness gap existed.
- `f1408af1` produced a severely damaged `lessons.jsonl`.
- its damaged shape was 493 physical lines, only 492 valid JSON records, with 735 IDs missing relative to the parent.
- `5c97b162` repaired that earlier memory incident.
- `ae52aff` replaced `test_policy.py` with invalid binary content despite a narrow test-oriented commit message.
- the file was later restored/corrected.
- the correct file version was independently verified at 6,601 bytes with Git blob SHA `604d45ecebe653fe7463a9d7d422edff10d3e0ad`.
- PR #388's original Base64 explanation was materially overbroad and was corrected after review.
- the final Base64 reproduction is decoder-specific and Python strict decoding rejects the malformed concatenation.
- the Work follow-up session directly observed separate local-Git and connected-GitHub authentication planes.
- the Work follow-up session directly observed misleading apparent mass deletions caused by partial/no-checkout state.
- the connected GitHub integration could write UTF-8 files even while local `git push` authentication failed.
- the current PR head includes the Work-sandbox constraints.
- CodeRabbit's substantive threads shown on the PR are resolved.
- the current head's visible GitHub Actions matrix checks are succeeding; the fetched check-run payload reports eight checks and no failure conclusion was found in that payload.

---

# 11. What remains reconstructed rather than directly proven

## Strong but relayed reconstruction

The earlier inaccessible agent reportedly:

- used a chunked Base64 publication path;
- chose a non-3-byte-aligned chunk size;
- received successful tool/API responses;
- treated returned SHA/write acknowledgement as sufficient verification;
- merged without an exact-head fresh content verification;
- did not post-merge verify the destination;
- thereby allowed the corrupted binary test file to reach `main`.

This story is internally coherent and the underlying Base64-boundary mechanism was independently reproduced.

But the exact original Work tool call sequence is no longer available.

Therefore we **cannot prove**:

- the exact chunk size used in the corrupting call;
- the exact API endpoint or intermediate transport;
- whether the remote service concatenated Base64 text before decoding or the client did;
- which decoder generated the specific 79-byte result;
- whether Base64 alignment was the only contributing implementation defect.

The final PR is correct to avoid upgrading those details to direct fact.

---

# 12. Root cause tree

```text
                         INCIDENT ARC
                              |
          +-------------------+-------------------+
          |                                       |
     DATA/MEMORY LOSS                         SOURCE CORRUPTION
          |                                       |
  +-------+--------+                              |
  |                |                              |
294f5ec9        f1408af1                       ae52aff
  |                |                              |
canonical        canonical +                     |
lessons lost     episodic blobs                   |
                 damaged                           |
          \          |                            /
           \         |                           /
            +--------+--------------------------+
                     |
               COMMON FAILURE
                     |
       success signal trusted as integrity
                     |
        insufficient independent re-read
                     |
       state-authority boundaries blurred
                     |
       +-------------+--------------+
       |                            |
 partial/ephemeral             split auth planes
 Work checkout                local Git != GitHub API
       |                            |
 misleading local             API reconstruction paths
 repository state             become tempting
                                    |
                            unsafe content publication
                                    |
                           relayed Base64 mechanism
```

---

# 13. The best concise account of “what really happened”

The safest reconstruction is:

> Multiple agents working across ephemeral ChatGPT Work sessions and multiple repositories encountered destructive content mutations that normal success signals did not detect. PT's canonical memory store was accidentally rewritten more than once, and a `perpetua-core` Python test file was replaced with binary garbage while the associated commit still looked superficially like a normal small code change. One earlier agent session appears to have used an API-based, chunked Base64 publication workaround because ordinary local Git transport was unavailable; that session then trusted successful API responses/returned identifiers instead of re-reading and hashing the exact remote branch content before merge. The exact historical API/decoder sequence is unrecoverable, so the Base64 account is properly treated as relayed, although the underlying interior-padding hazard was independently reproduced. A later session recovered the repository history, restored missing PT memory through canonical tooling, verified an earlier wholesale memory repair byte-for-byte, repaired the corrupted `perpetua-core` file, added remote-integrity gates to Orama/CIDF, and created PR #388 to preserve the full incident and lessons. CodeRabbit then caught overstatement and arithmetic/evidence problems in that reconstruction, and the PR was corrected again. The lasting lesson is not merely “use 12,288-byte Base64 chunks”; it is that local validity, API acknowledgement, exact remote-head content integrity, and post-merge destination integrity are separate facts and must be independently verified.

---

# 14. Recommended canonical lesson from the incident

Future agents should treat every consequential remote content mutation as a four-gate protocol:

```text
INTENDED LOCAL BYTES
    |
    | validate parse / length / hash
    v
WRITE REQUEST
    |
    | record acknowledgement only
    v
REMOTE EXACT HEAD
    |
    | fresh fetch / parse / byte length / cryptographic or Git blob hash
    v
AUTHORIZED MERGE
    |
    v
DESTINATION EXACT REF
    |
    | fresh fetch / parse / hash again
    v
COMPLETE
```

And in ChatGPT Work specifically:

```text
Never infer:
GitHub app auth from local git auth,
local git auth from GitHub app auth,
repository truth from partial checkout status,
remote content correctness from returned SHA alone,
or merged integrity from a previously verified PR head.
```

---

# 15. Remaining gap

The PT memory regression added during this arc can detect:

```text
accepted graduated candidate
but missing canonical semantic lesson
```

It cannot detect the broader class:

```text
arbitrary tracked text/source file replaced by binary or malformed bytes
```

The PR narrative explicitly identifies that as a still-open gap.

A future generalized content-integrity guard could plausibly verify, for selected source/documentation paths:

- expected text/binary classification;
- UTF-8 validity where required;
- parser validity for Python/JSON/JSONL/TOML/YAML/Markdown as applicable;
- suspicious whole-file shrinkage/replacement;
- exact remote-head hashes for critical publication flows.

That is a forward recommendation, not something PR #388 claims is already implemented.

---

# 16. Source map

## Primary GitHub evidence

- Perpetua-Tools PR #388  
  https://github.com/diazMelgarejo/Perpetua-Tools/pull/388

- PR #388 head at time of reconstruction  
  `3a4b711189ad3d3594a8dd263adcd0750aec6b6e`

- Initial incident-record commit  
  `13dd7f1d63aa41cf6d3af0d86d65f75cd4803de1`

- Base64 guidance correction  
  `80059e97c2c442d0ca00fc4d27a3f53baee64900`

- Incident-guidance correction  
  `6936b8398b23bb81807e91a3860220291376fd1e`

- Work sandbox constraints  
  `3a4b711189ad3d3594a8dd263adcd0750aec6b6e`

- Cross-referenced Orama remediation  
  https://github.com/diazMelgarejo/orama-system/pull/357

## Important incident identifiers

- PT memory deletion: `294f5ec9`
- PT wholesale memory corruption: `f1408af1`
- PT repair of that earlier corruption: `5c97b162`
- `perpetua-core` last known-good dependency-state commit: `02ab8e1`
- `perpetua-core` binary-corruption commit: `ae52aff`
- later correct boundary guard: `9b64569`
- unreachable prior-session local memory commit: `e494e85`

---

# 17. Confidence legend

### High confidence
Directly supported by reachable GitHub commit/PR/review/check artifacts or independently reproduced in the surviving session.

### Medium confidence
Relayed from the prior Work session but consistent with reachable evidence and independently reproduced mechanism.

### Low / intentionally unclaimed
Exact historical tool-call sequence, exact decoder/API behavior that produced the 79-byte file, or any local state existing only in the lost Work session.

---

## Final conclusion

PR #388 is itself an example of the process it advocates.

The first version was **not fully correct**.

It contained:
- an overgeneralized Base64 lesson;
- an inadequate “good path” reproduction;
- an unspecified decoder behavior;
- an incorrectly explained incident count.

Those defects were found only because another independent system re-read the actual evidence.

That reinforces the central conclusion of the whole incident:

> **Never use a component's own success report as the sole proof that the state it was supposed to create is actually correct. Re-read the authoritative resulting state independently.**

That principle applies equally to:
- memory graduation;
- Git commits;
- API file writes;
- returned SHAs;
- PR heads;
- merges;
- CI status;
- and incident reports about all of the above.
