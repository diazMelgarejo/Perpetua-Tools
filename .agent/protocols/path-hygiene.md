# Path hygiene — anti-doxxing (tracked files)

**Invariant:** Never write workstation-specific paths into any **git-tracked** file.

This applies to docs, plans, skills, `.agent/memory/*`, commit messages, PR bodies,
and AI-generated artifacts (including `learn.py` claims and autoplan restore comments).

## Forbidden (LINT-006 / repo_hygiene)

| Pattern | Why |
|---------|-----|
| `OS-specific home-directory paths` / `OS-specific home-directory path form` / `OS-specific home-directory path` | Exposes username + machine layout |
| `%USERPROFILE%\<segment>\...` (Downloads tree) | Still doxxes directory layout |
| `$HOME/<segment>/SKILLS.md/...` | Same — env var does not sanitize structure |
| `<user>` placeholders in paths | Leaks typical layout |
| Canonical "use my Downloads path" lessons | **Antipattern** — never pin workspace roots in memory |

## Allowed substitutes

| Use | Example |
|-----|---------|
| Repo-relative | `../../Perpetua-Tools/.agent/memory` |
| Repo anchor env | `$REPO_ROOT`, `$OPENCLAW_ROOT`, `PERPETUA_TOOLS_ROOT` |
| Generic home tilde | `~/.gstack/projects/<slug>/` (no username segment) |
| Repo name only | `orama-system`, `Perpetua-Tools` |
| CI placeholders | `scripts/review/repo_hygiene.py` examples use `<workspace>` |

## Write boundaries (must sanitize)

All writers call `sanitize_tracked_path_leaks()` from `.agent/memory/path_hygiene.py`:

- `learn.py`, `graduate.py`, episodic loggers
- Review queue renderer (`review_state.py`)
- Dream / Hermes outputs before commit

After `lessons.jsonl` edits: **re-render** `LESSONS.md` via `render_lessons.py` — never hand-merge.

## Pre-commit / CI

- **orama-system:** `python scripts/review/repo_hygiene.py .` (Git hygiene job)
- **Perpetua-Tools:** same LINT-006 alignment + path_hygiene at source

## Policy docs that *explain* forbidden patterns

Use notation like `OS-specific home-directory paths` or `OS-specific home-directory path` only — never your real path.
See `lesson_8c6e3368a308`.

## Related lessons

`lesson_da04cbbae68b`, `lesson_456ea361526d`, `lesson_3e554559c7ed`, `lesson_6fc89e22e3bb`
