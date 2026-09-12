# Remote Publishing Integrity and Limited-Workspace Domain Knowledge

**Verified/reconstructed:** 2026-09-12 UTC  
**Scope:** ChatGPT Work / remote sandboxes, Git/GitHub publication, UTF-8 and
Base64 transport, partial/no-checkout workspaces, and PT memory publication.

This is stable domain knowledge distilled from the incident arc recorded in
Perpetua-Tools PR #388 and the companion Orama CIDF remediation in PR #357.
The narrative incident record remains:

- `.agent/memory/working/MEMORY_CORRUPTION_INCIDENTS_AND_REMOTE_INTEGRITY_GATES_2026-09-10_TO_2026-09-12.md`
- graduated `lesson_2d3ced9f9317` (Base64/chunking contract)
- graduated `lesson_d7a13d8bc5fb` (four integrity facts)

This file explains the mechanism and operating model so a future agent in a
limited sandbox does not have to rediscover it from symptoms.

## 1. Separate the authority planes

A remote workspace can expose multiple GitHub-related capabilities that are
**not the same authority**:

1. the local shell's `git` transport and credential helper;
2. a local `gh` CLI session, if installed and authenticated;
3. a connected GitHub App / connector with its own authorization;
4. a provider-specific file/content API exposed by the remote workspace.

A working connector does not prove `git push` from the shell is authorized.
A failed local `git push` does not prove the connector cannot write. A missing
or shadowed shell credential does not authorize credential rotation by itself.

Before changing credentials or declaring publication impossible, identify the
plane that actually failed and the plane that is actually authorized.

## 2. Separate object presence, checkout state, and repository truth

A file can be absent from a worktree while its Git object is present and the
remote repository is correct. Limited sandboxes commonly use shallow,
partial, sparse, detached, or not-yet-materialized checkouts.

The layers are distinct:

- **remote ref:** branch/tag/PR head points to a commit;
- **commit/tree objects:** repository history says which blobs exist;
- **local object database:** the sandbox may or may not have fetched them;
- **index:** the checkout may or may not have staged/materialized them;
- **worktree:** ordinary filesystem presence is only the last projection.

An apparent mass deletion in `git status` from an incomplete checkout is not
evidence that the remote branch deleted the repository. Before repair or
publication:

1. identify the exact requested remote ref and SHA;
2. fetch that ref/object explicitly when local transport permits;
3. materialize or inspect the exact tree in a clean/detached worktree;
4. only then interpret file counts, diffs, or deletions.

Never commit an apparent mass-deletion state merely to "restore" a checkout
whose object/ref state has not been established.

## 3. Prefer direct Git object transport when it is available

For an existing repository and a large change set, native Git is usually the
simplest integrity-preserving transport because Git already provides:

- object framing;
- content hashing;
- tree construction;
- commit ancestry;
- delta/compression transport;
- ref update semantics.

Do not invent a multi-part content reconstruction protocol merely because a
remote workspace also exposes an API. Use the API when local Git transport is
unavailable or the integration explicitly requires it, then raise the
verification standard accordingly.

## 4. UTF-8 text and Base64 are different transport contracts

For a UTF-8 text file, prefer a text-oriented API that accepts the complete
UTF-8 string and performs any required API-level Base64 encoding internally.
This removes an unnecessary manual encoding layer.

When an API requires Base64, document the exact producer/decoder contract:

- Is one whole file Base64-encoded once and decoded once?
- Are raw chunks encoded independently, concatenated as Base64 text, then
  decoded once?
- Are parts independently encoded and independently decoded before byte
  concatenation?
- Does an intermediate tool re-wrap, truncate, normalize, or paginate output?

These cases are not interchangeable.

## 5. Why 12,288 bytes is a useful worked example

Base64 maps **3 raw bytes -> 4 encoded characters**. Padding (`=`) appears
when an encoded input ends on a boundary that is not a multiple of 3 bytes.

`12,288 = 4,096 * 3`, therefore a full 12,288-byte raw chunk:

- ends on a 3-byte boundary;
- requires no Base64 padding;
- encodes to exactly 16,384 Base64 characters.

