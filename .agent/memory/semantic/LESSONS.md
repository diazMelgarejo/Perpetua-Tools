# Lessons (auto-distilled + manually curated)

> Entries here outlive specific tasks. The dream cycle promotes recurring
> patterns from episodic into this file. Feel free to curate manually —
> delete bad lessons, tighten wording, reorganize sections.

## Seed lessons
- Always read `protocols/permissions.md` before any destructive tool call.
- Write the failing test before writing the fix.
- Log to episodic memory on every significant action, success or failure.
- When a skill has failed 3+ times in 14 days, propose a rewrite.
- Never force push to protected branches under any circumstance.

## Auto-promoted entries will be appended below

### 2026-06

- DO NOT assume directory or structure names: when the user gives an explicit name (e.g. '.agent/memory'), use it verbatim — never silently 'correct' it to a guess (e.g. '.agents/memory'). If it seems wrong or you have not read its conventions, STOP and ASK first. Read the area's AGENTS.md/_index before writing.  <!-- status=accepted confidence=0.6 evidence=1 id=lesson_2e154f1b55ab -->
- Do small, directly-related follow-up tasks in the same session, never defer them as a vague 'follow-up'. Procrastination leads to forgetting and stale/overdue debt.  <!-- status=accepted confidence=0.6 evidence=1 id=lesson_d892d844cf60 -->
- Before acting on a repo, verify you are not on a stale branch: fetch and compare the local HEAD tree to origin (tree-twin, not ahead/behind counts), and adopt upstream structural migrations before writing.  <!-- status=accepted confidence=0.6 evidence=1 id=lesson_0afc8c5f2778 -->
- Do the user's stated #1 task first; do not let setup/cleanup tangents replace it. If you must pivot, name the original task explicitly and return to it — never silently drop it.  <!-- status=accepted confidence=0.6 evidence=1 id=lesson_a7374ba4b00d -->
- gbrain per-source sync ('gbrain sync --source <id>') must run from INSIDE that source's own git repo (its local_path). A bare 'gbrain sync' from a non-git cwd fails: 'Not a git repository: GBrain sync requires a git-initialized repo'. Look up the path via 'gbrain sources list --json' (.local_path) and cd there first.  <!-- status=accepted confidence=0.6 evidence=1 id=lesson_36f924c161e1 -->
- Complete gbrain source archival/removal in the SAME pass you decide it — never leave 'pending removal'. Old-path duplicate sources (from repo moves) left un-archived resurface as sync_freshness/multi_source_drift warnings every session. Prefer 'gbrain sources archive' (reversible) + export the def to ~/repo-backups first; the orama guard scripts/gbrain/gbrain-selfheal.sh acks failures, refreshes live sources, and reports orphans automatically. Autopilot is launchd KeepAlive: stop with 'launchctl unload -w', a kill won't stick.  <!-- status=accepted confidence=0.6 evidence=1 id=lesson_d0d49b68ab24 -->

### 2026-04

- Always serialize timestamps in UTC to avoid cross-region comparison bugs  <!-- status=accepted confidence=0.46 evidence=1 id=lesson_422695ae5b2d -->
