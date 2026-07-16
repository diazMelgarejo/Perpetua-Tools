# DIAGNOSIS — learn.py manual-stage path skips the episodic mirror

Date: 2026-07-16
Discovered on: PT PR #246 (`pt-launcher-diagnostics-memory-replay`), during
CodeRabbit review 4717711505
Status: **diagnosed, fix not yet implemented** — this doc is the handoff so
the fix can land in a follow-up PR while the context is still fresh
Fixed symptom (already landed, `7a2e098`): reconstructed the one missing
episodic record by hand. This doc is about the *tool* bug, not that one
symptom.

---

## TODO (action item — pick one, don't skip both)

- [ ] **Preferred:** fix `.agent/tools/learn.py`'s `stage()` function to
      self-mirror to `AGENT_LEARNINGS.jsonl` at staging time (see snippet
      below), so this class of gap cannot recur for future manual stages.
- [ ] **Or, if the fix is deferred:** every future manual `learn.py` stage
      MUST be spot-checked for a matching episodic mirror before being
      treated as fully durable — do not assume parity with the auto-derived
      path until the fix lands.

One of these two must happen, not neither. The whole point of writing this
down is that "we'll just remember to check" is exactly the assumption that
failed the first time.

---

## Background — how this was found

1. PR #242 (`memory/launcher-read-only-contract-20260715`) captured a
   manually-taught lesson via `learn.py`: launcher diagnostics capability
   tiers (`--validate` must exit before any side effect; `--list` may read
   but must redact/gate topology). 4 files: a new graduated candidate JSON,
   2 `AGENT_LEARNINGS.jsonl` entries, 1 `LESSONS.md` bullet, 1
   `lessons.jsonl` entry.
2. #242 had 2 commits: the real content (`77e0909`) and a backmerge merge
   commit (`a125a0d`) that added no content of its own.
3. Per request, replayed only `77e0909` onto current `main` as PR #246
   instead of the backmerge-then-merge-again round trip — 2 clean commits,
   no merge commit. Cherry-pick hit 3 append-only-tail conflicts (all
   resolved as unions of both sides' additions, exact-duplicate lines
   deduped).
4. CodeRabbit review 4717711505 flagged: `24032d26aecc.json` and
   `lessons.jsonl` both carry `evidence_ids: ["2026-07-15T09:44:49.774953+00:00"]`,
   but no episodic record with that timestamp existed anywhere in
   `AGENT_LEARNINGS.jsonl`.
5. **Investigated before fixing** (per this project's standing discipline —
   verify, don't assume): checked whether the replay had dropped the entry.
   It hadn't. `git show 77e0909:.agent/memory/episodic/AGENT_LEARNINGS.jsonl`
   and `git show a125a0d:...` both come back with **zero** matches for that
   timestamp. The entry never existed in PR #242 either. The gap predates
   the replay entirely.
6. Read `24032d26aecc.json` directly: `"key": "manual_24032d"` — a
   manually-staged candidate, not auto-derived from a cluster. Its own
   `decisions[0]` entry (`staged_at`/`ts` = `2026-07-15T09:44:49.774953+00:00`,
   `reviewer: "learn"`) *is* the lesson-creation event the `evidence_id`
   refers to — it was just never mirrored into `AGENT_LEARNINGS.jsonl`.
7. Confirmed the neighboring entries in the same file (proactive-recall
   events at `09:44:39` and `09:45:03`, from the *auto-derived* path) DID
   mirror correctly — proving this is a manual-stage-specific gap, not a
   general episodic-logging failure.
8. Reconstructed the missing record by hand from the candidate's own
   already-existing fields (not invented content) and inserted it in
   correct chronological position (`7a2e098`).
9. Logged the meta-lesson explaining all of this, in the same PR branch as
   the lesson it should have covered — deliberately at the episodic level
   only (see "Meta-decision" below).

## Root cause — read directly from `.agent/tools/learn.py`

```python
def stage(claim, conditions, source="learn", importance=7):
    os.makedirs(CANDIDATES, exist_ok=True)
    cid = pattern_id(claim, conditions)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    candidate = {
        "id": cid,
        "key": f"manual_{cid[:6]}",
        "name": f"manual_{cid[:6]}",
        "claim": claim,
        "conditions": sorted(conditions),
        "evidence_ids": [now],
        "cluster_size": 1,
        "canonical_salience": 8.0,
        "staged_at": now,
        "status": "staged",
        "decisions": [{"ts": now, "action": "staged", "reviewer": source}],
        "rejection_count": 0,
    }
    path = os.path.join(CANDIDATES, f"{cid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(candidate, f, indent=2)
    return cid, path
```

This is the entire function. It writes the candidate JSON. It does not
touch `AGENT_LEARNINGS.jsonl` anywhere. `graduate.py` is invoked
immediately after (unless `--stage-only`), which writes to `lessons.jsonl`
and `LESSONS.md` — but by that point the episodic mirror opportunity has
already been skipped, since `stage()`'s `evidence_ids: [now]` promises an
episodic record will exist at that timestamp, and nothing ever creates it.

**The bug is a broken promise, not a missing feature.** `evidence_ids`
exists specifically to let a reader trace a claim back to the observation
that justified it. For the auto-derived path, that trace resolves. For the
manual-stage path, it currently doesn't.

## Sample snippet for the fix

Minimal, matches the module's existing style (see `_lesson_already_appended`
for the established pattern of reading `.agent/memory/*` files from this
module):

