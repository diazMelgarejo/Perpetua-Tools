# Domain Knowledge

> Stable facts about the domains you work in. Not procedures (those go in
> skills), not preferences (those go in `personal/PREFERENCES.md`), not
> time-bound events (those go in `episodic/`). Pure reference material.

## Example sections
- API contracts you reuse
- Vendor quirks ("service X rate-limits at 60 rpm, not the documented 100")
- Domain-specific terminology

## Windows Development Environment (verified 2026-06-26)

Canonical bootstrap (PowerShell, run before git push/rebase/pytest on the RTX host):
`bin/orama-system/skills/git-history-surgery/references/windows-powershell-runtime-bootstrap.md` (in `diazMelgarejo/orama-system`)

### Stable shim directory — `%USERPROFILE%\.lmstudio\bin`
- User-owned, survives LM Studio / GitHub Desktop version bumps. Holds lightweight
  `git.cmd`, `node.cmd`, `npm.cmd` wrappers — not full tool installs.
- Node runtime: `%USERPROFILE%\.lmstudio\.internal\utils\node.exe` (LM Studio bundle).
- npm global prefix: `%USERPROFILE%\.lmstudio` so `npm install -g` CLIs land in the shim bin.
- npm-generated `.ps1` launchers expect `node.exe` beside them; a hardlink from
  `%USERPROFILE%\.lmstudio\bin\node.exe` → the bundled node keeps globals working without elevation.
- **Never** symlink dev tools into versioned app install folders (e.g. `GitHubDesktop\app-*`).

### Git shim — dynamic GitHub Desktop discovery
- `%USERPROFILE%\.lmstudio\bin\git.cmd` should find the **latest** GitHub Desktop bundle:
  `%LOCALAPPDATA%\GitHubDesktop\app-*\resources\app\git` (sort by `LastWriteTime`, take newest).
  Do **not** hardcode `app-3.5.9-beta3` or any pinned version path.
- Before invoking `cmd\git.exe`, prepend **both** helper dirs and set exec path:
  - `PATH` += `…\mingw64\bin;…\cmd` (order matters)
  - `GIT_EXEC_PATH` = `…\mingw64\bin` (contains `git-remote-https.exe`)
- Symptom when misconfigured: `git: 'remote-https' is not a git command` even though
  `git --exec-path` looks correct — the child process lacks `mingw64\bin` on PATH.
- PowerShell gotchas: quote `git rev-parse --abbrev-ref '@{u}'` (bare `@{u}` is a hashtable);
  avoid `&&` in older PowerShell; separate commands or use native control flow.
- Explicit Python for scripts/tests: `%PERPETUA_TOOLS_ROOT%\.venv\Scripts\python.exe`
  (plain `python` may resolve to the Windows Store alias).

```powershell
$lmBin = "$env:USERPROFILE\.lmstudio\bin"
$gitRoot = Get-ChildItem "$env:LOCALAPPDATA\GitHubDesktop" -Directory -Filter "app-*" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1 |
  ForEach-Object { Join-Path $_.FullName "resources\app\git" }
$env:PATH = "$lmBin;$gitRoot\mingw64\bin;$gitRoot\cmd;$env:PATH"
$env:GIT_EXEC_PATH = "$gitRoot\mingw64\bin"
```

### bash.exe — present on some hosts, absent from cmd.exe PATH
- Git Bash sessions see `bash.exe`; **cmd.exe** and Node/bun spawns with `shell: true` do not.
- GitHub Desktop's bundle often ships `usr\bin\sh.exe` but **no** literal `bash.exe`.
  Do not assume full Git for Windows is installed.
- `HERMES_GIT_BASH_PATH` must point at a real `bash.exe` (Hermes harness, explicit bash
  wrappers). Discover under GitHub Desktop or install Git for Windows / WSL2 git bash.
- Test-only shim when pytest/shell tests need literal `bash` (keep outside the repo):

```powershell
$tmpBashDir = Join-Path $env:TEMP "codex-bash-shim"
New-Item -ItemType Directory -Force -Path $tmpBashDir | Out-Null
Copy-Item -Force "$gitRoot\usr\bin\sh.exe" (Join-Path $tmpBashDir "bash.exe")
$env:PATH = "$tmpBashDir;$gitRoot\usr\bin;$env:PATH"
```

