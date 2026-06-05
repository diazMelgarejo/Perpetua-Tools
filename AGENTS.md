# Agent instructions — Perpetua-Tools

Follow `CLAUDE.md` for repository architecture, runtime boundaries, and
workflow navigation. This file adds cross-agent guardrails that apply to all AI
coding agents working in this repo.

## History-rewrite & branch re-anchor — MANDATORY before judging any branch

**Applies to every AI agent here — Claude, Codex, Cursor, CodeRabbit, Greptile, and any
future agent.** This repo's `main` has been **rewritten**; pre-rewrite commits keep their
content but get **new SHAs**.

- **NEVER** judge orphan / behind / divergence with `git rev-list --count`, ahead/behind, or
  `git merge-base`. Across a rewrite boundary they are SHA-graph proxies and are **meaningless** —
  a branch can read "N behind" while its tip is byte-identical to a commit already in `main`.
  "N behind + identical content" is a contradiction: **HALT**, it means a rewrite.
- **ALWAYS** use the **tree-twin** test via the in-repo tool:
  ```bash
  scripts/git/reanchor_scan.sh . origin/main heads      # local branches
  git cherry -v origin/main <tip> <base>                # + = missing from main, - = already in
  ```
- Canonical method: orama [git-reanchor SKILL.md § 5](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/git-reanchor/SKILL.md).
  Why it recurs + branch salvage map: [`docs/LESSONS.md` § 2026-06-05](https://github.com/diazMelgarejo/Perpetua-Tools/blob/main/docs/LESSONS.md) ·
  failure catalog [Failure Mode 7](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/afrp/failure-modes.md).
- Reviving/force-updating a remote branch requires **explicit current-user authorization**
  (see § Security PR stacking). Preserve old tips before any force-push.
- Companion: orama [`AGENTS.md`](https://github.com/diazMelgarejo/orama-system/blob/main/AGENTS.md).
  **periscope excluded** (its `main`/`agentsview` are pure upstream mirrors, never rewritten by us).

## Prime directives for agent-maintained records

- Treat vulnerability memory, lessons, audits, and review ledgers as append-only
  historical records. Do not erase, delete, replace, truncate, or rewrite prior
  entries unless the user explicitly instructs that exact destructive action.
- When a record is stale, defunct, remediated, duplicated, or superseded, update
  it additively: add or change status/notes/feedback fields, append a follow-up
  entry, or link to the replacement. Preserve the original evidence and dates.
- For JSON records, load and write with structured parsers (`json.load` /
  `json.dump(..., indent=4)` in Python). Never hand-edit by string
  concatenation, ad hoc patches, or regex substitutions.
- Before any destructive or ambiguity-prone record operation, use
  AskUserQuestions: ask the user which record to change, what status to apply,
  and whether deletion/replacement is truly intended.

## Git attribution

- Use the repo git hooks in `scripts/git/` when available.
- Primary author may be one of the approved owner emails or an approved
  well-known AI author such as `Codex <codex@openai.com>`.
- `Co-authored-by` may include well-known public AI/helper domains and markers
  (`openai.com`, `anthropic.com`, `cursor.com`, `cursor.sh`, `google.com`,
  `github.com`, `microsoft.com`, `azure.com`, subdomains; `codex`, `claude`,
  `anthropic`, `cursor`, etc.).
- Random or unattributable Gmail co-authors are blocked. Only the approved owner
  Gmail addresses may appear in `Co-authored-by`.

## Security PR stacking directive

- Before opening or preparing any security-remediation PR, read the canonical
  security policy in `../orama-system/docs/SECURITY-POLICY.md` and follow its
  "Security PR stacking and merge strategy" section.
- Merge or revive existing security-priority branches before creating duplicate
  replacement branches.
- Stack security PRs in policy-priority order: `PR1` starts from `main`; each
  `PR(N+1)` is rebased on the previous PR branch before opening.
- Rebasing or force-updating an existing remote branch requires explicit current
  user authorization.
