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
[`bin/orama-system/skills/git-history-surgery/references/windows-powershell-runtime-bootstrap.md`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/git-history-surgery/references/windows-powershell-runtime-bootstrap.md)

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
  `%PERPETUA_TOOLS_ROOT%` must be set before use — define it in one of:
  - **System environment variables** (Control Panel → System → Advanced)
  - **PowerShell profile** (`$PROFILE`): `$env:PERPETUA_TOOLS_ROOT = "C:\path\to\Perpetua-Tools"`
  - **Harness bootstrap** (`start.ps1`): the Hermes/Codex bootstrap exports it automatically
    when launching from the repo root.

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
- `.cmd`/`.bat`/`.ps1` on **Windows turf** require **CRLF** in the working tree (`eol=crlf` in orama `.gitattributes`). LF-only batch files fail silently under `cmd.exe`.
- **Each turf, its own EOL — no tug-of-war:** macOS/Linux agents must **not** strip `\r` from Windows-serving files (`orama-system/platform/windows/**`, `*.cmd`, `*.bat`, `*.ps1`). Mac/Linux-owned sources (`*.sh`, `*.py`, docs) stay **LF**. Canonical policy: orama `git-history-surgery/references/platform-line-endings-turf.md`.
- **False dirty on Mac:** `git status` shows `platform/windows/*.cmd` modified but content unchanged — often a pre-attributes blob. Fix once with `git add <file>` (normalizes object to `i/lf w/crlf`), not hand-edited EOL conversion.

### PowerShell 5.1 encoding — UTF-8 BOM required for non-ASCII in `.ps1` files (verified 2026-06-28)

**Root cause:** PowerShell 5.1 reads `.ps1` files as Windows-1252 (ANSI) when there is **no BOM**.
UTF-8 multibyte sequences get misinterpreted byte-by-byte. The critical case:

| Character | UTF-8 bytes | Windows-1252 decode | Effect |
|-----------|------------|---------------------|--------|
| em-dash `—` (U+2014) | `E2 80 94` | `â` + `€` + `"` (U+201D) | **String closed early** — PS 5.1 accepts RIGHT DOUBLE QUOTATION MARK as a string delimiter |

**Symptom:** `Missing closing '}' in statement block` reported for the `try`/`catch` or `if` block
that **contains** the double-quoted string with the em-dash. The `}` at the end of that string is
consumed as orphaned code, not a block closer. `git checkout --` does **not** fix it if the
BOM-less file is already in git history.

**Diagnosis:**
```powershell
$errors = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile($file, [ref]$null, [ref]$errors)
$errors   # zero entries = clean parse
```

**Fix (idempotent — add BOM, no content change):**
```powershell
$content = [System.IO.File]::ReadAllText($file, [System.Text.Encoding]::UTF8)
[System.IO.File]::WriteAllText($file, $content, (New-Object System.Text.UTF8Encoding($true)))
```

**Rule:** Every `.ps1` file in the repo that contains non-ASCII characters (em-dashes, box-drawing,
Unicode arrows, Greek letters, etc.) **must** have a UTF-8 BOM. `install.ps1` was already BOM-safe
(written by Claude Code's Write tool which emits UTF-8); `start.ps1` was not (first authored
externally). Fixed in orama-system commit `2f78e35`.

**Single-quoted strings** are safe — PS only looks for `'` to close them, never smart quotes.
**Here-strings** (`@"..."@`) are safe — only `"@` at column 0 closes them.
**Em-dashes in comments** are safe. Only **double-quoted string literals** are at risk.

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

```powershell
# Core toolchain
git --version
node --version
npm --version

# Hermes/bash wrapper (when Hermes wrappers are in scope)
& $env:HERMES_GIT_BASH_PATH --noprofile --norc -lc 'echo hermes-bash-ok'

# gstack-brain-sync (two variants — use .cmd when bash-shebang wrapper is unavailable,
# e.g. in plain PowerShell sessions without Git Bash on PATH)
gstack-brain-sync --status                          # bash-shebang variant (requires Git Bash)
~/.claude/skills/gstack/bin/gstack-brain-sync.cmd --status  # .cmd variant (pure PowerShell)
```

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

## Git operations — gold nuggets (sticky notes)

> **Run these skills before any branch triage, rebase, merge, or delete** after a suspected
> history rewrite. Catalog: `.agent/memory/working/BRANCH_CATALOG_COMPLETE_2026-06-27.md`.

### Sticky skill routing (next git op)

