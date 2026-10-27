"""Docstring coverage for Python, PowerShell and shell files.

usage: python -I .agent/tools/doc_coverage.py <repo_root> <file> [<file> ...] [--json]

Python: the module, every class and every (async) function at any depth must
have a docstring. PowerShell: the script must carry comment-based help, and so
must every function (checked with the PowerShell 5.1 parser's GetHelpContent).
Shell: a comment block must open the file (after any shebang) and sit directly
above every function definition. Other file types are reported as skipped.
Exit 0 only when every checked item is documented.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

PS_CHECK = r"""
$ErrorActionPreference = 'Stop'
$out = @()
foreach ($f in $args) {
  $tokens = $null; $errs = $null
  $ast = [System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$tokens, [ref]$errs)
  $missing = @()
  if ($errs.Count -gt 0) { $missing += "PARSE-ERROR: $($errs[0].Message) (line $($errs[0].Extent.StartLineNumber))" }
  if ($null -eq $ast.GetHelpContent()) { $missing += 'script help (line 1)' }
  $fns = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)
  $total = 1
  foreach ($fn in $fns) {
    $total++
    if ($null -eq $fn.GetHelpContent()) { $missing += "function $($fn.Name) (line $($fn.Extent.StartLineNumber))" }
  }
  $out += [pscustomobject]@{ file = $f; total = $total; missing = @($missing) }
}
$out | ConvertTo-Json -Depth 4 -Compress
"""

SH_FUNC = re.compile(r"^\s*(?:function\s+)?([A-Za-z_][\w:.-]*)\s*\(\)\s*\{?\s*(?:#.*)?$|^\s*function\s+([A-Za-z_][\w:.-]*)\s*\{")


def py_missing(path: Path):
    """Return (item count, missing list) for a Python file: module, classes and every function."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    total, missing = 1, []
    if not ast.get_docstring(tree):
        missing.append("module (line 1)")
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            total += 1
            if not ast.get_docstring(node):
                kind = "class" if isinstance(node, ast.ClassDef) else "def"
                missing.append(f"{kind} {node.name} (line {node.lineno})")
    return total, missing


def sh_missing(path: Path):
    """Return (item count, missing list) for a shell file: header comment and a comment above each function."""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    total, missing = 1, []
    i = 1 if lines and lines[0].startswith("#!") else 0
    if not (i < len(lines) and lines[i].lstrip().startswith("#")):
        missing.append("file header comment (line 1)")
    for n, line in enumerate(lines):
        m = SH_FUNC.match(line)
        if not m:
            continue
        total += 1
        prev = lines[n - 1].strip() if n else ""
        if not prev.startswith("#"):
            missing.append(f"function {m.group(1) or m.group(2)} (line {n + 1})")
    return total, missing


def main(argv):
    """Check every file given, print per-file coverage and a total; exit 0 only when nothing is missing."""
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    root, files = Path(argv[0]), argv[1:]
    results, ps_files = [], []
    for rel in files:
        p = root / rel
        if not p.is_file():
            results.append({"file": rel, "status": "absent"})
            continue
        suffix = p.suffix.lower()
        if suffix == ".py":
            total, missing = py_missing(p)
        elif suffix in (".ps1", ".psm1"):
            ps_files.append(rel)
            continue
        elif suffix == ".sh":
            total, missing = sh_missing(p)
        else:
            results.append({"file": rel, "status": "skipped"})
            continue
        results.append({"file": rel, "total": total, "missing": missing})
    if ps_files:
        import tempfile
        fd, helper_name = tempfile.mkstemp(prefix="doccov_", suffix=".ps1")
        helper = Path(helper_name)
        with open(fd, "w", encoding="utf-8-sig") as fh:
            fh.write(PS_CHECK)
        try:
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-File", str(helper), *[str(root / f) for f in ps_files]],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
        finally:
            helper.unlink(missing_ok=True)
        data = json.loads(proc.stdout.strip() or "[]")
        data = data if isinstance(data, list) else [data]
        if len(data) != len(ps_files):
            sys.exit(f"PowerShell check failed: {proc.stderr.strip()[:500]}")
        for rel, item in zip(ps_files, data):
            results.append({"file": rel, "total": item["total"], "missing": item.get("missing") or []})
    gaps = sum(
        len(r.get("missing", [])) + (1 if r.get("status") == "absent" else 0)
        for r in results
    )
    total = sum(r.get("total", 0) for r in results)
    if as_json:
        print(json.dumps({"total": total, "missing": gaps, "files": results}, indent=1))
    else:
        for r in results:
            if "status" in r:
                print(f"{r['file']}: {r['status']}")
                continue
            print(f"{r['file']}: {r['total'] - len(r['missing'])}/{r['total']}")
            for m in r["missing"]:
                print(f"    missing {m}")
        print(f"TOTAL documented {total - gaps}/{total}  missing={gaps}")
    return 0 if gaps == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
