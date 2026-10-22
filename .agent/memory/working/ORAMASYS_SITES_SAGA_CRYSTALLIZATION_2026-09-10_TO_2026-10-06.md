# Oramasys Sites saga — crystallization and gold nuggets

**Purpose.** This is the durable, additive account of the arc that began with memory/content-integrity failures and ended, for this phase, at the stacked review repairs in PT #429 and Orama #387. It is a handoff, not a substitute for fetched repository state, CI, CodeRabbit, or owner acceptance.

**Evidence vocabulary.**

- **Verified** means a reachable artifact, local test, or fresh remote read was checked in the relevant session.
- **Relayed** means it came from the owner or a defunct earlier agent session. It may be mechanically plausible, but is not silently upgraded to fact.
- **Not verified** means an important question remains open. It is deliberately retained so a later agent does not claim it by implication.

## Executive thread

This was never only a Sites implementation. It began with a harder lesson: normal-looking success signals can coexist with destroyed bytes. PT memory was rewritten, a Python test in another repository became binary garbage, and an earlier ephemeral Work session could no longer be interrogated. The repair therefore evolved from “fix a file” into a discipline:

1. preserve historical evidence;
2. distinguish local correctness from remote correctness;
3. make validation independent from the mechanism being validated;
4. separate access/authentication claims from UI and deployment claims; and
5. leave a route that a future agent can reproduce without trusting prose.

The Sites/MCP work applied those disciplines to a concrete v1 product: a private prompt-contract workspace. PT remains the canonical compiler, schema and store contract; Orama owns reviewed snapshots, assembly, verification, local preview and the HTTP/UI adapter; Sites owns deployment identity, audience control and D1. The implementation deliberately does not claim model inference, local-process execution, a privileged portal, or a production operation controller.

## Timeline

### 1. The integrity incidents established the real problem

In September, direct review of PT history found two separate wholesale memory loss incidents. One small lesson addition removed legitimate semantic lesson records. A later incident reduced the canonical semantic corpus and damaged episodic history; a following repair restored the known-good bytes. A graduated-candidate-to-canonical-store regression was added because a rendered file looking plausible was not enough evidence that every accepted record survived.

In a separate repository, a supposedly small dependency-boundary test change was found to have replaced a Python test with binary data. The valid source was restored from the last known-good revision, parsed as Python, and verified by byte size and Git blob identity. The boundary test and optional test dependency posture were separately repaired. This demonstrated that a mundane commit message, an accepted write, and even a narrow-looking diff description do not prove the target bytes are usable.

An earlier Work session reported a chunked Base64 publication workaround after ordinary local Git transport was unavailable. Its claimed local commit was not reachable later, so the specific publication sequence is **relayed**. The underlying hazard was independently reproduced: independently encoded raw chunks concatenated for one final decode need non-final raw boundaries divisible by three, or interior padding makes the combined stream invalid for strict decoders. The safe conclusion is narrower than “Base64 is broken” and narrower than “12,288 is magic”: know the producer/decoder contract, prefer UTF-8 content writes when supported, and verify the final bytes remotely.

The resulting incident sources remain authoritative for detailed evidence:

- `.agent/memory/working/MEMORY_CORRUPTION_INCIDENTS_AND_REMOTE_INTEGRITY_GATES_2026-09-10_TO_2026-09-12.md`
- `.agent/memory/working/PR_388_CHATGPT_WORK_INCIDENT_RECONSTRUCTION_SOURCE_2026-09-12.md`
- Orama CIDF remote-content-integrity reference card.

### 2. The repair became a remote-content-integrity protocol

The durable correction was to stop treating four different facts as one:

| Fact | What establishes it | What it does **not** establish |
| --- | --- | --- |
| Local validity | parse/compile, byte count, local hash/blob | remote bytes |
| Write acknowledgement | API success or returned identifier | branch content |
| Exact remote-head integrity | fetch the exact branch head, parse and compare expected bytes/hash | destination after merge |
| Destination integrity | re-fetch destination after merge and repeat checks | prior gates retroactively |

For consequential writes, an agent records local bytes before publishing, reads the exact remote branch after writing, repeats that check immediately before merge, and reads the destination after merge. A returned SHA is useful only as a hypothesis to verify. When local Git credentials are absent but an authenticated GitHub integration works, that is an authority boundary—not permission to skip remote verification or invent a lossy transport.

