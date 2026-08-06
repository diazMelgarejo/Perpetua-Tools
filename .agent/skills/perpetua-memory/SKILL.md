---
name: perpetua-memory
version: 2026-08-06
triggers:
  - "stage lesson"
  - "graduate lesson"
  - "memory consolidation"
  - "reanchor memory"
  - "AGENT_LEARNINGS"
  - "lessons.jsonl"
  - "append-only record"
tools: [learn.py, graduate.py, memory_reflect, bash, git]
preconditions:
  - ".agent/memory/episodic/AGENT_LEARNINGS.jsonl exists"
  - ".agent/memory/semantic/lessons.jsonl exists"
constraints:
  - "never mutate append-only historical records in place"
  - "never naive-union episodic/lessons files during branch consolidation"
---

# Perpetua Memory — first-time-right operations (PT canonical)

Use this skill **before** any change under `.agent/memory/`. It complements
`memory-manager` (consolidation cadence) with **integrity gates** that prevent
the recurring Cursor-agent failures: in-place lesson edits, duplicate episodic
rows, and stale-branch memory unions.

## When to load

- Staging or graduating a lesson (`learn.py`, `graduate.py`)
- Consolidating stale branches that touch memory files
- Fixing review findings on lessons, candidates, episodic, or `LESSONS.md`
- Any `git checkout --theirs` on `.agent/memory/**` during conflict resolution

## Append-only doctrine (non-negotiable)

1. **Never rewrite** an existing row in `lessons.jsonl`, `AGENT_LEARNINGS.jsonl`,
   or `candidates/graduated/*.json` to fix wording — even if the original is wrong.
2. **Correct fix:** new record + link to the old id:
   - `lessons.jsonl`: `graduate.py --supersedes lesson_<old_id>`
   - `candidates/graduated/<id>.json`: add `"related_lesson_ids": ["lesson_<old_id>"]`
     (do **not** use unsupported `supersedes` / `superseded_by` keys in graduated JSON)
3. `LESSONS.md` is **rendered** from `lessons.jsonl` — regenerate via
   `python3 .agent/memory/render_lessons.py` after semantic changes; do not hand-edit
   bullets except during migration.
4. `git checkout --theirs` on a graduated JSON file is a **whole-file overwrite** —
   same violation as in-place edit. Restore original bytes from `origin/main`, then
   supersede properly.

## Staging a lesson (happy path)

```bash
python3 .agent/tools/learn.py "<claim >= 20 chars>" \
  --rationale "<why>" \
  --conditions "tag1" "tag2"   # optional; omit to auto-tokenize from claim
```

- Creates staged candidate under `.agent/memory/candidates/<id>.json`
- Mirrors episodic row (`manual-stage:<id>`) with matching `evidence_ids`
- Auto-graduates unless `--stage-only`

## Graduating with supersession

```bash
python3 .agent/tools/graduate.py <candidate_id> \
  --rationale "<why accepted>" \
  --supersedes lesson_<old_id>    # when replacing prior guidance
```

After graduation, if the graduated JSON supersedes another lesson, add:

```json
"related_lesson_ids": ["lesson_<old_id>"]
```

to the **graduated** candidate file when `graduate.py` did not write it (audit-trail
queryability for append-only cross-links).

## Branch consolidation / reanchor (memory files)

**Before** unioning memory from stale branches:

1. `git fetch origin main`
2. Fresh worktree from `origin/main` (see `git-history-surgery` → CLAYGO protocol)
3. Per branch: `git cherry -v origin/main <tip>` + `git diff --stat origin/main...<branch>`
4. **Skip** if cherry `-` only, empty three-dot diff, or tree-twin on main
5. **Never** `cat >>` / line-append union on `AGENT_LEARNINGS.jsonl` — grep for
   existing `action:` / `lesson_` ids first; import only genuinely missing rows
6. Skip `is_legacy_episodic_row()` shapes (`{date, summary, tags}` without canonical fields)
7. Reject `post-tool` rows with `detail: "ok"` and empty `evidence_ids`

## Validation before commit

```bash
# JSONL line validity
python3 -c "
import json, pathlib
for p in pathlib.Path('.agent/memory').rglob('*.jsonl'):
    for i,l in enumerate(p.read_text().splitlines(),1):
        if l.strip(): json.loads(l)
print('jsonl ok')
"

# Re-render semantic markdown if lessons.jsonl changed
python3 .agent/memory/render_lessons.py

# Repo hygiene (path leaks, etc.)
python3 scripts/review/repo_hygiene.py --scope .agent/memory || true
```

## Anti-patterns (seen in production)

| Failure | Symptom | Fix |
|--------|---------|-----|
| In-place lesson edit | `git checkout --theirs` on graduated JSON | Restore + supersede |
| Missing supersession link | Rationale says "supersedes" but no `related_lesson_ids` | Add field to graduated JSON |
| Stale-base memory union | Duplicate legacy G5 rows, post-tool noise | Diff-gate per row id |
| Wrong git rollback lesson | `branch -f` described as silent no-op | Supersede with tested behavior |

## Related skills

- `memory-manager` — reflection cadence, distillation, search
- `git-history-surgery` — fresh-main CLAYGO, reanchor_scan, path-scoped replay
- orama `using-git-worktrees` — ephemeral baseline worktrees