```python
def _append_episodic_mirror(cid, claim, ts, source="learn"):
    """Mirror a manual stage into AGENT_LEARNINGS.jsonl so evidence_ids
    referencing `ts` resolve to a real episodic record — matching the
    auto-derived candidate path's existing behavior. Never raises; a
    failure here must not block staging (same fail-open posture as
    _lesson_already_appended's OSError handling).
    """
    episodic_path = os.path.join(BASE, "memory/episodic/AGENT_LEARNINGS.jsonl")
    entry = {
        "timestamp": ts,
        "skill": "learn",
        "action": f"manual-stage:{cid}",
        "result": "success",
        "detail": f"Manually staged lesson {cid} via .agent/tools/learn.py: {claim!r}",
        "pain_score": 1,
        "importance": 6,
        "reflection": "",
        "confidence": 0.9,
        "source": {"skill": "learn", "profile": "manual", "run_id": f"manual_{cid[:6]}"},
        "evidence_ids": [ts],
    }
    try:
        with open(episodic_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # fail-open: staging must succeed even if the mirror write fails
```

Call site — inside `stage()`, right after the candidate file is written:

```python
    path = os.path.join(CANDIDATES, f"{cid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(candidate, f, indent=2)
    _append_episodic_mirror(cid, claim, now, source)   # <-- new line
    return cid, path
```

Notes for whoever implements this:

- `ts` must be the *exact same* `now` value used for `evidence_ids`/
  `staged_at`/`decisions[0].ts` in the candidate — that's the whole point,
  the mirror's `timestamp` is what makes the `evidence_id` resolve.
- Fail-open on write errors (`except OSError: pass`), matching
  `_lesson_already_appended`'s own posture elsewhere in this file — a
  memory-hygiene side effect must never block the primary staging action.
- Add a regression test asserting: after `stage(...)`, grepping
  `AGENT_LEARNINGS.jsonl` for the returned `cid`'s staging timestamp finds
  exactly one matching line, and that its `evidence_ids[0]` equals its own
  `timestamp` (referential integrity, checked mechanically instead of by
  manual review next time).
- Consider whether `--stage-only` runs should also mirror (probably yes —
  the staging event happened regardless of whether graduation follows).

## Meta-decision — why this stayed at the episodic level only

Deliberate, not an oversight. The generalized reflection about tool
behavior (this document, and the shorter episodic entry that preceded it)
was **not** also hand-crafted into `lessons.jsonl` as a `learn.py`-style
graduated lesson. Doing that would mean manually writing a `lessons.jsonl`
row and a graduated candidate JSON by hand, outside the tool — which is
exactly the "manual entry bypassing normal tooling" pattern that produced
the original gap this document diagnoses. Fixing a bug about untrustworthy
manual entries by making another untrustworthy manual entry would be
self-undermining. Once the `stage()` fix above lands, if this meta-lesson
is worth graduating into a standing rule, it should go through `learn.py`
itself — dogfooding the fixed tool, not hand-writing around it again.

## Cross-references

- Original lesson this diagnosis is *about*: `lesson_24032d26aecc`
  (`.agent/memory/semantic/lessons.jsonl`, `.agent/memory/candidates/graduated/24032d26aecc.json`)
- Reconstructed episodic record: `AGENT_LEARNINGS.jsonl`, commit `7a2e098`
- Meta-lesson episodic entry: `AGENT_LEARNINGS.jsonl`, commit `5ca0614`
- CodeRabbit finding: PT PR #246, review `4717711505`
- Original PR this was replayed from: PT PR #242
