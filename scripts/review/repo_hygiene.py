#!/usr/bin/env python3
"""Repo hygiene entrypoint with deterministic CI identity authorization.

The full scanner implementation is retained byte-for-byte in
``repo_hygiene_core.py``.  This entrypoint owns the identity boundary because
CI cannot depend on operator-local ``.verboten-literals.local`` state.
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

# Preserve the established import surface for tests and callers.
for _name, _value in vars(_core).items():
    if not _name.startswith("__"):
        globals()[_name] = _value

AUTHORIZED_PRIVATE_IDENTITIES_FILE = ".github/authorized-private-identities.sha256"


def identity_fingerprint(name: str, email: str) -> str:
    """Return the canonical SHA-256 identity fingerprint used by all guards."""
    canonical = f"{name.strip().casefold()} <{email.strip().casefold()}>"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def authorized_private_identity_hashes(root: Path) -> set[str]:
    """Load tracked exact-identity hashes; comments and blank lines are ignored."""
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
    """Validate git config without requiring operator-private files in CI.

    Authorization sources are additive and ordered from public to private:
    tracked public identities, tracked non-reversible exact-identity hashes,
    then the operator-local verboten-literals registry.
    """
    name = _core.run_git(root, "config", "user.name").stdout.strip()
    email = _core.run_git(root, "config", "user.email").stdout.strip()
    if os.getenv("GITHUB_ACTIONS") == "true" and not name and not email:
        return []

    if (name, email) in _core.APPROVED_IDENTITIES:
        return []

    digest = identity_fingerprint(name, email)
    if digest in authorized_private_identity_hashes(root):
        return []

    private_emails = {
        value.casefold() for value in _core.private_literal_values(root, "owner_gmail")
    }
    private_names = [
        value.casefold() for value in _core.private_literal_values(root, "owner_name")
    ]
    name_tokens = private_names or ["cyre"]
    private_identity_ok = (
        email.casefold() in private_emails
        and any(token in name.casefold() for token in name_tokens)
    )
    if private_identity_ok:
        return []

    expected = " or ".join(
        f"{approved_name} <{approved_email}>"
        for approved_name, approved_email in sorted(_core.APPROVED_IDENTITIES)
    )
    return [
        "git identity mismatch: "
        f"found {name or '<unset>'} <{email or '<unset>'}>; "
        f"expected {expected} or an authorized private identity fingerprint"
    ]


# The core main() resolves check_identity from its own module globals.
_core.check_identity = check_identity


def main() -> int:
    return _core.main()


if __name__ == "__main__":
    raise SystemExit(main())
