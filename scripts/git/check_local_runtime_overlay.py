#!/usr/bin/env python3
"""Block committing operator LAN topology into local-runtime overlay YAML files.

config/devices.yml and config/models.yml may carry discovery-written DHCP addresses
in the **working tree**. That overlay is intentional and must not be discarded by
agents. Only **staged** content is checked — uncommitted local drift is allowed.

See config/LOCAL-RUNTIME-OVERLAY.md.
"""
from __future__ import annotations

import argparse
import ipaddress
import re
import subprocess
import sys
from pathlib import Path

OVERLAY_FILES = frozenset(
    {
        "config/devices.yml",
        "config/models.yml",
    }
)

_LAN_IP_RE = re.compile(
    r'^\s*lan_ip:\s*"(?P<ip>(?:\d{1,3}\.){3}\d{1,3})"',
    re.MULTILINE,
)
_HOST_DEFAULT_RE = re.compile(
    r'^\s*host:\s*"\$\{[^}]+\:-https?://(?P<host>[^"/]+)',
    re.MULTILINE,
)
_IP_IN_LINE_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

_PRIVATE_NETS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)

_SAFE_LITERALS = frozenset({"localhost", "127.0.0.1", "0.0.0.0"})


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def staged_overlay_paths(root: Path) -> list[str]:
    proc = _run_git(
        root,
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=ACMR",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git diff --cached failed")
    return [line for line in proc.stdout.splitlines() if line in OVERLAY_FILES]


def staged_file_text(root: Path, rel: str) -> str:
    proc = _run_git(root, "show", f":{rel}")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git show :{rel} failed")
    return proc.stdout


def _is_private_ip(value: str) -> bool:
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return False
    if addr.is_loopback:
        return False
    return any(addr in net for net in _PRIVATE_NETS)


def _violations_in_text(rel: str, text: str, *, context: str = "staged") -> list[str]:
    errors: list[str] = []
    if rel == "config/devices.yml":
        for match in _LAN_IP_RE.finditer(text):
            ip = match.group("ip")
            if _is_private_ip(ip):
                line_no = text[: match.start()].count("\n") + 1
                errors.append(
                    f"{rel}:{line_no}: {context} lan_ip must stay empty/loopback; "
                    "local discovery overlay must not be committed "
                    "(see config/LOCAL-RUNTIME-OVERLAY.md)"
                )
    if rel == "config/models.yml":
        for line_no, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            host_match = _HOST_DEFAULT_RE.match(line)
            if host_match:
                host = host_match.group("host")
                if host.casefold() in _SAFE_LITERALS:
                    continue
                if _is_private_ip(host):
                    errors.append(
                        f"{rel}:{line_no}: {context} host default must not embed "
                        "operator LAN topology "
                        "(see config/LOCAL-RUNTIME-OVERLAY.md)"
                    )
                    continue
            if "host:" in line:
                for ip_match in _IP_IN_LINE_RE.finditer(line):
                    ip = ip_match.group(0)
                    if _is_private_ip(ip):
                        errors.append(
                            f"{rel}:{line_no}: {context} host must not embed "
                            "operator LAN topology "
                            "(see config/LOCAL-RUNTIME-OVERLAY.md)"
                        )
                        break
    return errors


def check_tree_overlay(root: Path) -> list[str]:
    """Validate on-disk overlay files (CI / integrity checks on clean checkout)."""
    errors: list[str] = []
    for rel in sorted(OVERLAY_FILES):
        path = root / rel
        if not path.is_file():
            continue
        errors.extend(_violations_in_text(rel, path.read_text(encoding="utf-8"), context="committed"))
    return errors


def check_staged_overlay(root: Path) -> list[str]:
    errors: list[str] = []
    for rel in staged_overlay_paths(root):
        try:
            text = staged_file_text(root, rel)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        errors.extend(_violations_in_text(rel, text, context="staged"))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo",
        nargs="?",
        default=".",
        help="repository root (default: .)",
    )
    parser.add_argument(
        "--mode",
        choices=("staged", "tree"),
        default="staged",
        help="staged: index only (pre-commit); tree: on-disk files (CI)",
    )
    args = parser.parse_args(argv)
    root = Path(args.repo).resolve()
    errors = (
        check_tree_overlay(root)
        if args.mode == "tree"
        else check_staged_overlay(root)
    )
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print("OK: local runtime overlay (staged) check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
