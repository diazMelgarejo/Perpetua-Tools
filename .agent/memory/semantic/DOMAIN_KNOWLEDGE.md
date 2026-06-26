# Domain Knowledge

> Stable facts about the domains you work in. Not procedures (those go in
> skills), not preferences (those go in `personal/PREFERENCES.md`), not
> time-bound events (those go in `episodic/`). Pure reference material.

## Example sections
- API contracts you reuse
- Vendor quirks ("service X rate-limits at 60 rpm, not the documented 100")
- Domain-specific terminology

## Windows Development Environment (verified 2026-06-25)

### bash.exe — present but not on cmd.exe PATH
- `bash.exe` is at `C:\Program Files\Git\usr\bin\bash.exe` (also `\bin\bash.exe`).
- It IS on the Git Bash session PATH; NOT on cmd.exe's system PATH.
- Any tool spawning via cmd.exe (`shell: true` in Node/bun on Windows) cannot find bash.
- Claude Code's Bash tool runs its own bash at `/usr/bin/bash` — env vars there don't
  cross into PowerShell and vice-versa.

### gstack brain-sync Windows fix — `.cmd` wrapper (gstack issue #1731)
- `gstack-gbrain-sync.ts` uses `NEEDS_SHELL_ON_WINDOWS = process.platform === "win32"`,
  so bun spawns `gstack-brain-sync` via cmd.exe, which can't exec bash shebangs.
- Fix: `~/.claude/skills/gstack/bin/gstack-brain-sync.cmd` wrapper created 2026-06-25.
  Calls `C:\Program Files\Git\usr\bin\bash.exe` with the script path explicitly.
- Pattern: any bash shebang script in `~/.claude/skills/gstack/bin/` that needs to be
  callable from bun/Node.js on Windows needs a matching `.cmd` shim.

### LLAMA_SERVER_BASE_URL — already in PowerShell profile, never missing
- `%USERPROFILE%\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1` line 1:
  `$env:LLAMA_SERVER_BASE_URL = "http://localhost:1234/v1"` — verified present.
- Do NOT add it again. Not absent from PowerShell; just doesn't propagate to Bash tool.
- Export explicitly in bash sessions: `export LLAMA_SERVER_BASE_URL="http://localhost:1234/v1"`

### git -C flag required for orama-system in bash sessions
- The bash tool's cwd may differ from the `ultrathink-system` git root.
- Always use: `git -C "$ORAMA_SYSTEM_PATH" <subcommand>` for reliable results.

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