### 3. The v1 Sites/MCP vertical slice was deliberately bounded

The approved work created a small private prompt workspace rather than pretending that a browser Worker can run the legacy local orchestration stack. The contract has five tools: deterministic preparation, save, list, get and archive. Original prompts preserve whitespace, Unicode and line endings; idempotent retries use owner-scoped request keys; changed content under the same key conflicts rather than overwrites; archive retains rather than erases.

The first implementation/assembly work established several boundaries:

- snapshots of PT compiler/schema must be byte-identical before assembly;
- the assembled Site records provenance and is verified read-only;
- a local Worker uses an isolated child runtime, preserving host proxy/CA settings and avoiding tracked runtime state;
- synthetic local identity proves local isolation only and is never evidence of a hosted user identity;
- HTTP status is handled before JSON parsing, so plain-text gateway denial produces an actionable message rather than a parser error; and
- private Site access is controlled at the hosting boundary, not supplied by prompt-tool arguments.

The first audit correctly kept several claims separate: source registration, source upload, Site deployment, plugin installation, authenticated plugin calls, browser login, and two-user hosted isolation are distinct checkpoints. No single green UI, API acknowledgement, or local smoke test can collapse them.

### 4. Readiness r2 caught failures that a build did not

The r2 readiness pass discovered that a fresh production build could still omit the history-index migration needed for the actual paginated query. The independent verifier therefore compares the assembled bytes, parses metadata, applies candidate migrations only in memory, compares schema/index semantics, probes idempotency and archive constraints, and captures actual query plans. It never assembles or repairs the artifact it examines.

Local preview had a second, separate failure mode: Wrangler configuration lookup, logs, registries and D1 persistence are different paths. A synthetic bad home reproduced the startup failure; explicit child-scoped XDG state restored readiness without replacing the developer's host environment. Symlink ancestors of runtime, D1 and configuration paths must be resolved before containment checks. Cancellation must stop the owned detached Worker group and remove only disposable runner state.

The private Site was then published under the existing owner-only policy. Anonymous Site/MCP/history requests were denied. The installed plugin later made authenticated native calls for preparation, history, save/get, idempotent retry and changed-payload conflict. A long approved plan exceeded one original field and was stored as ordered byte-preserving parts, then read back and reconstructed exactly. This is evidence for that plugin session, **not** for browser login or a second user's isolation.

### 5. Review improved the verifier and the memory record

Code review of the first readiness PR caught practical gaps:

- literal loopback addresses violated repository hygiene;
- a broad `lib/` ignore rule could hide real Site overlay source;
- the verifier needed to compare every migration file that Wrangler would apply, not merely files named in the journal;
- the UI should show well-formed Site JSON-RPC errors without exposing raw provider bodies; and
- status text must be corrected additively when a previously blocked gate later passes.

The resulting Orama leaf PR replaced repeated address literals with the named `localhost` host, un-ignored the Site overlay source directory, checked migration-directory/journal equivalence, and refined the response decoder.

The next review found three subtler verifier defects, reproduced as failing tests and repaired in the same leaf:

1. an invalid or out-of-range `--index-only-from` boundary could silently disable the intended check;
2. naïve line-comment stripping could hide DML following comment syntax; and
3. simple semicolon splitting rejected valid quoted index identifiers.

The verifier now requires a real journal index and classifies statements outside comments and quoted tokens before SQLite validates the candidate SQL in memory. The refreshed adapter suite and real built-Worker/D1 smoke passed locally. That evidence is local, with synthetic identities; it is not a replacement for hosted browser validation.

PT's companion review identified a memory-authority error: a lesson had been hand-added to the retired `docs/LESSONS.md` log instead of through the canonical semantic workflow. The repair was deliberately narrow. Existing `learn.py` staged evidence and invoked `graduate.py`; the resulting `lessons.jsonl`, rendered semantic `LESSONS.md`, episodic mirror and graduated candidates became the canonical record. The retired docs log, `graduate.py`, and the renderer were left unchanged. Both historical JSONL prefixes were checked byte-for-byte; only new suffix records were appended.

## The gold nuggets

