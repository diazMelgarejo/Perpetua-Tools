---
name: hermes-harness
description: "Onboards Hermes Agent as a cross-harness operator shell for PT-orama and ECC workflows. Use when installing Hermes, importing ECC/orama skills into Hermes, configuring Nous Portal or LM Studio providers, adding Hermes beside OpenClaw, or…"
---

# hermes-harness

This is a thin wrapper. The canonical skill lives in this repo at the path below
(resolve the repo root at runtime — paths are never hardcoded).

- Canonical skill path (repo-relative): `bin/orama-system/skills/hermes-harness/SKILL.md`

## Before Use

Before relying on the canonical card, check whether the canonical repository can safely sync:

```bash
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT/bin/orama-system/skills/hermes-harness"
git fetch origin --prune
git status --short --branch
```

If the repo is on a tracking branch and the worktree is clean:

```bash
git pull --ff-only
```

If the worktree is dirty, the branch is not tracking origin, or fast-forward is impossible, do not overwrite local work. Report the drift and read the current canonical card with that caveat.

## Load Canonical Skill

Open and follow `bin/orama-system/skills/hermes-harness/SKILL.md` (relative to the repo root). Do not copy behavior from this wrapper.

**Hardware policy:** Hermes on Windows consumes Perpetua-Tools `config/model_hardware_policy.yml`
via the same CLI as OpenClaw — see orama `commands/pt-hardware-policy/SKILL.md` and PT
`.claude/skills/hardware-policy/SKILL.md`. Never infer NEVER_MAC/NEVER_WIN at runtime.

## Windows UTF-8 Note

On Windows PowerShell, set UTF-8 explicitly before reading or writing skill files:

```powershell
[Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8='1'
```
