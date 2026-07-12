#!/usr/bin/env python3
"""Sanitize hardcoded private IPv4 addresses from tracked source/test files.

Replaces RFC1918 and link-local (169.254.0.0/16) IPs with loopback-range
(127.0.0.0/8) equivalents so tests and examples no longer leak real LAN
topology.  The mapping preserves /24 relationships so subnet-aware tests
(e.g. provenance bucketing) keep passing.

Usage:
    python scripts/sanitize_private_ips.py --dry-run
    python scripts/sanitize_private_ips.py --apply
"""
from __future__ import annotations

import argparse
import ipaddress
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple


# 127.0.0.0/8 is loopback and safe to use as a non-doxxing replacement.
_LOOPBACK_NET = ipaddress.ip_network("127.0.0.0/8")

# RFC1918 private ranges.  Link-local (169.254.0.0/16) is left untouched here
# because tests use it as a well-known SSRF target; it is not personal topology.
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]

# Do not touch these file categories (placeholders / env vars handled manually).
_SKIP_SUFFIXES = (
    ".md",
    ".yml",
    ".yaml",
    ".sh",
    ".json",
    ".jsonl",
    ".lock",
    ".example",
)

# Paths that are local-only or historical and should not be rewritten here.
_SKIP_PATH_PARTS = {
    ".agent/",
    ".claude/",
    ".cursor/",
    ".state/",
    "AGENT_RESUME.md",
    "CHANGELOG.md",
    "CLAUDE.md",
    "SKILL.md",
    "README.md",
    "vendor/",
    ".env",
    ".env.example",
    ".env.local",
}

_IP_RE = re.compile(
    r"\b(?P<ip>(?:[0-9]{1,3}\.){3}[0-9]{1,3})(?:/(?P<prefix>[0-9]{1,2}))?\b"
)


def _is_private(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in net for net in _PRIVATE_NETWORKS)


def _build_mapping(hosts: List[str], cidrs: List[str]) -> Dict[str, str]:
    """Return deterministic private-IP/CIDR -> loopback mappings.

    Hosts and CIDR network addresses that share the same original /24 are
    mapped to the same loopback /24, preserving the last octet (including .0
    for network addresses).  This keeps subnet-aware tests passing.
    """
    # Collect every unique /24 prefix that appears.
    prefixes: Dict[Tuple[int, int, int], int] = {}
    for ip_str in hosts:
        addr = ipaddress.ip_address(ip_str)
        key = (int(addr.packed[0]), int(addr.packed[1]), int(addr.packed[2]))
        prefixes.setdefault(key, len(prefixes) + 1)
    for cidr in cidrs:
        try:
            net = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue
        addr = net.network_address
        key = (int(addr.packed[0]), int(addr.packed[1]), int(addr.packed[2]))
        prefixes.setdefault(key, len(prefixes) + 1)

    if max(prefixes.values(), default=0) > 254:
        raise RuntimeError("Ran out of 127.x.y loopback /24 subnets")

    mapping: Dict[str, str] = {}
    for ip_str in hosts:
        addr = ipaddress.ip_address(ip_str)
        key = (int(addr.packed[0]), int(addr.packed[1]), int(addr.packed[2]))
        subnet = prefixes[key]
        last_octet = int(addr.packed[3])
        mapping[ip_str] = str(ipaddress.ip_address(f"127.0.{subnet}.{last_octet}"))

    for cidr in cidrs:
        try:
            net = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue
        addr = net.network_address
        key = (int(addr.packed[0]), int(addr.packed[1]), int(addr.packed[2]))
        subnet = prefixes[key]
        # CIDR network address always maps to .0 in the loopback /24.
        mapping[cidr] = f"127.0.{subnet}.0/{net.prefixlen}"

    return mapping


def _should_process(path: Path) -> bool:
    rel = str(path)
    for part in _SKIP_PATH_PARTS:
        if part in rel:
            return False
    if rel.endswith(_SKIP_SUFFIXES):
        return False
    return True


def _replace_in_text(text: str, mapping: Dict[str, str]) -> str:
    def repl(match: re.Match) -> str:
        original = match.group(0)
        ip = match.group("ip")
        prefix = match.group("prefix")
        if prefix is not None:
            cidr = original
            return mapping.get(cidr, original)
        return mapping.get(ip, original)

    return _IP_RE.sub(repl, text)


def _collect_private_ips(text: str) -> Tuple[List[str], List[str]]:
    hosts: List[str] = []
    cidrs: List[str] = []
    for match in _IP_RE.finditer(text):
        ip = match.group("ip")
        prefix = match.group("prefix")
        if not _is_private(ip):
            continue
        if prefix is not None:
            cidrs.append(match.group(0))
            # Also bucket the CIDR's network address so it gets a loopback mapping.
            hosts.append(ip)
        else:
            hosts.append(ip)
    return hosts, cidrs


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes to disk")
    parser.add_argument("--paths", nargs="*", help="Restrict to specific paths")
    args = parser.parse_args(argv)

    if args.paths:
        tracked = [Path(p) for p in args.paths]
    else:
        result = subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, check=True
        )
        tracked = [Path(line) for line in result.stdout.splitlines() if line]

    files_to_process = [p for p in tracked if p.is_file() and _should_process(p)]

    total_hosts = 0
    total_cidrs = 0
    changed_files: List[Path] = []

    for path in files_to_process:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        hosts, cidrs = _collect_private_ips(text)
        if not hosts and not cidrs:
            continue

        mapping = _build_mapping(hosts, cidrs)

        new_text = _replace_in_text(text, mapping)
        if new_text == text:
            continue

        total_hosts += len(hosts)
        total_cidrs += len(cidrs)
        changed_files.append(path)

        print(f"{'[apply] ' if args.apply else '[dry-run] '}{path}")
        for old, new in sorted(mapping.items()):
            print(f"    {old} -> {new}")

        if args.apply:
            path.write_text(new_text, encoding="utf-8")

    print(
        f"\nSummary: {len(changed_files)} file(s) changed, "
        f"{total_hosts} host(s), {total_cidrs} CIDR(s) replaced."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
