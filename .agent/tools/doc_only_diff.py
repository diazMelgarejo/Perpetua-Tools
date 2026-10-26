"""Prove a commit range changed documentation only (docstrings and comments).

usage: python -I .agent/tools/doc_only_diff.py <repo_root> <base_rev> <head_rev>

For every file changed between base and head:
  .py        ASTs must be equal after removing module/class/function docstrings
  .ps1/.psm1 PowerShell token streams must be equal after dropping comment tokens
  .sh        lines must be equal after dropping blank and comment-only lines
Any other changed file is reported as NOT-DOC. Exit 0 only when every file is
documentation-only.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
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


def git_show(root: Path, rev: str, path: str):
    """Return a file's bytes at a revision, or None when it does not exist there."""
    proc = subprocess.run(["git", "-C", str(root), "show", f"{rev}:{path}"], capture_output=True)
    return proc.stdout if proc.returncode == 0 else None


def strip_py(src: bytes) -> str:
    """Return an AST dump with module, class and function docstrings removed."""
    tree = ast.parse(src.decode("utf-8-sig"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree, include_attributes=False)


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
    """Return comparable shell lines, rejecting constructs whose comments affect content."""
    out: list[str] = []
    heredoc = False
    for line in src.decode("utf-8-sig").splitlines():
        stripped = line.strip()
        if heredoc:
            out.append(line.rstrip())
            if stripped == "EOF":
                heredoc = False
            continue
        if "<<" in line:
            heredoc = True
            out.append(line.rstrip())
            continue
        if not stripped or (stripped.startswith("#") and not stripped.startswith("#!")):
            continue
        out.append(line.rstrip())
    if heredoc:
        raise ValueError("unterminated here-document; cannot prove documentation-only shell change")
    return out


def main(argv):
    """Compare every file changed between two revisions; exit 0 only when all changes are documentation-only."""
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
    report, ok = [], True
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
            status = "doc-only"
        else:
            status = "NOT-DOC"
        ok = ok and status == "doc-only"
        report.append({"file": name, "status": status})
    print(json.dumps({"doc_only": ok, "files": report}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
