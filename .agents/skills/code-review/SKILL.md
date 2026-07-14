---
name: code-review
description: "Use when reviewing code across multiple files, PRs, or unfamiliar areas; before refactors; when the user asks for blast-radius, detect_changes_tool, get_review_context_tool, semantic_search_nodes_tool, code-reviewer subagents, or…"
---

# code-review

This is a thin wrapper. The canonical skill lives in this repo at the path below
(resolve the repo root at runtime — paths are never hardcoded).

- Canonical skill path (repo-relative): `bin/orama-system/skills/code-review/SKILL.md`

## Before Use

Before relying on the canonical card, check whether the canonical repository can safely sync:

```bash
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT/bin/orama-system/skills/code-review"
git fetch origin --prune
git status --short --branch
```

If the repo is on a tracking branch and the worktree is clean:

```bash
git pull --ff-only
```

If the worktree is dirty, the branch is not tracking origin, or fast-forward is impossible, do not overwrite local work. Report the drift and read the current canonical card with that caveat.

## Load Canonical Skill

Open and follow `bin/orama-system/skills/code-review/SKILL.md` (relative to the repo root). Do not copy behavior from this wrapper.

## Review provenance and remediation

For PR reviews, CI findings, and bot comments, also load:

- [Branch-Local Review Remediation](../../../.agent/references/branch-local-review-remediation.md)

Bind each finding to the exact reviewed branch and head. Cluster findings by shared invariant, fix the owning abstraction, add focused regression tests, and do not place review-only fixes on `main` before merge.

## Perpetua-Tools: hardware affinity reviews

When the diff touches model IDs, routing, `openclaw.json`, `launch_researchers.py`,
or `hardware_policy.py`, also load **`.claude/skills/hardware-policy/SKILL.md`** and verify:

1. No duplicate YAML parsers (`rg '_simple_policy_parse|def _forbidden'`)
2. Alias ids covered in `model_hardware_policy.yml`
3. `pytest tests/test_launch_researchers_affinity.py tests/test_hardware_routing.py -q`

## Related skills

- [`../agent-methodology/SKILL.md`](../agent-methodology/SKILL.md) — Apply the Oramasys context, synthesis, TDD, and verification stages.
- [`../git-history-surgery/SKILL.md`](../git-history-surgery/SKILL.md) — Preserve review lineage when the branch needs rebase or recovery.

## Windows UTF-8 Note

On Windows PowerShell, set UTF-8 explicitly before reading or writing skill files:

```powershell
[Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8='1'
```
