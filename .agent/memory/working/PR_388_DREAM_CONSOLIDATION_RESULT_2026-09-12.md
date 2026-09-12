# PR #388 Dream Consolidation Result — 2026-09-12

**Scope:** Perpetua-Tools PR #388 memory-corruption / remote-integrity incident arc.  
**Execution environment:** GitHub Actions on the exact PR branch, using PT's tracked
`.agent/memory/auto_dream.py` and canonical `.agent/tools/learn.py` paths.

## Why the Dream cycle ran remotely

The active ChatGPT Work sandbox could read/write through the connected GitHub
integration but could not materialize the repository through ordinary shell Git
transport. Rather than simulate Dream or reconstruct the memory tree from tool
output, a one-shot branch-scoped GitHub Actions runner checked out the exact PR
branch, executed PT's native memory tools, validated their outputs, committed the
result, and deleted its own helper/workflow files.

This is itself an application of the incident lesson: use an authoritative raw
repository checkout for a whole-repository mutation instead of rebuilding large
memory files through truncated display/API output.

## First Dream pass

The first successful native Dream pass ran before the three additional
limited-sandbox lessons were taught:

```text
dream cycle: patterns=50 staged=0 prefiltered_out=0 pending_review=0 archived=0 kept=790
```

No new candidate needed staging; the existing Base64 and four-integrity-facts
lessons already covered the principal incident pattern.

## Canonical lesson enrichment

Three sandbox-specific rules were then graduated through `learn.py` (not by
hand-editing `lessons.jsonl`):

- `lesson_740a99f625ca` — local Git credentials, `gh` CLI authentication, and
  connected GitHub App/API authorization are separate authority planes;
- `lesson_566a72e30743` — apparent mass deletion in a partial or
  not-yet-materialized checkout is checkout-state ambiguity until the exact ref
  and objects are fetched/materialized;
- `lesson_7de08a67fea1` — displayed/truncated tool output is not a safe transport
  for reconstructing large tracked files; use raw Git/blob/file transport or an
  explicit byte-offset manifest plus final byte-count/hash verification.

`DOMAIN_KNOWLEDGE.md` was also enriched with a concise pointer and summary of the
full semantic reference:

```text
.agent/memory/semantic/
REMOTE_CONTENT_INTEGRITY_AND_LIMITED_WORKSPACE_DOMAIN_KNOWLEDGE_2026-09-12.md
```

## Final Dream pass

After the three canonical lessons were graduated, the native Dream cycle ran
again:

```text
dream cycle: patterns=50 staged=0 prefiltered_out=0 pending_review=0 archived=0 kept=793
```

This indicates that the manually graduated incident lessons already covered the
reusable patterns strongly enough that Dream did not stage additional review
candidates.

## Validation performed in the runner

Before committing the Dream/enrichment result, the one-shot runner performed:

- Python compilation of the memory scripts/helper;
- JSON parsing of every tracked memory `*.jsonl` row;
- regeneration of `semantic/LESSONS.md` from canonical `lessons.jsonl`;
- `scripts/review/repo_hygiene.py`;
- `tests/test_periscope_lesson_supersession.py` via `unittest`:
  4 tests passed, including the invariant that every accepted graduated
  candidate must exist in canonical `lessons.jsonl`;
- `git diff --check`.

The helper and workflow deleted themselves in the successful commit, leaving
only durable `.agent/memory` changes.

## Safe failed attempts

Two intermediate attempts did **not** publish partial memory mutations:

1. the first enrichment workflow was rejected before jobs started because its
   YAML structure was too complex;
2. the simplified runner first used the wrong `.agent` root, then a subsequent
   run successfully enriched/dreamed but stopped at `git diff --check` because
   `DOMAIN_KNOWLEDGE.md` had one extra blank line at EOF.

Because validation preceded the commit/push step, those failed attempts left no
partial memory commit. The final run normalized the EOF, repeated the entire
canonical enrichment + Dream process from the branch state, passed validation,
and only then committed.

## Related durable records

- narrative incident record:
  `.agent/memory/working/MEMORY_CORRUPTION_INCIDENTS_AND_REMOTE_INTEGRITY_GATES_2026-09-10_TO_2026-09-12.md`;
- operator reconstruction source:
  `.agent/memory/working/PR_388_CHATGPT_WORK_INCIDENT_RECONSTRUCTION_SOURCE_2026-09-12.md`;
- semantic domain model:
  `.agent/memory/semantic/REMOTE_CONTENT_INTEGRITY_AND_LIMITED_WORKSPACE_DOMAIN_KNOWLEDGE_2026-09-12.md`;
- original graduated integrity lessons:
  `lesson_2d3ced9f9317` and `lesson_d7a13d8bc5fb`;
- limited-sandbox graduated lessons:
  `lesson_740a99f625ca`, `lesson_566a72e30743`, and
  `lesson_7de08a67fea1`.

## Outcome

PR #388 now preserves the source reconstruction, the corrected forensic
narrative, stable domain knowledge, five focused graduated lessons, canonical
rendered lessons, episodic evidence, and the result of an actual PT Dream cycle.
No merge is implied or authorized by this record.
