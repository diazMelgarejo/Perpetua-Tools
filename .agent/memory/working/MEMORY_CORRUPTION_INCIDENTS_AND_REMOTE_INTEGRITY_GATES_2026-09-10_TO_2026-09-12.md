# Memory-Corruption Incidents and Remote-Content-Integrity Gates (2026-09-10 to 2026-09-12)

**Provenance, stated explicitly throughout this document, not left implicit:**
sections marked **[direct]** were found, diagnosed, and repaired by this
Claude session directly, with commands and evidence reproduced in this same
session. Sections marked **[relayed]** are reconstructed from the operator's
own report of a separate agent session's work; that session is no longer
able to publish or verify further, and its cited local commit (`e494e85`)
is not reachable from any clone available to this session — confirmed by
`git cat-file -t e494e85` returning "not a valid object name" against a
fresh `origin` fetch. Where a relayed claim could be independently checked
against a real, reachable artifact (a PR, a blob SHA, a byte count), that
check was performed and is reported as such; where it could not, it is
reported as relayed and unverified, not as fact.

Two lessons distilled from this whole arc are graduated separately:
`lesson_2d3ced9f9317` (the Base64 chunk-size mechanism) and
`lesson_d7a13d8bc5fb` (the four integrity levels). This document is the
narrative and technical detail behind those two lessons — read it when a
future agent needs the full mechanism, not just the rule.

## Timeline

### 1. `294f5ec9` — the first wholesale-deletion incident **[direct]**

A commit intended to add one new lesson (`lesson_66b917484d5e`, about
git-merge scope) instead net-deleted 34 lines from
`.agent/memory/semantic/lessons.jsonl` — confirmed via an exact before/after
ID-set diff against the commit's own parent, not inferred from symptoms.
31 of the 34 dropped lines were legitimate, previously-accepted lesson
records, silently gone with no test failure at the time, since nothing
was checking for this failure mode yet.

Repair: restored the 31 records from the parent commit, then found a
*second*, wider version of the same gap by cross-checking every graduated
candidate file directly against `lessons.jsonl` — 21 more records marked
`accepted` in their own candidate file were never written to the canonical
store at all, a gap in the graduation pipeline itself, unrelated to
`294f5ec9`'s specific deletion. Reconstructed all 21 using `graduate.py`'s
own exact candidate-to-lesson field mapping (read from source, not
guessed), via the canonical `append_lesson()` function.

Two structural defects found during that reconstruction, also fixed:
5 pre-existing duplicate IDs with identical claim text but divergent
condition tag-sets (merged, union of tags, nothing lost); one
reconstructed candidate's `supersedes` field was a 2-element list, which
crashed `render_lessons.py`'s `superseded_by_map()` (a dict key must be
hashable) — narrowed to the single schema-conforming target the claim text
itself identified as the true supersession, the weaker "extends" relation
preserved as a condition tag rather than silently dropped.

Regression added: a test that walks every graduated candidate file and
asserts every `accepted`-status one has a corresponding `lessons.jsonl`
entry — confirmed RED against the unrepaired state (44 missing) before
restoring GREEN. This is the test that would have caught `294f5ec9`
immediately instead of silently, had it existed first.

### 2. `f1408af1` — the second wholesale-deletion incident, already self-corrected **[direct, verified]**

While checking PT's recent history for *further* instances of the same
class of bug (prompted by a direct operator question about accidental
deletions), found a second, independent occurrence: `f1408af1` reduced
`lessons.jsonl` from 1,226 valid JSON records to a 493-physical-line blob:
492 valid JSON records and one malformed first line with a binary prefix. The
ID-set difference was 735 deleted IDs (not the surviving record count), and it
inflated
`AGENT_LEARNINGS.jsonl` from 782 to 2273 lines. The very next commit,
`5c97b162` ("fix(memory): preserve canonical JSONL blobs"), had already
caught and repaired it before this session found it.

Verified the repair was genuinely complete, not just line-count-coincidental:
zero lesson IDs remained missing after `5c97b162` (confirmed by set-difference
against the pre-drop ID set), and `AGENT_LEARNINGS.jsonl`'s post-repair
content was byte-for-byte identical to its pre-incident state (`diff`
returned empty). A broader sweep of the surrounding 20 commits found
nothing else with a similarly dramatic, unexplained line-count swing.
Nothing needed restoring — this entry exists so a future agent doesn't
re-discover and re-investigate the same already-closed incident.

### 3. `ae52aff` — the third incident, today's, in a different repository **[direct]**

