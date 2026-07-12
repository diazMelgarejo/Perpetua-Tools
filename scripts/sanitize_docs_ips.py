#!/usr/bin/env python3
"""Replace RFC1918 private IPs in documentation with placeholders.

Leaves link-local (169.254.0.0/16) untouched because it is a well-known
SSRF/example range, not personal topology.  Public IPs (8.8.8.8, 1.1.1.1)
are also left as-is.

Usage:
    python scripts/sanitize_docs_ips.py --dry-run
    python scripts/sanitize_docs_ips.py --apply
"""
from __future__ import annotations

import argparse
import ipaddress
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]

# Only process markdown / plain-text docs and hardware guides.
_ALLOWED_SUFFIXES = {".md"}

# Files that are local-only or already handled (match whole basename).
_SKIP_BASENAMES = {
    "AGENT_RESUME.md",
    "CHANGELOG.md",
    "CLAUDE.md",
    "SKILL.md",
    "README.md",
}
_SKIP_PATH_PARTS = {
    ".agent/",
    ".claude/",
    ".cursor/",
    ".state/",
    "vendor/",
}

_IP_RE = re.compile(
    r"\b(?P<ip>(?:[0-9]{1,3}\.){3}[0-9]{1,3})(?P<suffix>:(?:[0-9]+|\<[^>]+\>))?(?:/(?P<prefix>[0-9]{1,2}))?\b"
)


def _is_private(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in net for net in _PRIVATE_NETWORKS)


def _replace(text: str) -> str:
    def repl(match: re.Match) -> str:
        ip = match.group("ip")
        if not _is_private(ip):
            return match.group(0)
        suffix = match.group("suffix") or ""
        prefix = match.group("prefix")
        if prefix is not None:
            return f"<YOUR_LAN_IP>/{prefix}"
        return f"<YOUR_LAN_IP>{suffix}"

    return _IP_RE.sub(repl, text)


def _should_process(path: Path) -> bool:
    rel = str(path)
    # Skip only root-level memory/history files.
    if "/" not in rel and path.name in _SKIP_BASENAMES:
        return False
    for part in _SKIP_PATH_PARTS:
        if part in rel:
            return False
    return path.suffix in _ALLOWED_SUFFIXES


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes to disk")
    parser.add_argument("--paths", nargs="*", help="Restrict to specific paths")
    args = parser.parse_args(argv)

    if args.paths:
        tracked = [Path(p) for p in args.paths]
    else:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        tracked = [Path(line) for line in result.stdout.splitlines() if line]

    files_to_process = [p for p in tracked if p.is_file() and _should_process(p)]

    changed = 0
    for path in files_to_process:
        text = path.read_text(encoding="utf-8")
        new_text = _replace(text)
        if new_text == text:
            continue
        changed += 1
        print(f"{'[apply] ' if args.apply else '[dry-run] '}{path}")
        if args.apply:
            path.write_text(new_text, encoding="utf-8")

    print(f"\nSummary: {changed} doc file(s) changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