These rules are reusable beyond this saga. They complement—not replace—the more compact graduated lessons and the detailed incident records.

1. **Treat every success signal as scoped evidence.** “The API returned 200,” “the tool installed,” “the page rendered,” and “the test passed” each answer a different question. State exactly which one.
2. **A verifier must mirror the real applier.** If the runtime applies every SQL file in a directory, validating only a friendly journal is a false guarantee. Test the real execution order and file set.
3. **Verification must not repair its subject.** A tool that assembles, migrates or normalizes while checking can turn a broken candidate into the evidence of its own correctness.
4. **Preserve original bytes before improving behavior.** Memory, prompt originals, migrations and incident evidence are audit inputs. Append a supersession or status update; do not edit history to make it read better.
5. **Generated outputs have one authority.** For PT semantic lessons, `lessons.jsonl` plus the graduation path are authoritative and the semantic markdown is derived. Do not revive an obsolete renderer merely to satisfy a generic review suggestion.
6. **Check the exact remote ref, not an earlier local intention.** API acknowledgements, local blobs and stale tracking branches are not the branch users/reviewers will merge. Fetch the exact head and compare full trees.
7. **A narrow transport workaround is not a general rule.** Base64 alignment depends on independently encoded chunks being concatenated for one decode. Prefer direct UTF-8 writes; if encoding is forced, define the exact producer/consumer contract and verify decoded length/hash.
8. **Local identity tests prove only local identity behavior.** They cannot establish the host's OAuth session, access policy, browser flow or another user's isolation.
9. **Cancellation is a correctness path.** A test runner that leaves a Worker, runtime directory or persistent test state behind converts a passing test into a later non-deterministic failure.
10. **Review feedback is input, not authority.** Verify it against this repository's architecture. The PT renderer recommendation had a sound canonical-source concern but an incorrect retired-output remedy; the correct fix used graduation without expanding the old path.
11. **A field-size limit needs an explicit lossless protocol.** Split at a byte-safe natural boundary, preserve ordering without injected separators, read every part back, reconstruct, and hash the whole.
12. **Crystallization has three layers.** Keep a factual working narrative for context, compact graduated lessons for recall, and episodic evidence for audit. Collapsing them into one format loses either provenance or usability.

## Current closure state and future-agent starting point

The active work is on stacked leaf PRs above the first readiness pair:

| Scope | Current role | Do not infer |
| --- | --- | --- |
| PT #428 | original memory/readiness branch | that its original wording reflects later hosted evidence |
| PT #429 | canonical-memory and status/review repairs | that the retired docs log should be regenerated |
| Orama #386 | original implementation/readiness branch | that its local tests prove hosted login |
| Orama #387 | leaf review repairs and stronger verifier | that its branch is deployed or merged |

Before any merge, re-fetch the live PR heads, inspect current CodeRabbit and CI, and rerun the relevant integrity gate. No merge is authorized by this record. Owner browser login, genuine two-account hosted isolation, and the separately authorized forged-header probe remain distinct acceptance work. The first-publication reversal gate was not established before the earlier release; retaining a prior version is not proof that a D1 rollback was tested.

## Future agent checklist

1. Start with this record, the readiness-boundaries note, and the remote integrity incident record; then fetch current remote state.
2. Decide whether the task is local, remote-branch, merge-destination, hosted authentication, or production operation work. Do not borrow evidence across those categories.
3. For memory changes, use `.agent/tools/learn.py` or the staged `graduate.py` workflow; validate structured JSONL and preserve the exact base prefix.
4. For Site/MCP changes, build the assembled artifact, run the independent verifier, then run the real local Worker smoke in a disposable runtime.
5. For remote publication, validate exact blob/tree equality after the write and again at the branch head. Never publish a reconstructed or chunked payload without end-to-end byte verification.
6. Report verified, relayed and unverified facts in separate sentences. A precise limitation is an operational asset, not an incomplete answer.

## Crystallization ruling

This record is additive because earlier records remain useful as evidence. It consolidates their causal chain and preserves their distinctions rather than rewriting them into a smoother but less auditable story. The enduring achievement is not a particular PR or one successful deployment: it is a repeatable method for preventing “successful” automation from silently changing the wrong bytes, asserting the wrong identity, or carrying stale knowledge forward.
