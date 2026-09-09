---
name: git-history-surgery
description: "End-to-end git history surgery for the orama-system stack: scrub contaminated history, force-push safely, and recover/re-anchor branches after a rewrite using byte-identical tree twins. Invoke when: 'expunge git history', 'remove secret…"
---

# git-history-surgery

This is a thin wrapper. The canonical skill lives in the orama-system repo at
the path below. Resolution is read-only and marker-verified — never fetch,
pull, prune, install, register, or modify anything while loading a skill.

- Canonical skill path (repo-relative): `bin/orama-system/skills/git-history-surgery/SKILL.md`

## Before Use

Resolve the canonical repository root, in order, using the first candidate
whose `bin/orama-system/skills/git-history-surgery/SKILL.md` exists as a file. Never hardcode a workstation path — search
instead. Do not guess or fall back to a different repository's copy if none
resolves.

1. `ORAMA_SYSTEM_ROOT` or `ORAMA_SYSTEM_PATH`, if set.
2. `$(git rev-parse --show-toplevel 2>/dev/null)` — correct only when the
   current working directory is already inside the canonical repo itself.
3. A bounded, marker-based search of the current git repo's parent and
   grandparent directories (depth 2) for a sibling checkout containing `bin/orama-system/skills/git-history-surgery/SKILL.md`
   — the same crawl `scripts/git/resolve_sibling_git_repo.sh` performs. If
   the current directory is not inside a git repo, this step has nothing to
   search from and is skipped.

```bash
ROOT=""
for cand in "$ORAMA_SYSTEM_ROOT" "$ORAMA_SYSTEM_PATH" \
    "$(git rev-parse --show-toplevel 2>/dev/null)"; do
  [ -n "$cand" ] && [ -f "$cand/bin/orama-system/skills/git-history-surgery/SKILL.md" ] && ROOT="$cand" && break
done
if [ -z "$ROOT" ] && base="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  parent="$(dirname "$base")"
  for d in "$parent"/*/ "$(dirname "$parent")"/*/; do
    [ -f "${d}bin/orama-system/skills/git-history-surgery/SKILL.md" ] && ROOT="${d%/}" && break
  done
fi
```

If `$ROOT` is still empty, report the canonical skill as unavailable and ask
for its location only if the task genuinely needs it.

## Load Canonical Skill

Read `$ROOT/bin/orama-system/skills/git-history-surgery/SKILL.md` and follow it. Do not copy behavior from this wrapper.

## Refresh (explicit maintenance only — never a side effect of loading)

Synchronizing the canonical repo is a separate, explicitly authorized action.
When asked to refresh it:

```bash
cd "$ROOT/bin/orama-system/skills/git-history-surgery"
git fetch origin --prune
git status --short --branch
```

If the repo is on a tracking branch and the worktree is clean:

```bash
git pull --ff-only
```

If the worktree is dirty, the branch is not tracking origin, or fast-forward is impossible, do not overwrite local work. Report the drift and read the current canonical card with that caveat.

## Windows UTF-8 Note

On Windows PowerShell, set UTF-8 explicitly before reading or writing skill files:

```powershell
[Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8='1'
```
