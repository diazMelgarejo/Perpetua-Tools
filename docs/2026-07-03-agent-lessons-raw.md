# Agent Lessons Memory

This file captures durable operating lessons for future Perpetua-Tools / orama-system agent work.

## 2026-07-04 — Numbered plan docs require index verification

Before creating any numbered planning document, read the local index first.

For `orama-system/docs/v2/*` specifically:

1. Read `docs/v2/README.md` before choosing a number.
2. Use the README's `Next free slot` as the coordination lock.
3. Create the new document at that slot.
4. Update the README spec tree and advance `Next free slot` in the same pass.
5. If a wrong-numbered file was created, move/preserve its content at the correct slot and delete the wrong file.

Root lesson: do not infer numbering from an uploaded filename or stale conversation context.

## 2026-07-04 — Repo source of truth beats review projections

Margin, PR comments, Cursor handoff docs, and chat summaries are review surfaces. The committed repo artifact is the source of truth.

When publishing a reviewable artifact:

- update the repo file first,
- publish the rendered review copy second,
- fold review comments back into the repo file,
- reuse the same Margin doc when revising,
- never treat Margin comments as approval.

## 2026-07-04 — Skill files must dogfood concise modular architecture

For `SKILL.md` work:

- `SKILL.md` is the orchestrator, not the encyclopedia.
- New generated skills should target <= 200 lines.
- Existing or exceptional skill files must remain <= 500 lines.
- Long templates, examples, anti-patterns, detailed workflows, and eval checklists belong in one-level modular files such as `instructions/`, `examples/`, `references/`, `templates/`, `scripts/`, and `eval/`.
- Always read the repo skill architecture guide before changing skill authoring rules.

## 2026-07-04 — Verify branch and PR state before narration

Do not narrate that a commit, PR, or file is on `main` without verifying the current branch/file state.

Required pattern:

1. Fetch the PR or file from the target branch.
2. Compare the actual changed files against the stated plan.
3. State what is landed, what is only documented, and what is still missing.
4. Do not close, reset, or delete branches until changes are confirmed on `main`.

## 2026-07-04 — AlphaClaw is controlled through Perpetua

Do not edit the AlphaClaw fork directly during cross-repo endpoint, OpenClaw, or v2 planning work.

Represent AlphaClaw only as a downstream controlled surface unless the user explicitly changes ownership instructions.

## 2026-07-04 — Dry-run before long-running or cross-repo execution

For long-running goals, autonomous loops, plugin installs, GPU work, external LLM usage, or cross-repo changes:

- run or produce a dry-run plan first,
- show affected files and commands,
- classify risks and ownership,
- avoid side effects until reviewed.

Dry-run must not call paid/external LLMs, install plugins, touch GPUs, mutate AlphaClaw, or mutate repos beyond a plan/report file.
