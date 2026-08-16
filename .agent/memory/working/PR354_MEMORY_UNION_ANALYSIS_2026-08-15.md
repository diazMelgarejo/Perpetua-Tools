# PR #354 Memory Union Forensic Analysis & Reconciliation Report

**Date:** 2026-08-15  
**Scope:** Perpetua-Tools PR #354 (`repair/memory-lossless-20260815`)  
**Methodology:** OramaSys / AFRP Type B (Expert) / CIDF (Synthesize & Preserve)  
**Cross-References:** GitHub PR #354 discussion (`discussion_r3788626078`) & review (`pullrequestreview-4942979012`)

---

## 1. Executive Summary

This investigation analyzes two memory-integrity phenomena observed during the multi-ref union repair on Perpetua-Tools PR #354:
1. **The 4 quarantined lines in `.agent/memory/working/MEMORY_UNION_INVALID_ROWS_2026-08-15.txt`**: Identified as raw CLI tool-runner stdout/stderr truncation banners ingested into the stream during broad text scraping, correctly isolated by the validation gate.
2. **Line 1366 in `.agent/memory/episodic/AGENT_LEARNINGS.jsonl`**: Identified as an episodic `proactive-recall` record whose outer JSON envelope is valid, but whose inner nested `detail` JSON string was truncated at exactly 500 characters by `post_execution.py`'s length cap.

All temporary worktree paths referenced in this analysis have been sanitized to `$TMP/disposable-worktrees/*` per repository path-hygiene protocols.

---

## 2. Forensic Analysis of `MEMORY_UNION_INVALID_ROWS_2026-08-15.txt`

### The 4 Rows Verbatim

```text
Row 1: Warning: truncated output (original token count: 314706)
Row 2: ... 210245 bytes omitted ...
Row 3: Warning: truncated output (original token count: 291705)
Row 4: ... 118244 bytes omitted ...
```

### Why They Appeared
- During multi-branch memory aggregation, CLI tools (such as subshell commands or test output loggers) executed commands with very large outputs.
- The execution harness emitted pagination/truncation warning banners directly to stdout.
- When union scripts scraped raw stdout/file lines without strict pre-JSON validation, these non-JSON lines were picked up.
- **Resolution in PR #354:** The union repair script validated each candidate row with `json.loads()` and cleanly segregated non-JSON lines into `MEMORY_UNION_INVALID_ROWS_2026-08-15.txt` rather than corrupting `AGENT_LEARNINGS.jsonl` or discarding them uninspected.

---

## 3. Analysis of Line 1366 in `AGENT_LEARNINGS.jsonl`

### Record Structure

```json
{
  "timestamp": "2026-08-15T05:28:04.135211+00:00",
  "skill": "proactive-recall",
  "action": "recall:PT 354 memory union review remediation security attribution conflict audit",
  "result": "success",
  "detail": "{\"returned\": [\"All .agent/memory writers must call sanitize_tracked_path_leaks() from path_hygi\", \"When Mac and Win both push Perpetua-Tools .agent/memory in the same coord round,\", \"Before git pull --rebase when Perpetua-Tools main is behind origin, stash local \", \"Hardcoded API keys in tracked files are a SECURITY.md violation. The BigModel GL\", \"Generated memory output such as LESSONS.md and lessons.jsonl must only be modifi\", \"When harmonizing two divergent branches, use the integrative merg",
  "pain_score": 2,
  "importance": 6,
  "reflection": "",
  "confidence": 0.5,
  "source": {
    "skill": "proactive-recall",
    "profile": "default",
    "run_id": "pid-4",
    "commit_sha": "e9a543a2749246ee08ac2da65774360cc4423f35"
  },
  "evidence_ids": []
}
```

### Root Cause: Producer-Side Length Budget
1. **Recall Hook (`.agent/tools/recall.py`):**
   - When a recall query executes, it formats matched lesson claims into a dictionary:
     ```python
     detail = {
         "returned": [r["claim"][:80] for r in result],
         "considered": meta["considered"],
         "source_counts": meta.get("source_counts", {}),
         "only_md_available": meta.get("only_md_available", False),
     }
     reflect("proactive-recall", f"recall:{intent[:80]}", json.dumps(detail, ensure_ascii=False), ...)
     ```
2. **Episodic Hook Truncation (`.agent/harness/hooks/post_execution.py`):**
   - The logging function applies a static length ceiling:
     ```python
     "detail": sanitize_tracked_path_leaks(str(result)[:500])
     ```
3. **The Conflict:**
   - Slicing a serialized JSON string at 500 characters abruptly severs the string in the middle of the 6th claim item (`"When harmonizing two divergent branches, use the integrative merg`).
   - The outer `post_execution.py` wraps this truncated string into a new JSON object (`json.dumps(entry)`), escaping it. The outer line parses as valid JSONL, but the inner `detail` string cannot be parsed as standalone JSON without recovery.

---

## 4. Multi-Agent Concurrency & Active Worktree Topology

At the time of these operations, multiple agent sessions were operating concurrently across isolated worktrees:

| Sanitized Worktree Path | Branch / Target | Operational Role |
|---|---|---|
| `$TMP/disposable-worktrees/pt-memory-repair-20260815` | `repair/memory-lossless-20260815` | Lossless memory reconstruction & PR #354 |
| `$TMP/disposable-worktrees/orama-gemini-bugfixes-20260814` | `2026-08-14-005-gemini-bugfixes` | Gemini skill reconciliation & thin wrapper verification |
| `$TMP/disposable-worktrees/pt-task5-coordination-memory-20260815` | `docs/task5-coordination-memory-20260815` | Task 5 audit & coordination memory |
| `$TMP/disposable-worktrees/pt-endpoint-policy-pr352-review-20260814` | `2026-08-12-endpoint-policy-standardization` | Endpoint policy review & CI checks |
| `$TMP/disposable-worktrees/orama-antigravity-atomic-hardening-20260815` | `antigravity-atomic-tmp-hardening-20260815` | Atomic receipt `mkstemp`/`fsync` hardening |
| `$REPO_ROOT` (Perpetua-Tools) | `main` | Primary shared repository root |

### Concurrency Mechanics
- **Process Isolation:** `_episodic_io.py` utilizes `fcntl.flock` sidecar locks (`.lock`) to ensure line-level atomic writes across processes and prevent byte interleaving during concurrent appends.
- **Finding:** The truncation was **not** caused by race conditions or lock failures, but by the fixed 500-character budget in `post_execution.py`.

---

## 5. Architectural Recommendations

1. **Structured Detail Logging in `post_execution.py`:**
   - If `result` is a dictionary or already valid JSON, parse/preserve the structured hierarchy or enforce bounded array slicing before serialization, rather than substring-slicing serialized JSON text.
2. **Quarantine Invariant:**
   - Maintain non-JSON tool output segregation in forensic sidecars (`MEMORY_UNION_INVALID_ROWS_*.txt`) whenever replaying or aggregating historic logs.
