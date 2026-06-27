#!/usr/bin/env python3
"""Verify policy decision sites import utils.hardware_policy (T1-C).

Files that mention NEVER_MAC / NEVER_WIN must route enforcement through the
canonical hardware_policy API — not inline duplicate parsers.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY_KEYWORDS = frozenset({"NEVER_MAC", "NEVER_WIN", "ALWAYS_MAC", "ALWAYS_WIN"})
EXEMPT_PREFIXES = (
    "src/utils/hardware_policy.py",
    "tests/",
    "vendor/",
    ".venv/",
)
CANONICAL_MARKERS = (
    "from utils.hardware_policy import",
    "from src.utils.hardware_policy import",
    "import utils.hardware_policy",
    "utils.hardware_policy.",
)


def _is_exempt(rel: str) -> bool:
    if rel.startswith(EXEMPT_PREFIXES):
        return True
    if "/tests/" in rel or rel.startswith("tests/"):
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
        if not any(kw in source for kw in POLICY_KEYWORDS):
            continue
        if not any(marker in source for marker in CANONICAL_MARKERS):
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
