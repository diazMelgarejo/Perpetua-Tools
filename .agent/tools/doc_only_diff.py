"""Prove a commit range changed documentation only (docstrings and comments).

usage: python -I .agent/tools/doc_only_diff.py <repo_root> <base_rev> <head_rev> [--strict-markdown]

For every file changed between base and head:
  .py        ASTs must be equal after removing module/class/function docstrings, and the
             "directive" comments (shebang, encoding cookie, type:, noqa, pragma, fmt:,
             isort:, pylint:, mypy:, ruff:, pyright:) must be identical
  .ps1/.psm1 PowerShell token streams must be equal after dropping comment tokens
  .sh        lines must be equal after dropping blank and comment-only lines; text inside a
             here-document is data and is always compared (an unterminated one is UNPROVABLE)
  .md        listed under "markdown_unreviewed": markdown is not semantically compared (fenced
             code and configuration snippets can carry behaviour); --strict-markdown makes any
             markdown change fail instead
Any other changed file is reported as NOT-DOC. A git failure (unknown revision) fails closed.
Exit 0 only when every file is documentation-only.
"""
from __future__ import annotations

import ast
import io
import json
import re
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

PS_TOKENS = r"""
$src = [IO.File]::ReadAllText($args[0])
$tokens = $null; $errs = $null
[void][System.Management.Automation.Language.Parser]::ParseInput($src, [ref]$tokens, [ref]$errs)
$out = foreach ($t in $tokens) {
  if ($t.Kind -eq 'Comment' -or $t.Kind -eq 'NewLine' -or $t.Kind -eq 'LineContinuation') { continue }
  "$($t.Kind)|$($t.Text)"
}
($out -join "`n")
"""

# Comments that carry meaning to tools: a change here is not "just documentation".
_PY_DIRECTIVE = re.compile(
    r"^#!|^#.*coding[:=]|#\s*(type|noqa|pragma|fmt|isort|pylint|mypy|ruff|pyright)\b",
    re.IGNORECASE,
)
# <<WORD, <<-WORD, <<'WORD', <<"WORD" (but not the <<< here-string).
_HEREDOC = re.compile(r"(?<!<)<<(?!<)(-?)\s*\\?(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")


def git_show(root: Path, rev: str, path: str):
    """Return a file's bytes at a revision, or None when it does not exist there."""
    proc = subprocess.run(["git", "-C", str(root), "show", f"{rev}:{path}"], capture_output=True)
    return proc.stdout if proc.returncode == 0 else None


def py_directives(src: bytes) -> list:
    """Return the comments that carry meaning to tools (shebang, encoding cookie, type/lint/format pragmas)."""
    found = []
    for tok in tokenize.generate_tokens(io.StringIO(src.decode("utf-8-sig")).readline):
        if tok.type == tokenize.COMMENT and _PY_DIRECTIVE.search(tok.string):
            found.append(tok.string.strip())
    return found


def strip_py(src: bytes) -> str:
    """Return an AST dump with docstrings removed, followed by the directive comments (compared verbatim)."""
    tree = ast.parse(src.decode("utf-8-sig"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree, include_attributes=False) + "\n" + repr(py_directives(src))


def ps_tokens(src: bytes) -> str:
    """Return the PowerShell token stream (comments and newlines dropped) via the real 5.1 parser."""
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "x.ps1"
        f.write_bytes(src)
        helper = Path(d) / "tok.ps1"
        helper.write_text(PS_TOKENS, encoding="utf-8-sig")
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(helper), str(f)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            raise RuntimeError(f"PowerShell tokenization failed: {proc.stderr.strip()[:500]}")
        return proc.stdout


def strip_sh(src: bytes) -> list:
    """Return comparable shell lines; here-document bodies are data and are always kept.

    A here-document starts at <<WORD (or <<-WORD, <<'WORD') and ends at a line holding only WORD
    (leading tabs allowed for <<-). The <<< here-string is not a here-document. An unterminated
    here-document raises ValueError so the change cannot be certified.
    """
    out: list[str] = []
    pending: list[tuple[str, bool]] = []
    for line in src.decode("utf-8-sig").splitlines():
        if pending:
            word, dash = pending[0]
            out.append(line.rstrip())
            if (line.lstrip("\t") if dash else line).rstrip() == word:
                pending.pop(0)
            continue
        stripped = line.strip()
        if not stripped or (stripped.startswith("#") and not stripped.startswith("#!")):
            continue
        out.append(line.rstrip())
        for match in _HEREDOC.finditer(line):
            pending.append((match.group(3), match.group(1) == "-"))
    if pending:
        raise ValueError("unterminated here-document; cannot prove documentation-only shell change")
    return out


def main(argv):
    """Compare every file changed between two revisions; exit 0 only when all changes are documentation-only."""
    strict_md = "--strict-markdown" in argv
    argv = [a for a in argv if a != "--strict-markdown"]
    root, base, head = Path(argv[0]), argv[1], argv[2]
    diff = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", f"{base}..{head}"],
        capture_output=True,
        text=True,
    )
    if diff.returncode != 0:
        print(json.dumps({"doc_only": False, "error": diff.stderr.strip() or "git diff failed"}))
        return 1
    names = diff.stdout.split()
    report, ok, markdown = [], True, []
    for name in names:
        a, b = git_show(root, base, name), git_show(root, head, name)
        suffix = Path(name).suffix.lower()
        if a is None or b is None:
            status = "ADDED-OR-DELETED"
        elif suffix == ".py":
            status = "doc-only" if strip_py(a) == strip_py(b) else "CODE-CHANGED"
        elif suffix in (".ps1", ".psm1"):
            status = "doc-only" if ps_tokens(a) == ps_tokens(b) else "CODE-CHANGED"
        elif suffix == ".sh":
            try:
                status = "doc-only" if strip_sh(a) == strip_sh(b) else "CODE-CHANGED"
            except ValueError as error:
                status = f"UNPROVABLE: {error}"
        elif suffix == ".md":
            markdown.append(name)
            status = "UNPROVABLE: markdown is not semantically compared" if strict_md else "doc-only"
        else:
            status = "NOT-DOC"
        ok = ok and status == "doc-only"
        report.append({"file": name, "status": status})
    print(json.dumps({"doc_only": ok, "markdown_unreviewed": markdown, "files": report}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
