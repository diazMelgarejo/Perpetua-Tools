# Python venv resolution and the default-environment pattern (2026-11-17) — Exhibit B

Verified on the Mac peer (macOS, Apple silicon) with uv 0.13.8 and uv-managed CPython 3.13.18,
which embeds SQLite 3.53.1 with source id `2026-05-05 … c88b2201`. Author/actor: Claude Code,
self-reported. The operator designated this solution **Exhibit B for elegance**, beside
Exhibit A, orama-system PR #516's fragment synthesis. Facts are labeled verified, from a run on
this host, or reference, from a cited specification.

## 1. How CPython decides it is running in a venv

- **Reference, PEP 405.** At startup CPython looks for `pyvenv.cfg` adjacent to the executable
  or one directory above it. If the executable is a symlink, it is not dereferenced for this
  lookup. When the file is found, `sys.prefix` becomes the venv directory and `sys.base_prefix`
  becomes the installation named by the `home` key.
- **Verified.** A venv's `bin/python3` is itself a relative symlink (`python3 -> python`) to the
  base interpreter. It works because it is invoked *from* `<env>/bin`, where `../pyvenv.cfg`
  exists.
- **Verified.** A second symlink placed elsewhere, for example `~/.local/bin/python3` pointing at
  `<env>/bin/python3`, does **not** activate the env. The lookup is anchored at the invoked path
  (`~/.local/bin`, then `~/.local`), which has no `pyvenv.cfg`. The process runs as the base
  interpreter with none of the env's packages.
- **Verified.** With `include-system-site-packages = false` (the default), `site.ENABLE_USER_SITE`
  is False inside the venv, so user-site packages are invisible too.

## 2. Failure modes met on 2026-11-16/17

| # | Symptom | Cause, verified | Durable rule |
| --- | --- | --- | --- |
| 1 | After making uv 3.13.18 the default `python3`, `python3 scripts/agent_coordination.py` failed with `No module named 'aiosqlite'`. The board CLI was broken for every agent on the Mac. | The old default (framework CPython 3.13.0) carried 229 packages, some in its user site. A new interpreter starts empty. | Changing the default interpreter is a dependency migration. Freeze the old set and carry it over before or with the switch. |
| 2 | Ten venvs had `bin/python` dangling at `cpython-3.13.7-…` or `cpython-3.12.11-…` | `pyvenv.cfg` `home` pointed at a **patch-specific** uv directory, and uv later removed that patch | Anchor `home` on the uv **minor-version link** directory (section 3). |
| 3 | `uv venv --python 3.13.18 <env>` wrote `home = …/cpython-3.13.18-macos-aarch64-none/bin` | uv resolves a version request to the patch directory | Pass the link path itself: `uv venv --python ~/.local/share/uv/python/cpython-3.13-macos-aarch64-none/bin/python3.13 <env>`. Both this and `<link> -m venv` write `home = …/cpython-3.13-…/bin`. |
| 4 | Framework and uv builds disagree on user-site packages | Framework uses `~/Library/Python/3.13/lib/python/site-packages`; the uv standalone build uses `~/.local/lib/python3.13/site-packages` | Never rely on user site across interpreters; put the packages in an explicit env. |
| 5 | `netifaces==0.11.0` failed to build (C compile error, no cp313 wheel) | The project is unmaintained; the old install predates the toolchain | Use the drop-in `netifaces-plus==0.12.5` (same `import netifaces`, ships wheels). Callers: orama `scripts/discover.py`, `scripts/ip_detection_solution.py`; PT `packages/net_utils/network_autoconfig.py`. |
| 6 | A link to a venv interpreter from `~/.local/bin` imported nothing from the env | Section 1: symlinks are not dereferenced for the `pyvenv.cfg` lookup | Enter an env through an `exec` wrapper, never a link from another directory. |
| 7 | `uv python install --default` (experimental in uv 0.13.8) writes `python` and `python3` links into `~/.local/bin` | uv owns those names | Re-running it overwrites the wrappers. Re-check after any uv default change. |