That makes 12,288 a convenient example when **independently encoded chunks
are concatenated into one Base64 stream that will be decoded once**: every
non-final chunk can remain padding-free.

The number 12,288 is **not a universal magic chunk size**. Any non-final raw
chunk size divisible by 3 has the same alignment property. More importantly,
if each encoded part is decoded independently and the decoded byte parts are
then concatenated, 3-byte alignment is not required for correctness.

The invariant is the producer/decoder contract, not the numeral.

## 6. Interior Base64 padding is a protocol smell

If independently encoded non-final chunks contain `=` padding and their
encoded strings are naively concatenated for one final decode, the stream has
padding in its interior. Decoder behavior can vary:

- a strict decoder may reject the stream;
- another decoder may stop at the first padding boundary;
- another implementation may have provider-specific behavior.

Do not rely on any decoder's incidental behavior. Prevent ambiguity by either:

1. encoding the complete payload once;
2. using padding-free non-final chunks (raw length divisible by 3) when the
   encoded chunks must be concatenated before one decode; or
3. decoding each part independently and concatenating decoded bytes.

After reconstruction, always verify decoded length and a cryptographic/content
hash. A sequence of individually successful encode/decode/API calls is not a
file-integrity proof.

## 7. Tool-output text is not a safe byte transport by default

Remote-agent tools may truncate large stdout, cap response tokens, wrap text,
insert elisions, or return only excerpts. Therefore:

- never reconstruct a large file from displayed/truncated command output;
- never treat `... (truncated)` or a partial search result as file content;
- use raw file/blob APIs, connector file references, or native Git objects;
- if chunking is unavoidable, use explicit byte offsets and lengths and prove
  continuity (no gaps, overlaps, reordering, duplication, or truncation).

Every chunk manifest should record at least:

- source blob/file identifier;
- byte offset;
- raw byte count;
- encoding used;
- sequence number / total count;
- expected final byte count;
- expected final hash.

## 8. A returned SHA is evidence, not proof of intended content

A content API can correctly return a blob SHA for the bytes it received even
when the caller sent the wrong, truncated, duplicated, or re-encoded bytes.
The API proves only that GitHub stored *some* content under that identifier.

For intended exact bytes, independently verify:

1. expected local byte length;
2. expected local content/Git blob hash;
3. remote file/blob length at the exact branch head;
4. remote file/blob hash;
5. parser/compiler/schema checks on the freshly fetched remote bytes.

For Git, blob identity is content-addressed over the Git blob framing plus the
file bytes (`blob <length>\0<bytes>`). A commit SHA also includes tree,
parents, metadata, and message. Thus an API-created remote commit can have a
different commit SHA from a local commit while containing byte-identical file
blobs. Compare the artifacts at the right layer.

## 9. The four integrity facts are independent

Treat these as four separate gates:

### Gate 1 — Local source validity

Before commit/publication:

- expected file size or line count;
- UTF-8 decode for text files;
- JSON/JSONL/YAML/schema validation where relevant;
- `py_compile`/parser/build checks for executable source;
- local content/blob hash captured when exact transport matters.

### Gate 2 — Write acknowledgement

After the API or Git write:

- request succeeded;
- returned commit/blob/ref identifiers captured;
- errors and partial failures checked.

Gate 2 does **not** imply Gate 3.

### Gate 3 — Exact remote branch integrity

Before review resolution or merge:

- re-read the live PR state and exact head SHA;
- fetch the affected file/blob from that exact head through an independent
  read path;
- compare byte count/hash with the intended source;
- parse/compile/schema-check the freshly fetched remote content;
- verify the changed-file set and net diff are what was intended.

### Gate 4 — Merged destination integrity

After an authorized merge:

- re-read the destination ref (`main` or other base);
- fetch the affected file/blob from the destination;
- repeat byte/hash/parser checks;
- verify the intended head is actually reachable/absorbed and no post-merge
  branch delta is being mistaken for already-merged work.

No earlier gate authorizes skipping a later one.

## 10. Commit identity versus semantic equivalence

Do not require a remote API-created commit to equal a local commit SHA. The
same file content can be represented by different commits because parent
selection, author/committer metadata, timestamps, messages, or tree assembly
may differ.

For reconstruction/publication verification, distinguish:

