# 10. Line Endings & Encoding (Cross-Platform)

**TL;DR:** Never rely on per-developer `core.autocrlf`. Commit a `.gitattributes` + `.editorconfig` pair at the repo root, run `git add --renormalize .` once, and phantom "modified on checkout" diffs disappear for every contributor on Windows, macOS, Linux, and BSD — permanently.

---

## Root Cause

A file that "keeps getting modified on checkout" is almost never a real change. It is Git's line-ending conversion firing because the policy lives in each developer's *local* config (`core.autocrlf`) instead of in the repository itself.

`core.autocrlf` is set per clone. The moment one contributor's setting disagrees with the bytes actually stored in the repo, Git rewrites CRLF↔LF on checkout and reports the whole file as dirty even though nothing meaningful changed. Telling every contributor to "just set `core.autocrlf` correctly" is a losing game — it breaks the instant a new person joins with a fresh machine. Byte Order Marks (BOM) compound the mess: Git never manages encoding at all, so a BOM silently injected by a legacy Windows editor can break `bash`, `gcc`, and `python` on UNIX (a shebang preceded by `\xEF\xBB\xBF` is no longer a shebang).

The elegant, community-agreed fix is to stop tuning local configs and instead push the policy *into the repository*, where it is enforced for everyone from the first clone. Two small root-level files do the whole job: `.gitattributes` owns line endings (the Git layer), `.editorconfig` owns encoding and prevents the problem at authoring time (the editor layer).

---

## Fix

### Step 1 — Line endings: `.gitattributes`

Create `.gitattributes` at the repo root. It overrides local developer settings and normalizes line endings consistently across all operating systems.

```gitattributes
# Default: auto-detect text vs binary, normalize text to LF in the repository.
* text=auto

# UNIX scripts that must always be LF, even in a Windows working tree.
*.sh   text eol=lf
*.bash text eol=lf
*.py   text eol=lf

# Windows-only files that genuinely require CRLF to run correctly.
*.bat  text eol=crlf
*.cmd  text eol=crlf
*.ps1  text eol=crlf

# Binaries: never diff as text, never convert line endings.
*.png binary
*.jpg binary
*.gif binary
*.ico binary
*.woff binary
```

**How it works both ways.** `text=auto` stores every text file as LF *in the repository* on every platform, so the committed blob is identical no matter who commits it — that is what kills the phantom diffs. The working-tree ending is then decided per platform:

- **Windows** — with the developer's `core.autocrlf=true`, Git checks files out as CRLF so native tooling is happy, and converts them back to LF on staging. UNIX scripts and Windows scripts get their explicit `eol=` override regardless.
- **UNIX-like (macOS / Linux / FreeBSD)** — files check out as LF and commit as LF. No conversion, no phantom modifications.

**Modern alternative — LF everywhere.** Many current cross-platform projects (VS Code, Node.js, React) drop the smart-checkout dance entirely and force LF in the working tree too:

```gitattributes
* text=auto eol=lf
```

Every mainstream Windows editor, compiler, and even Notepad has handled LF cleanly for years, so there is no longer a reason to hand Windows CRLF. This variant is simpler and removes the last dependency on `core.autocrlf`. Keep the `*.bat`/`*.cmd`/`*.ps1 eol=crlf` overrides — those files still need CRLF on Windows. Prefer this LF-everywhere form for new repos; use the `text=auto` smart-checkout form when a Windows toolchain in the project genuinely chokes on LF.

### Step 2 — Encoding / BOM: `.editorconfig`

Git handles line endings but not Byte Order Marks. The golden rule for cross-platform open source is **UTF-8 without BOM**. Create `.editorconfig` at the repo root; every major IDE (VS Code, Visual Studio, IntelliJ/Rider, Vim, Sublime, Notepad++) reads it natively or via a near-universal plugin and applies it on save.

```editorconfig
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.{bat,cmd,ps1}]
end_of_line = crlf
```

**How it works both ways.** On Windows and UNIX alike, the instant a contributor saves, the editor guarantees the file is pure UTF-8 (no BOM) with standardized line endings — *before* Git ever evaluates the change. `.gitattributes` cleans problems up at commit time; `.editorconfig` prevents them from being typed in at all. The pair is belt-and-suspenders, and it is the exact setup shipped by the large open-source projects above.

Do not add a BOM. It breaks UNIX shebangs and is unnecessary on modern Windows (VS Code, PowerShell Core `pwsh`, and Notepad since Windows 10 1809 all handle BOM-less UTF-8). The only tools that still emit or require a BOM are legacy Windows PowerShell 5.1 (`Out-File`/`Set-Content`) and old Excel CSV import — handle those at the point of generation (`Out-File -Encoding utf8NoBOM`), never by letting a BOM into the repo.

### Step 3 — Clear the cache and normalize (the one-time reset)

Adding `.gitattributes` does **not** retroactively fix files already committed with the wrong ending — the index still holds the old blobs, which is exactly why the phantom diffs survive until you renormalize. Force Git to re-evaluate the whole tree once:

```bash
# 1. Commit the rules first, so renormalization uses them.
git add .gitattributes .editorconfig
git commit -m "build: add cross-platform line-ending and encoding rules"

# 2. Re-evaluate every tracked file against the new rules.
git add --renormalize .

# 3. Confirm — the phantom modifications are gone.
git status

# 4. Commit the normalized blobs (may be empty if the repo was already clean).
git commit -m "build: normalize line endings across project"
```

Once this lands on `main`, any developer cloning on Windows, macOS, Linux, or BSD gets a clean working tree with zero automatic-modification noise.

---

## Verification

```bash
# What ending will Git store for a given file? (look for "text eol=lf")
git check-attr -a path/to/file.py

# Any CRLF left in the index for a file that should be LF? (should print nothing)
git show :path/to/file.py | grep -c $'\r'

# Any BOM at the head of a file? (0xEF 0xBB 0xBF should be absent)
head -c 3 path/to/file.py | xxd

# After renormalize, a fresh clone should show zero pending changes.
git status --porcelain
```

---

## Rules

- **Policy belongs in the repo, not in `~/.gitconfig`.** `.gitattributes` + `.editorconfig` are enforced from the first clone; `core.autocrlf` is not.
- **LF in the repository, always.** Choose LF-everywhere (`* text=auto eol=lf`) for new repos; use smart-checkout (`* text=auto`) only when a Windows toolchain needs CRLF in the working tree.
- **UTF-8 without BOM, always.** A BOM breaks UNIX shebangs; solve legacy-Windows BOM needs at generation time, never in the tree.
- **Name the exceptions explicitly.** `*.bat`/`*.cmd`/`*.ps1` → CRLF; binaries → `binary`. Everything else follows the default.
- **Always renormalize after adding the rules.** Without `git add --renormalize .` the old blobs persist and the phantom diffs continue.
- **Optional safety net.** With `.gitattributes` present the per-OS `core.autocrlf` (`true` on Windows, `input` on UNIX) becomes mostly redundant, but it is harmless as a backstop for files the attributes file does not cover.

---

## Related

- Companion mirror (orama-system): [wiki/17-line-endings-and-encoding.md](https://github.com/diazMelgarejo/orama-system/blob/main/docs/wiki/17-line-endings-and-encoding.md)
- This is the **canonical** copy; the orama page mirrors it.
- Enforced by the same portable-path / mojibake discipline as [wiki README](README.md) conventions.