| Situation | Skill / reference (orama-system) |
|-----------|----------------------------------|
| Branch looks 600+ behind / `merge-base` exit 1 | [`git-history-surgery`](../../orama-system/bin/orama-system/skills/git-history-surgery/SKILL.md) → [`reanchor-after-rewrite.md`](../../orama-system/bin/orama-system/skills/git-history-surgery/references/reanchor-after-rewrite.md) |
| Scan all local heads vs rewritten `main` | PT: `scripts/git/reanchor_scan.sh . origin/main heads` — see [`using-git-worktrees`](../../orama-system/bin/orama-system/skills/using-git-worktrees/SKILL.md) |
| Verify unique work before PR | `git cherry -v origin/main <tip> <twin-base-from-scan>` — only `+` lines are truly unmerged |
| Case A: tip already in main as tree twin | `git branch -f <branch> <twin-sha>` (or detach worktree at twin first) — **not** `git rebase origin/main` |
| Case B: commits above twin need replay | Re-anchor to deepest twin, then cherry-pick/rebase only `+` commits |
| Windows host before fetch/rebase/push | [`windows-powershell-runtime-bootstrap.md`](../../orama-system/bin/orama-system/skills/git-history-surgery/references/windows-powershell-runtime-bootstrap.md) |
| `.cmd` blocks checkout/rebase on macOS | [`platform-line-endings-turf.md`](../../orama-system/bin/orama-system/skills/git-history-surgery/references/platform-line-endings-turf.md) — do not `git restore` CRLF files to LF |
| Nested multi-agent merges | [`git-history-surgery`](../../orama-system/bin/orama-system/skills/git-history-surgery/SKILL.md) + episodic `nested-branch-merge-protocol` (2026-06-26) |
| `check_tdd_commit.sh`: `mapfile: command not found` | [`bash-32-git-script-portability.md`](../../orama-system/bin/orama-system/skills/git-history-surgery/references/bash-32-git-script-portability.md) — macOS bash 3.2; use `while read` not `mapfile` |
| Install TDD + hygiene hooks | `bash scripts/git/install-local-hooks.sh` (orama or PT sibling) — commit-msg runs `check_tdd_commit.sh` |

### Gold nuggets (2026-06-27 branch catalog)

1. **Never trust `merge-base exit 1` or ahead/behind alone after a rewrite.** `cursor/critical-bug-investigation-0df5` was misclassified as unrelated orphan (647 behind); tree-twin scan showed tip `c1ae82e` = main twin `ad702c5` — work already absorbed. Action: re-anchor ref, not rebase.
2. **`reanchor_scan.sh` + `git cherry -v` is the canonical triage pair** — replaces naive `git branch --no-merged` inventories. Save markdown catalog before destructive ops.
3. **orama branches are not orphan class** — large June integration branches (`2026-06-13/14-*`) are stale merge-bases (`a156104`), not unrelated history. Still use cherry `+` before rebase.
4. **PT unrelated-looking branches may be MERGED/in-main** — 12 heads classified MERGED/in-main by tree-twin (incl. `feat/perpetua-submodule-upgrade`, `fix/pt71-clean`, `0df5`). Delete local after human review, not rebase.
5. **Open PR candidates (post cherry verify):** P1 `chore/domain-knowledge-windows-shims` (DOMAIN_KNOWLEDGE Windows shims); P2 `2026-06-11-001-win-endpoint-discovery-sync` (routing); P3 `clean-pt127`; orama `fix/pr135-lint006-windows` (LINT-006 Windows paths).
6. **Pre-destructive snapshot rule:** write `.agent/memory/working/BRANCH_CATALOG_COMPLETE_<date>.md` before rebase/delete/surgery — append-only memory, not a substitute for `reanchor_scan`.

## Vitest / TDD gate — gold nuggets (sticky notes)

> Canonical orama gate: `orama-system/docs/TDD.md`. Evidence:
> `docs/testing/2026-06-26-vite-frontend-tdd-gate.tdd.md`. Session log:
> `.agent/memory/working/VITEST_TDD_SESSION_2026-06-27.md`.

### Sticky skill routing

| Situation | Skill / reference (orama-system) |
|-----------|----------------------------------|
| Stage 4 TDD gate before commit | [`oramasys-method/references/tdd-gate.md`](../../orama-system/bin/orama-system/skills/oramasys-method/references/tdd-gate.md) |
| Bash 3.2 hook portability (no `mapfile`) | [`bash-32-git-script-portability.md`](../../orama-system/bin/orama-system/skills/git-history-surgery/references/bash-32-git-script-portability.md) |
| Operator console tests | `cd orama-system/web && pnpm test` (16 tests / 5 files on branch) |
| `web/src/` change without test | `tdd-skip: <reason>` in commit message OR paired `*.test.ts(x)` |

### Gold nuggets (2026-06-27 Vitest/TDD session)

