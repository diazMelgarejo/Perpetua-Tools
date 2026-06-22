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

### 2026-04

- Always serialize timestamps in UTC to avoid cross-region comparison bugs  <!-- status=accepted confidence=0.46 evidence=1 id=lesson_422695ae5b2d -->