- Claude Code's Bash tool uses its own `/usr/bin/bash` — env vars do not cross into PowerShell
  and vice versa. Export per session when needed.

### gbrain + gstack shims (gstack issue #1731)
- `gbrain` installed via npm/bun is a **`gbrain.cmd` / `gbrain.ps1` shim** on Windows.
  Direct `spawn("gbrain", …)` without `shell: true` → ENOENT ("brain-sync exited undefined").
- gstack centralizes this: `NEEDS_SHELL_ON_WINDOWS = process.platform === "win32"` in
  `lib/gbrain-exec.ts`; every `spawnGbrain` / `spawnGbrainAsync` / brain-sync spawn sets
  `shell: NEEDS_SHELL_ON_WINDOWS`. Static tripwire: `test/gbrain-spawn-windows-shell.test.ts`.
- `gstack-brain-sync` is a **bash shebang** at `~/.claude/skills/gstack/bin/gstack-brain-sync`.
  cmd.exe cannot exec shebangs — add a sibling **`gstack-brain-sync.cmd`** that invokes
  bash explicitly, e.g. `"%HERMES_GIT_BASH_PATH%" "%~dp0gstack-brain-sync" %*` (or resolve
  bash from the same `$gitRoot` discovery above). Any bash script in that `bin/` tree that
  bun/Node must call on Windows needs the same `.cmd` shim pattern.
- `.cmd`/`.bat` files require **CRLF** line endings (`*.cmd text eol=crlf` in `.gitattributes`);
  LF-only batch files fail silently under cmd.exe.

### LLAMA_SERVER_BASE_URL — already in PowerShell profile, never missing
- `%USERPROFILE%\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1` line 1:
  `$env:LLAMA_SERVER_BASE_URL = "http://localhost:1234/v1"` — verified present.
- Do NOT add it again. Not absent from PowerShell; just doesn't propagate to Bash tool.
- Export explicitly in bash sessions: `export LLAMA_SERVER_BASE_URL="http://localhost:1234/v1"`

### git -C flag required for orama-system in bash sessions
- The bash tool's cwd may differ from the `ultrathink-system` git root.
- Always use: `git -C "$ORAMA_SYSTEM_PATH" <subcommand>` for reliable results.

### Windows toolchain verification
After bootstrap or shim changes, run in PowerShell:
`git --version`; `node --version`; `npm --version`;
`& $env:HERMES_GIT_BASH_PATH --noprofile --norc -lc 'echo hermes-bash-ok'` (when Hermes/bash wrappers matter);
`~/.claude/skills/gstack/bin/gstack-brain-sync --status` (or `.cmd` variant on Windows).

## Seeds
_(empty — populate as you go)_

## .agent/ system — origin and provenance

**First commit:** `82bcbfae` — 2026-06-19 00:22 +0800, author: cyre <Lawrence@cyre.me>  
**Commit message:** `docs: establish GEMINI.md mandate and agentic-stack context`  
**Repository:** Perpetua-Tools (`diazMelgarejo/Perpetua-Tools`)  
**Added directly to `main`** (not via a PR)

**install.json at first commit:**
- `agentic_stack_version`: `0.9.0`
- `installed_at`: `2026-06-18T13:11:50Z` (the day before the commit)
- `abs_target`: `%USERPROFILE%\...\Perplexity-Tools` (historical install.json snapshot — never commit live paths)

**What it added in one shot (55 files):** complete memory system (episodic/semantic/working), all Python tools (graduate.py, learn.py, recall.py, show.py, etc.), harness layer (conductor.py, hooks/, protocols/), 6 initial skills. No other repo cited as origin.

**Design intent (from AGENTS.md first line):**  
> "This folder is the portable brain. Any harness (Claude Code, Cursor, Windsurf, OpenCode, OpenClaw, Hermes, standalone Python) can mount it and get the same memory, skills, and protocols."

**Origin:** Built from scratch as a purpose-designed portable agent memory system. The version `0.9.0` suggests prior offline/local development before the first tracked commit. The design philosophy connects to ECC cross-harness thinking but the code is not derived from any prior tracked repo.
