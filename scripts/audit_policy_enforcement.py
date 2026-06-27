#!/usr/bin/env python3
"""Verify policy decision sites import utils.hardware_policy (T1-C).

Files that mention NEVER_MAC / NEVER_WIN must route enforcement through the
canonical hardware_policy API — not inline duplicate parsers.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY_KEYWORDS = frozenset({"NEVER_MAC", "NEVER_WIN", "ALWAYS_MAC", "ALWAYS_WIN"})
EXEMPT_PREFIXES = (
    "src/utils/hardware_policy.py",
    "scripts/audit_policy_enforcement.py",
    "tests/",
    "vendor/",
    ".venv/",
)
_HARDWARE_POLICY_MODULES = frozenset({
    "utils.hardware_policy",
    "src.utils.hardware_policy",
})


def _is_exempt(rel: str) -> bool:
    if rel.startswith(EXEMPT_PREFIXES):
        return True
    if "/tests/" in rel or rel.startswith("tests/"):
        return True
    return False


def _mentions_policy_keywords(source: str) -> bool:
    """Detect policy keyword usage in real code, not comments/string bypass tricks."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return any(kw in source for kw in POLICY_KEYWORDS)

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in POLICY_KEYWORDS:
            return True
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if any(kw in node.value for kw in POLICY_KEYWORDS):
                return True
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    if any(kw in part.value for kw in POLICY_KEYWORDS):
                        return True
    return False


def _imports_hardware_policy(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _HARDWARE_POLICY_MODULES:
                    return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in _HARDWARE_POLICY_MODULES:
                return True
        elif isinstance(node, ast.Attribute):
            if node.attr == "hardware_policy":
                if isinstance(node.value, ast.Name) and node.value.id == "utils":
                    return True
    return False


def main() -> int:
    violations: list[str] = []
    for py in sorted(ROOT.rglob("*.py")):
        rel = py.relative_to(ROOT).as_posix()
        if _is_exempt(rel) or "__pycache__" in rel:
            continue
        try:
            source = py.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError:
            # Unparseable files still get the keyword check; only AST-based
            # import detection is skipped. This preserves the raw-source
            # fallback path: a file with syntax errors but policy keywords
            # without the canonical import is still flagged as a violation.
            tree = None
        if not _mentions_policy_keywords(source):
            continue
        if not _imports_hardware_policy(tree):
            violations.append(
                f"{rel}: policy keyword without utils.hardware_policy import"
            )
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    print("OK: all policy enforcement sites use hardware_policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
