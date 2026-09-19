#!/usr/bin/env python3
"""Resolve the Orama ref paired with a PT endpoint-policy PR branch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_STACKS_PATH = _REPO_ROOT / "config" / "cross-repo-policy-stacks.json"


def resolve_orama_policy_ref(head_ref: str) -> str:
    """Return the declared Orama peer ref, or the same-named ref by default."""
    data = json.loads(_STACKS_PATH.read_text(encoding="utf-8"))
    refs = data.get("orama_system_refs", {})
    return str(refs.get(head_ref, head_ref))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("head_ref")
    args = parser.parse_args()
    print(resolve_orama_policy_ref(args.head_ref))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