- **exact file equality:** blob hash + byte equality;
- **tree equality:** tree object equality when expected;
- **semantic change equality:** no unexpected diff relative to the intended
  base;
- **history identity:** commit SHA equality only when the same commit object
  itself was transported.

This prevents both false failure (different commit SHA, correct content) and
false success (returned SHA exists, wrong content).

## 11. PR and branch state are mutable external authority

Before deciding that a branch is duplicate, already merged, lost, or ready to
merge, re-read live state. Record:

- PR state;
- `mergedAt` / whether it was actually merged;
- base branch and base SHA;
- head repository owner, branch, and head SHA;
- net remaining diff against the current base.

Important distinctions:

- open PR != merged PR;
- closed-unmerged != merged;
- same branch name in a fork != same head identity;
- a merged PR can have **new post-merge commits** on its old branch, which form
  a new delta and usually require a new PR;
- a squash merge can make commit ancestry appear divergent even when the
  semantic tree changes were absorbed, so use diff/tree evidence too.

This domain knowledge complements AFRP's live-authority rule.

## 12. Limited-sandbox publication playbook

When desktop tooling is unavailable:

1. **Recall first.** Search PT memory for prior auth, checkout, corruption, and
   remote-integrity lessons.
2. **Identify authority plane.** Determine whether local Git, `gh`, or a
   connected GitHub integration can read/write.
3. **Read live remote state.** Exact PR/base/head/repository identity.
4. **Establish local source integrity.** Do not write from a partial/truncated
   display.
5. **Choose the simplest authorized transport.** Native Git first when
   available; UTF-8 content API for text when Git transport is unavailable;
   Base64 only with an explicit contract.
6. **Write once per logical batch.** Avoid reconstructing a monolithic file by
   repeated blind overwrites.
7. **Gate 3 immediately.** Independently fetch the exact remote bytes and
   parse/compile them before claiming success or resolving review threads.
8. **Re-read review/CI.** Review systems rescan on new heads.
9. **Merge only with explicit authority and current-head evidence.**
10. **Gate 4 after merge.** Re-read destination bytes, not only PR state.
11. **Reflect and learn.** Significant publication failures should enter
    episodic memory, then semantic lessons/domain knowledge through PT's
    canonical memory tooling.

## 13. Stop conditions

Stop and do not publish/merge when any of the following is true:

- source file came from truncated console/tool output;
- encoded chunks have unknown boundaries or ordering;
- final reconstructed size/hash is unknown;
- remote file cannot be independently re-read;
- remote parser/compiler fails;
- PR head changed after the last verification;
- base changed materially and the diff was not re-evaluated;
- checkout state makes mass deletions ambiguous;
- credentials/auth plane are inferred rather than verified;
- an API's success response is the only evidence of correctness.

## 14. Evidence from the 2026-09-12 incident arc

The incident family demonstrated three related but distinct failure modes:

1. canonical memory records were accidentally removed by whole-file or stale
   reconstruction operations;
2. partial/no-checkout state produced misleading apparent deletions;
3. a Python test file reached a remote `main` branch as a tiny binary/gibberish
   payload after a publication path reported success.

The corrective controls are correspondingly layered:

- append-only/canonical memory tooling and candidate-to-lesson completeness
  tests;
- exact-ref/object/checkout verification;
- remote-content-integrity gates with byte/hash/parser checks.

Do not collapse them into one vague rule such as "be careful with GitHub".
They occur at different abstraction layers and require different evidence.

## 15. Cross-references

- PT PR #388 — incident reconstruction and memory consolidation.
- Orama System PR #357 — CIDF remote-content-integrity gates/reference card.
- `lesson_2d3ced9f9317` — Base64 chunking contract.
- `lesson_d7a13d8bc5fb` — four integrity facts.
- `lesson_93c1b7416ff3` — live external-authority reread before consequential
  actions.
- `.agent/skills/perpetua-memory/SKILL.md` — append-only memory and branch
  consolidation doctrine.

## Compact mnemonic

**AUTH -> REF -> BYTES -> PARSE -> REVIEW -> MERGE -> BYTES AGAIN**

If any arrow is unverified, the publication is not finished.
