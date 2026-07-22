---
name: orama-gstack
description: "orama-system's own remediation, conflict-resolution, and fix layer for gstack and gbrain — fork-patch tracking, safe-upgrade workflow, gbrain failure-mode diagnostics, and a routing index into gstack's own skills. Renamed from 'gstack'…"
---

# gstack-gbrain

This is a thin wrapper. The canonical skill lives in this repo at the path below
(resolve the repo root at runtime — paths are never hardcoded).

- Canonical skill path (repo-relative): `bin/orama-system/gstack-gbrain/SKILL.md`

## Before Use

Before relying on the canonical card, check whether the canonical repository can safely sync:

```bash
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT/bin/orama-system/gstack-gbrain"
git fetch origin --prune
git status --short --branch
```

If the repo is on a tracking branch and the worktree is clean:

```bash
git pull --ff-only
```

If the worktree is dirty, the branch is not tracking origin, or fast-forward is impossible, do not overwrite local work. Report the drift and read the current canonical card with that caveat.

## Load Canonical Skill

Open and follow `bin/orama-system/gstack-gbrain/SKILL.md` (relative to the repo root). Do not copy behavior from this wrapper.

## Windows UTF-8 Note

On Windows PowerShell, set UTF-8 explicitly before reading or writing skill files:

```powershell
[Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8='1'
```
