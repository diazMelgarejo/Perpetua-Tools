# Platform line endings — turf rule (2026-06-27)

> Promote to `semantic/LESSONS.md` when path-hygiene allows editing that file.
> Canonical skill: orama `git-history-surgery/references/platform-line-endings-turf.md`

## Rule

**Each turf, its own EOL — no tug-of-war.**

| Turf | EOL in worktree | Mac/Linux agents |
|------|-----------------|------------------|
| Windows-serving (`platform/windows/**`, `*.cmd`, `*.bat`, `*.ps1`) | CRLF | Do **not** strip `\r` |
| Mac/Linux-owned (`*.sh`, `*.py`, docs) | LF | Keep LF |

## `gstack-brain-sync.cmd` fix (orama)

- **Correct:** worktree CRLF; git object normalized via `git add` (`i/lf w/crlf` per `.gitattributes`).
- **Wrong:** LF-only content in `.cmd` (breaks cmd.exe); repeated restore/edit cycles on Mac.

## Also updated

- `semantic/DOMAIN_KNOWLEDGE.md` § Windows Development Environment
