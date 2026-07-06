# PR141 Append-Only PR Narrative Lesson

Date: 2026-07-07
Source: orama-system PR 141
Status: working-memory handoff for the PT lesson pipeline

## Context

The PT agent instructions say semantic lessons are rendered by the memory tools, so this note is a handoff for a host agent to graduate with `.agent/tools/learn.py` instead of editing the rendered semantic lesson file directly.

## Lesson candidates

1. PR descriptions are historical review artifacts. Preserve the original PR purpose, summary, non-goals, and validation instructions at the top.

2. Later commits and review responses should be added under an append-only update log. Do not replace the original PR corpus with the latest delta.

3. Review-bot summaries may stay useful as an appendix, but they should not become the only description of the PR.

4. Additive and integrative updates apply to PR bodies, lessons, docs, and review notes. Preserve useful older context unless the user explicitly asks to remove it.

5. When a repo marks a memory file as rendered, use the repo memory toolchain to graduate lessons. If the toolchain cannot be executed in the current environment, stage a working-memory handoff.

6. Git attribution policy changes must update all owned surfaces together: attribution audit, identity check, commit-message check, verification check, and docs.

7. Hygiene-rule tests should build sensitive fixture strings at runtime, while still asserting that the validator detects them.

## Suggested graduation command

```bash
python3 .agent/tools/learn.py "PR bodies are append-only review artifacts: preserve the original purpose and scope at the top, and add later repair notes only below as a chronological update log." --rationale "In orama-system PR 141, replacing the PR body with the latest repair summary erased useful original context. Restoring the original corpus and appending later updates preserved review continuity."
```

## Related anchors

- orama-system PR 141
- orama-system docs/LESSONS.md section: 2026-07-07 — PR descriptions are append-only review artifacts
- PT .agent/AGENTS.md memory rules
