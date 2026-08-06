---
name: perpetua-memory
version: 2026-08-06.2
triggers:
  - "stage lesson"
  - "graduate lesson"
  - "memory consolidation"
  - "reanchor memory"
  - "mega-cleanup"
  - "housecleaning"
  - "graft-1"
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
  - "one branch, one squashed commit, one PR per repo for housecleaning"
---

# Perpetua Memory — first-time-right operations (PT canonical)

Use this skill **before** any change under `.agent/memory/`. It complements
`memory-manager` (consolidation cadence) with **integrity gates** that prevent
the recurring Cursor/cloud-agent failures: in-place lesson edits, duplicate episodic
rows, stale-branch memory unions, and the notorious **"1 commit off"** branch trap.

Anchoring lessons: `lesson_071ec367227c` (append-only supersede),
`lesson_9940e1aa6fc4` (`checkout --theirs` trap), `lesson_e276758511e6`
(`git branch -f` vs `update-ref`), `lesson_00f3e059181b` (reanchor cherry gate),
`lesson_5b40f288ce47` (worktree isolation).

## When to load

- Staging or graduating a lesson (`learn.py`, `graduate.py`)
- **Mega-cleanup v1** / pre-v2 housecleaning that touches memory or stale branches
- Consolidating stale branches that touch memory files
- Fixing review findings on lessons, candidates, episodic, or `LESSONS.md`
- Any `git checkout --theirs` on `.agent/memory/**` during conflict resolution
- Probing "graft 1 unique commit" remotes after `reanchor_scan.sh`

---

## Append-only doctrine (non-negotiable)

1. **Never rewrite** an existing row in `lessons.jsonl`, `AGENT_LEARNINGS.jsonl`,
   or `candidates/graduated/*.json` to fix wording — even if the original is wrong.
2. **Correct fix:** new record + link to the old id:
   - `lessons.jsonl`: `graduate.py --supersedes lesson_<old_id>`
   - `candidates/graduated/<id>.json`: add `"related_lesson_ids": ["lesson_<old_id>"]`
     (do **not** use unsupported `supersedes` / `superseded_by` keys in graduated JSON)
3. If rationale text mentions supersession but `related_lesson_ids` is missing,
   the audit trail is **broken** — CodeRabbit will flag it; fix before merge.
4. `LESSONS.md` is **rendered** from `lessons.jsonl` — run
   `python3 .agent/memory/render_lessons.py` after semantic changes; do not hand-edit
   bullets except during migration.
5. `git checkout --theirs` on a graduated JSON file is a **whole-file overwrite** —
   same violation as in-place edit (`lesson_9940e1aa6fc4`). Restore original bytes
   from `origin/main`, then supersede properly.

### Worked example (PT PR #332, review #4870664281)

| Mistake | Correct fix |
|---------|-------------|
| Mutated `e773f6f957c2.json` via `--theirs` during conflict | Restore bytes from `main`; graduate `071ec367227c` with `--supersedes lesson_e773f6f957c2` |
| Graduated JSON missing link | Add `"related_lesson_ids": ["lesson_e773f6f957c2"]` to `071ec367227c.json` |
| Wrong `git branch -f` claim in new lesson | Supersede `lesson_2546180f3d5b` → `lesson_e276758511e6` with tested behavior |

---

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

After graduation, add to the **graduated** JSON when `graduate.py` did not:

```json
"related_lesson_ids": ["lesson_<old_id>"]
```

---

## Mega-cleanup v1 — housecleaning pre-v2 migration

**Shape:** one branch · one squashed commit · one PR per repo.  
**Not:** one cherry-pick per stale remote (11 branches ≠ 11 commits).

Branch name convention: `cursor/mega-cleanup-v1-<suffix>` off fresh `origin/main`.

### Workflow

1. `git fetch origin main`
2. **Fresh detached worktree** from `origin/main` (`lesson_5b40f288ce47`) —
   never batch-reanchor in the live checkout other agents use
3. Inventory stale remotes:
   ```bash
   bash scripts/git/reanchor_scan.sh . origin/main remotes | rg 'graft 1 unique'
   ```
4. **Per candidate branch** — all three gates (never trust ahead/behind alone):
   ```bash
   git cherry -v origin/main <tip>           # + = missing, - = already in main
   git diff --shortstat origin/main...<ref>  # three-dot: net unique delta
   git rev-parse origin/main^{tree} <ref>^{tree}  # tree-twin check
   ```
