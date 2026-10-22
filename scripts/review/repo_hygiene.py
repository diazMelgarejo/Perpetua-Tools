#!/usr/bin/env python3
"""Repo hygiene entrypoint with deterministic CI identity authorization.

The full scanner implementation is retained in ``repo_hygiene_core.py``,
including the staged prohibited-address gate (RFC1918, loopback, ULA, CGNAT).
This entrypoint owns the identity boundary because CI cannot depend on
operator-local ``.verboten-literals.local`` state. Pre-commit execs this file.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import repo_hygiene_core as _core

# Single source of truth for approved authors: scripts/git/identity-policy.json,
# read through the byte-synced canonical engine (never a local allowlist).
_GIT_SCRIPTS = _SCRIPT_DIR.parent / "git"
if str(_GIT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_GIT_SCRIPTS))
import audit_engine  # noqa: E402

for _name, _value in vars(_core).items():
    if not _name.startswith("__"):
        globals()[_name] = _value

# The scanner contains literal examples of the patterns it detects. Its old
# path was self-exempt; preserve that invariant after moving the unchanged
# implementation to repo_hygiene_core.py.
_CORE_RELATIVE_PATH = "scripts/review/repo_hygiene_core.py"
_core.PERSONAL_PATH_EXCEPTIONS.add(_CORE_RELATIVE_PATH)
_core.BIDI_CONTROL_EXCEPTIONS.add(_CORE_RELATIVE_PATH)
_core.SECRET_PATTERN_EXCEPTIONS.add(_CORE_RELATIVE_PATH)

AUTHORIZED_PRIVATE_IDENTITIES_FILE = ".github/authorized-private-identities.sha256"


def identity_fingerprint(name: str, email: str) -> str:
    canonical = f"{name.strip().casefold()} <{email.strip().casefold()}>"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def authorized_private_identity_hashes(root: Path) -> set[str]:
    path = root / AUTHORIZED_PRIVATE_IDENTITIES_FILE
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    hashes: set[str] = set()
    for raw in lines:
        value = raw.split("#", 1)[0].strip().casefold()
        if len(value) == 64 and all(ch in "0123456789abcdef" for ch in value):
            hashes.add(value)
    return hashes


def check_identity(root: Path) -> list[str]:
    name = _core.run_git(root, "config", "user.name").stdout.strip()
    email = _core.run_git(root, "config", "user.email").stdout.strip()
    if os.getenv("GITHUB_ACTIONS") == "true" and not name and not email:
        return []
    try:
        policy_result = audit_engine.is_approved_identity(
            name,
            email,
            root=root,
            repo_name=root.name,
            private_literal_values_fn=_core.private_literal_values,
            profile="configured",
        )
    except audit_engine.IdentityPolicyError as exc:
        return [f"identity policy error: {exc}"]
    if policy_result.approved:
        return []
    if identity_fingerprint(name, email) in authorized_private_identity_hashes(root):
        return []

    private_emails = {
        value.casefold() for value in _core.private_literal_values(root, "owner_gmail")
    }
    private_names = [
        value.casefold() for value in _core.private_literal_values(root, "owner_name")
    ]
    name_tokens = private_names or ["cyre"]
    if email.casefold() in private_emails and any(
        token in name.casefold() for token in name_tokens
    ):
        return []

    return [
        "git identity mismatch: "
        f"found {name or '<unset>'} <{email or '<unset>'}>; "
        f"{policy_result.reason} (scripts/git/identity-policy.json) "
        "and no authorized private identity fingerprint"
    ]


_core.check_identity = check_identity


def main() -> int:
    return _core.main()


if __name__ == "__main__":
    raise SystemExit(main())