## 3. The pattern (Exhibit B)

```text
PATH: ~/.local/bin  (before the framework bin)
  python3, python   = #!/bin/sh  exec "$HOME/.local/share/python-default-3.13/bin/python3" "$@"
                         |
~/.local/share/python-default-3.13/        (venv; packages from one rebuild file)
  pyvenv.cfg  home = ~/.local/share/uv/python/cpython-3.13-macos-aarch64-none/bin   <- minor-version link
  bin/python3 -> python -> base interpreter
                         |
~/.local/share/uv/python/cpython-3.13-macos-aarch64-none -> cpython-3.13.18-macos-aarch64-none
  (uv repoints the link on a 3.13.x patch upgrade; the env keeps resolving)

Untouched: framework CPython 3.13.0 (SQLite 3.45.3, below the 3.51.3 floor), still installed.
```

- **One rebuild file.** `~/.config/python-default/requirements.txt` holds 227 lines. It comes from
  `pip freeze --all` of the old default (kept as `framework-3.13.0-freeze.txt`). Two editable
  installs that pointed at deleted `/private/tmp` checkouts are dropped, and `netifaces` is
  swapped for `netifaces-plus`.
- **`exec`, not a child process.** The wrapper replaces the shell, so the PID, signals, exit code,
  stdin and stdout are the interpreter's own. `sys.executable` is the env path, so
  `pyvenv.cfg` is found.
- **Atomic repoint.** Write `.python3.tmp`, `chmod 755`, then `mv -f` onto the name. `rename(2)` is
  atomic on one filesystem, so a concurrent caller sees the old or the new wrapper, never a
  partial file.
- **Replace, then remove.** Build the new env beside the old one under a new name. Verify the
  version, the SQLite floor, the critical imports and the board CLI. Repoint the wrappers. Delete
  the old env only after a fresh login shell resolves the new one.
- **Rollback.** Delete the two wrappers and the framework 3.13.0 is the default again.
- **Upgrade.** A 3.13.x patch upgrade needs nothing; uv repoints the minor-version link. A minor
  upgrade (3.14) means building `python-default-3.14` from the same rebuild file and repointing.

## 4. Verification

```bash
zsh -lic 'command -v python3'          # ~/.local/bin/python3 (open a new shell or run rehash)
python3 -c 'import sys,sqlite3; print(sys.version.split()[0], sqlite3.sqlite_version,
  sys.prefix != sys.base_prefix)'      # 3.13.18 3.53.1 True
grep '^home' ~/.local/share/python-default-3.13/pyvenv.cfg   # .../cpython-3.13-macos-aarch64-none/bin
python3 scripts/agent_coordination.py --help                 # board CLI imports aiosqlite
```

Detect venvs with a dangling interpreter (read-only):

```bash
for c in $(find ROOT -maxdepth 4 -name pyvenv.cfg); do
  d=$(dirname "$c"); "$d/bin/python" -c pass 2>/dev/null || echo "BROKEN $d"
done
```

Replace each one by building and verifying the new env, then deleting the stale one. Never
delete first.

## 5. Why it is an exhibit of elegance

- **Fixes the resolution layer, not the callers.** Every `python3 …` instruction, used by many
  agents and hosts, keeps working unchanged.
- **Immutable bases.** Neither the framework interpreter nor the uv-managed base gains packages.
- **Reproducible and reversible.** One rebuild file; delete two small files to undo.
- **Survives the next upgrade.** Anchoring `home` on the minor-version link removes the cause of
  the ten stale venvs.
- **Found by review, fixed replacement-first.** A side agent flagged the package loss. The board
  break was confirmed, then the replacement was built and verified before anything was removed.

Open items: replacing the four main-repo `.venv` directories (PT, orama-system, oramasys,
phylax) and deleting six broken worktree venvs are operator-run scripts. The autoresearch
`scout-block` hook blocks agent commands that name `.venv/`. Windows parity was not addressed.