1. **RC-1 gate on branch, not main** — merge orama PR #118 before treating Vitest as shipped.
2. **`check_tdd_commit.sh`** — commit-msg gate; macOS needs `while read` not `mapfile` (importance 9).
3. **Nav smokes** — `CommandCenter.test.tsx`: composer / runs / artifacts exclusive panels.
4. **Empty dry cherry-pick** — delete absorbed branches; don't PR (pairs with tree-twin triage).
5. **CRLF PR order** — #116 before #117/#118 on `gstack-brain-sync.cmd`.
6. **Playwright E2E** — deferred until post-merge (importance 5).

## Codex CLI v0.142.x dispatch — gold nuggets (sticky notes)

> Canonical orama card:
> [`codex-cli-v142-dispatch.md`](../../orama-system/bin/orama-system/references/codex-cli-v142-dispatch.md).
> Working log: `.agent/memory/working/CODEX_V142_DISPATCH_2026-06-28.md`.
> Launcher: `orama-system/.../dispatch_codex_partner.py`.

### Sticky skill routing

| Situation | Skill / reference (orama-system) |
|-----------|----------------------------------|
| Codex fanout from orchestrator | [`codex-cli-v142-dispatch.md`](../../orama-system/bin/orama-system/references/codex-cli-v142-dispatch.md) profile **fanout** |
| TTY / interactive Codex | same card, profile **interactive** (`--sandbox danger-full-access --ask-for-approval never`) |
| Resolve paths at runtime | `-C` repo root + repo-relative pytest paths — never hardcoded host paths |
| Windows PATH for Codex | `platform/windows/ensure-partner-cli-paths.ps1` (native before LM Studio shim) |

### Gold nuggets (2026-06-28 Win testdrive)

1. **`--approval-mode` removed in 0.140+** — fanout failures are flag drift, not npm vs WinGet version skew (both can be 0.142.x).
2. **Use `-C <repo-root>`** so prompts stay relative (`tests/foo.py`); do not paste absolute checkout paths into fanout prompts.
3. **Three profiles:** fanout (exec+bypass), bounded (exec+workspace-write), interactive (top-level sandbox+never).
4. **Cite the canonical card** from all codex-related skills — do not fork flag tables into SKILL bodies.

## Hermes skill absorption — gold nuggets (sticky notes)

> Canonical map:
> [`hermes-skill-absorption-map.md`](../../orama-system/bin/orama-system/skills/hermes-harness/references/hermes-skill-absorption-map.md).
> Working log: `.agent/memory/working/HERMES_ABSORPTION_AUDIT_2026-06-28.md`.

### Sticky skill routing

| Situation | Skill / reference (orama-system) |
|-----------|----------------------------------|
| Old Hermes slug (`hermes-agent`, etc.) | Load redirect target from absorption map — never the stub body |
| `.agents/perpetua-hardware` | Points to `hardware-affinity-gate` (orama), not PT/hardware folder |
| Archive `llm-council-orchestration` | SUPERSEDED → `pt-orama-council` + `hermes-council-review-gates` |
| Win LM Studio coder | `qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2` via loaded probe |

### Gold nuggets (2026-06-28 absorption audit)

1. **Redirect stubs + `.agents` wrappers** must stay thin — canonical bodies only in `bin/orama-system/skills/`.
2. **Dual-layer hardware:** orama `hardware-affinity-gate` (methodology) + PT policy YAML (runtime SSoT) + Hermes `pt-hardware-policy` (edge).
3. **Never use archive council skill** — invented "Qwen 3.6 Coder" was wrong; use live model ID from LM Studio.

## Hermes integration authority — gold nuggets (sticky notes)

> Plan: `orama-system/docs/plans/2026-06-28-hermes-integration-authority.md`.
> Protocol: `hermes-harness/references/hermes-universal-invocation-protocol.md`.
> Working log: `.agent/memory/working/HERMES_INTEGRATION_AUTHORITY_2026-06-28.md`.

### Sticky skill routing

| Situation | Skill / reference (orama-system) |
|-----------|----------------------------------|
| Hermes dispatch envelope | `hermes-universal-invocation-protocol.md` — core trio + L2 extensions |
| Partner audit trail | L2 `transport: { partner, profile }` (L1 CLI stays internal) |
| Delegation identity | `agent_id` = owner, `executor_id` = runner |
| Lesson graduation (optional) | `pt-orama-lesson-mining` only with `--include-optional`; no PT dependency |
| OpenClaw on Windows | Registry entry OK; Mac-only ops return `blocked` envelope |

### Gold nuggets (2026-06-28 authority batch)

1. **hermes-harness v1.1.0.0** matches openclaw-skills authority: registry, bootstrap JSON health, boundaries.
2. **Command cards** live under `hermes-harness/commands/<slug>/`, not top-level `skills/<slug>/`.
3. **Result superset:** OpenClaw core (`status`, `files_modified`, `follow_up_actions`) + optional Hermes fields.
4. **Four required thin wrappers** (council, review, delegate, hardware-policy); lesson-mining is optional.