While migrating `oramasys/oramasys`'s `route_node` to consume
`oramasys/agate` as the canonical v2 hardware-policy authority (closing a
real architectural violation: `perpetua_core.policy.HardwarePolicyResolver`
was a second, independent policy implementation embedded inside the core
scheduler package, contrary to PT's own recorded "core never imports
upward from policy" migration invariant), the deprecated compatibility
wrapper in `perpetua-core` needed its own dependency posture decided:
should `agate` be a hard dependency, dev-only, or something else.

First pass (this session): dev-only. A later commit by another agent
session, `02ab8e1`, correctly tightened this further — removed `agate`
from *all* declared dependencies, reasoning that even a dev-only
declaration meant `perpetua-core`'s own package metadata named a
dependency on the policy layer it's supposed to have zero relationship
with. Sound reasoning, verified independently in this session by
reinstalling with only `.[dev]` and confirming `import agate` genuinely
raises `ImportError`.

The very next commit, `ae52aff` ("test(policy): normalize dependency names
in boundary check"), is where the actual corruption happened. Its commit
message describes a small, targeted test fix — normalizing package-name
comparisons (hyphens vs. underscores) in a boundary-check test. Its actual
diff, found by this session while investigating an unrelated operator
question about the current dependency posture, showed the entire 179-line
`src/tests/test_policy.py` replaced with corrupted binary bytes — confirmed
directly: `file` identified the committed blob as binary "data," zero
parseable lines, `ast.parse()` failing outright. Both CI matrix jobs
(pytest 3.11 and 3.12) were failing on `main`'s actual current tip at the
moment this was found — not a hypothetical or a stale report, checked
directly against the live GitHub Checks API.

Repair (this session): restored the file from `02ab8e1`, the last commit
with genuinely valid content, verified parseable as Python before trusting
it. A second, separate gap found while fixing this: `02ab8e1`'s dependency
removal had no accompanying CI change, so even with the corruption fixed,
the tests exercising real delegation to `agate.PolicyStore` would still
fail in CI with `ModuleNotFoundError` — a different failure, but still a
failure. Fixed with a workflow-level `pip install`, then annealed (at the
operator's own prompt to look for a more elegant fix) into a properly
named, version-controlled optional-dependency group
(`test-agate-compat`) instead of a bare string duplicated outside
`pyproject.toml` — verified end-to-end both ways: a plain `.[dev]` install
still has zero agate (the intended invariant holds), `.[dev,test-agate-compat]`
brings in both packages and the full suite passes (140/140, 84.69% coverage).

A fourth commit landed after this session's restoration,
`9b64569` ("test(policy): preserve canonicalized dependency boundary
guard") — this is, itself, the *correct, working* version of what
`ae52aff` was trying and failing to do: replaced the boundary check's
fragile string-splitting (vulnerable to being fooled by literal text
matches or file reordering) with real `tomllib` parsing and PEP
503-style name normalization. Verified independently: the file's exact
byte size (6,601) and Git blob SHA (`604d45ecebe653fe7463a9d7d422edff10d3e0ad`)
were reproduced directly in this session and matched what the other
agent's own report separately claimed — real, independent confirmation
from two different sessions computing the same hash over the same
content, not one session trusting the other's assertion.

### 4. The Base64/chunking root cause behind `ae52aff` **[relayed, mechanism independently reproduced]**

The operator relayed a diagnosis from the other, no-longer-reachable agent
session: the corruption's root cause was a chunked Base64 publication path
using a chunk size not divisible by 3, and the fix was to use 12,288-byte
chunks (a multiple of 3) with exact Git blob SHA equality required before
any tree write.

This session did not witness that diagnosis process directly and cannot
verify the specific tool or API call that produced the corruption. What
this session *did* do: independently reproduce the underlying mechanism
with real code, to confirm the relayed diagnosis was mechanistically
sound rather than accepting it on report alone. Full reproduction and
result:

```python
import base64
raw_data = b"A" * (12288 * 2 + 1)

# Multiple of 3: 12288 = 4096 * 3
chunks_good = [raw_data[i:i+12288] for i in range(0, len(raw_data), 12288)]
encoded_good = [base64.b64encode(c) for c in chunks_good]
decoded_good = base64.b64decode(b"".join(encoded_good), validate=True)
assert decoded_good == raw_data
# -> no padding in any non-final chunk; naive concatenation decodes
#    back to the original bytes exactly.

# NOT a multiple of 3: 7000
chunks_bad = [raw_data[i:i+7000] for i in range(0, len(raw_data), 7000)]
encoded_bad = [base64.b64encode(c) for c in chunks_bad]
# -> the first chunk's encoding ends in '=' padding even though more
#    data follows; the strict Python decoder rejects the concatenated stream.
#    This is deliberately a decoder-specific reproduction, not a claim about
#    every decoder or a safe substitute for length/hash verification.
```

This confirms only the reproduced producer/decoder contract: Python
independently Base64-encodes each raw chunk, concatenates the encoded chunks,
then Python `base64.b64decode(..., validate=True)` decodes once. Base64 encodes
3 raw bytes into 4 output characters, so a non-3-byte interior boundary creates
interior padding. This decoder rejects the malformed stream rather than silently
truncating it. Other decoders may stop at the first padding marker or behave
differently, so no broader behavior is claimed. APIs that decode each part
separately do not require 3-byte alignment. Record the producer/decoder contract
and validate final decoded length and a cryptographic hash. The 79-byte payload
is evidence of a failed publication path, not proof that every decoder silently
truncates.

### 5. The four integrity levels **[relayed, reasoning independently sound]**

The other agent's own retrospective, relayed by the operator, named the
specific process failure precisely: it conflated four things that are not
equivalent — (1) local file validity, (2) API write acknowledgment or
returned SHA, (3) remote object integrity at the exact branch head, and
(4) merged destination integrity. It checked (1), then treated a
successful (2) as if it proved (3), and merged without ever separately
checking (3) or (4).

This session did not witness the specific verification steps that were
skipped, but the reasoning is sound on its own terms and consistent with
what this session found directly in incidents 1–3 above: in every one of
those, per-step tool calls (a `git commit`, a graduation script run, a CI
install step) reported success, and the actual corruption was only found
by a *separate*, *later* check that re-read the real content rather than
trusting the prior step's own report of success. The four-level framing is
a correct, generalizable name for the pattern this session independently
encountered three times without originally having that name for it.

## What shipped from this arc

- `oramasys/perpetua-core` PR #6: the corruption repair plus the
  elegance follow-up (named optional-dependency group). Deliberately
  left unmerged pending CodeRabbit review, per explicit operator
  instruction — do not merge ahead of automated review even when the
  fix is independently verified.
- `diazMelgarejo/orama-system` PR #357 (opened by the other agent
  session, extended by this one, not duplicated): CIDF now requires the
  three remote-content-integrity gates plus a post-merge recheck; a
  dedicated reference card; the 79-byte incident as a worked example;
  this session's own addition of the verified Base64 chunk-size
  mechanism and the four-level distinction, with working reproduction
  code, for a future agent's benefit specifically in a limited sandbox
  without desktop tooling, where this level of mechanism detail is the
  difference between recognizing the failure mode and repeating it.
- Two graduated lessons in this PT repository: `lesson_2d3ced9f9317`
  and `lesson_d7a13d8bc5fb`, both cross-referencing PR #357 for full
  detail rather than duplicating it here at lesson-entry length.
- The regression test from incident 1 (every accepted graduated
  candidate must appear in `lessons.jsonl`) remains the one piece of
  this whole arc that would have caught a wholesale-deletion incident
  automatically rather than requiring a human or agent to notice
  something felt off. No equivalent automated check yet exists for the
  `ae52aff`-class corruption (a file replaced with valid-looking-length
  binary garbage) — a gap named here, not yet closed.


## Directly Observed ChatGPT Work / Remote-Workspace Constraints **[direct, follow-up session]**

This follow-up session ran in the same class of ChatGPT Work sandbox as the
agent whose report initiated this incident record. The following constraints
were directly observed here. They are added as operational context, not
retroactive proof of the prior agent's exact implementation or root cause.

### Split authentication planes

The local shell and the connected GitHub integration are separate
authentication planes. A local `git push` failed with
`could not read Username for 'https://github.com'`, while the authenticated
GitHub integration could read PR #388, update its existing branch, and return
commit and blob identifiers. Therefore:

- never infer local Git transport authority from a working GitHub app;
- never infer GitHub-app write authority from a local CLI failure;
- choose the authorized path deliberately, then independently fetch the remote
  result from the exact branch after each consequential write.

This distinction is especially important in a sandbox without an interactive
credential prompt, stored desktop keychain, or a configured `gh` session.

### Checkout state is evidence, not truth

A no-checkout/partial clone initially left this session's worktree reporting
a very large set of tracked files as deleted. The intended PR ref was not yet
materialized locally. After fetching the exact pull-request ref and switching
to a detached checkout of it, the apparent mass-deletion state disappeared.

Treat that symptom as an incomplete checkout state until proven otherwise:

1. inspect the current ref and whether the requested object exists;
2. fetch the exact PR head/ref explicitly;
3. use a detached, exact-SHA checkout for review;
4. only then interpret `git status`, diffs, file counts, or deletions.

Do not repair, stage, commit, or publish an apparent mass deletion before this
sequence. In shared and ephemeral workspaces, an incomplete checkout is a more
plausible first hypothesis than a request to delete the repository.

### API-writing constraints and safe publication

Remote-workspace APIs may expose a text-oriented file-write operation even
when local Git transport is unavailable. Prefer that UTF-8 path for UTF-8
source and documentation files. Do not invent a chunked Base64 reconstruction
path merely to work around a missing local push; if an API requires Base64,
document whether it accepts one complete payload or separately decodes each
part before choosing a multipart protocol.

For every path, validate four distinct facts:

1. local intended content is parseable/valid;
2. the write endpoint acknowledges the request;
3. a fresh remote read at the exact branch head has the intended bytes and
   expected Git blob SHA;
4. after any authorized merge, the destination ref has those same bytes.

A returned SHA is useful evidence but does not replace the later exact-ref
read. Output truncation, partial clones, missing decoders, and unavailable
interactive auth are environmental constraints—not excuses to collapse these
four gates.

### Relationship to the reconstructed Base64 incident

This session did **not** reproduce the earlier binary corruption: the
connected GitHub integration accepted direct UTF-8 writes. It did reproduce
the underlying operational pressure that can lead an agent to unsafe content
reconstruction: local Git transport was unavailable while remote API writes
remained available. The earlier Base64 account remains marked **[relayed,
mechanism independently reproduced]**. These follow-up observations are
**[direct]** and should not be conflated with a claim that the same exact API
or decoder was used by the prior agent.