5. **Classify** each branch (record proof in PR body before deletion):
   - **SHIP** — cherry `+`, non-empty three-dot diff, not a stale-base regression
   - **DELETE** — cherry `-` only, empty three-dot diff, tree-twin on main, or
     main is a **superset** of branch content
   - **DELETE (stale-base trap)** — cherry `+` but diff would **regress** current
     main (e.g. removes code main added later; massive `+29/-4174` LESSONS.md salvage)
6. **Harmonize** all SHIP deltas into **one squashed commit** on the mega-cleanup branch
7. Open **one PR**; list DELETE candidates with proof table; operator deletes remotes after merge

### Cursor-agent "1 commit off" bug (seen 2026-08)

| Pattern | Signal | Action |
|---------|--------|--------|
| Stale-base single commit | `1 ahead / N behind`, cherry `+` | Three-dot diff vs **current** main — may be obsolete |
| Ghost branch | `0 ahead / N behind`, agent still working on it | Checkout `main`; branch already merged |
| Naive episodic union | `cat >>` AGENT_LEARNINGS.jsonl during reanchor | Diff-gate per row id; see episodic gates below |
| Byte-identical absorb | Working file same on main, branch still `cherry +` | `diff` the specific paths; delete branch |
| Main superset | Branch removes ignores/config main already has | DELETE — do not ship |

---

## Branch consolidation / reanchor (memory files)

**Before** unioning memory from stale branches:

1. Follow mega-cleanup gates above
2. **Never** `cat >>` / line-append union on `AGENT_LEARNINGS.jsonl`
3. Grep for existing `manual-stage:<id>`, `lesson_<id>`, `action:` before adding rows
4. Skip rows matching `is_legacy_episodic_row()` in `.agent/harness/hooks/_episodic_io.py`
   — legacy `{date, summary, tags}` shapes; `auto_dream` skips them but they add noise
5. Reject low-signal rows: `post-tool` / `detail: "ok"` with empty `evidence_ids`
6. For `lessons.jsonl` union: **dedupe by `id`** — keep `main`'s row when ids collide
   (`lesson_00f3e059181b`: squash-merge patch-ids never match but content may be absorbed)
7. Verify specific lessons landed: `rg lesson_<id> .agent/memory/semantic/lessons.jsonl`
   before carrying a whole stale branch forward

### Episodic row acceptance checklist

- [ ] Canonical fields present (`timestamp`, `skill`, `action`, `result`, `detail`, `evidence_ids`)
- [ ] `evidence_ids` non-empty for non-trivial rows
- [ ] No duplicate of existing `legacy-daily-summary` or same `action:` key
- [ ] Not already on `main` (grep `action` / lesson id)

---

## Git rollback during branch probing

When cherry-picking candidates in a loop to test apply cleanliness:

- `git branch -f <name> <sha>` **refuses** to move the currently checked-out branch
  (exit 128, ref unchanged) — `lesson_e276758511e6`
- Use `git update-ref refs/heads/<name> <sha>` to move the ref
- Then sync index/worktree: `git restore --staged --worktree .` so the undone cherry-pick
  does not leave stale staged files

---

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

---

## Anti-patterns (production incidents)

| Failure | Symptom | Fix |
|--------|---------|-----|
| In-place lesson edit | `git checkout --theirs` on graduated JSON | Restore + supersede (`lesson_9940e1aa6fc4`) |
| Missing supersession link | Rationale says "supersedes" but no `related_lesson_ids` | Add field to graduated JSON |
| Stale-base memory union | Duplicate legacy G5 rows, post-tool noise (PT #332) | Diff-gate per row id |
| 11-branch → 11-commit PR | Housecleaning sprawl | Mega-cleanup: one squashed commit |
| Wrong git rollback lesson | `branch -f` described as silent no-op | Supersede (`lesson_e276758511e6`) |
| Trust cherry `+` alone | Branch looks unique, content on main via squash | `git diff main...branch` per path |
| Stale episodic on branch | `-1000 lines` vs main in working file diff | DELETE branch; content absorbed elsewhere |

---

## Related skills

- `memory-manager` — reflection cadence, distillation, search
- `git-history-surgery` — fresh-main CLAYGO, `reanchor_scan.sh`, path-scoped replay
- orama `using-git-worktrees` — ephemeral baseline worktrees
