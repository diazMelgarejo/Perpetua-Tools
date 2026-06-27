---
name: oramasys-method
description: "Successor and drop-in replacement for the legacy ultrathink-system method. Applies the orama-system 5-stage methodology (Context Immersion → Visionary Architecture → Ruthless Refinement → Masterful Execution → Crystallize) with the AFRP…"
---

# oramasys-method

This is a thin wrapper. The canonical skill lives in the **orama-system** repo
(resolve paths at runtime — never hardcode workstation paths).

- Canonical skill (orama-system): `bin/orama-system/skills/oramasys-method/SKILL.md`
- **PR merge / conflicts:** `bin/orama-system/skills/oramasys-method/references/integrative-merge.md`

## Before Use

Sync the canonical card from orama-system when a sibling checkout exists:

```bash
ORAMA="${ORAMA_SYSTEM_ROOT:-${OPENCLAW_HOME:-$HOME}/orama-system}"
if [ -d "$ORAMA/bin/orama-system/skills/oramasys-method" ]; then
  cd "$ORAMA/bin/orama-system/skills/oramasys-method"
  git fetch origin --prune && git status --short --branch
  # git pull --ff-only   # only when clean + tracking
fi
```

If the worktree is dirty, the branch is not tracking origin, or fast-forward is impossible, do not overwrite local work. Report the drift and read the current canonical card with that caveat.

## Load Canonical Skill

Open and follow the canonical card in **orama-system**:

- [`orama-system/.../oramasys-method/SKILL.md`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/oramasys-method/SKILL.md)
- [`references/integrative-merge.md`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/oramasys-method/references/integrative-merge.md) — **mandatory for PR merges** (synthesize, never amputate)

If `../orama-system` exists locally, prefer
`../orama-system/bin/orama-system/skills/oramasys-method/SKILL.md`. Do not copy behavior from this wrapper.

## Windows UTF-8 Note

On Windows PowerShell, set UTF-8 explicitly before reading or writing skill files:

```powershell
[Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8='1'
```
