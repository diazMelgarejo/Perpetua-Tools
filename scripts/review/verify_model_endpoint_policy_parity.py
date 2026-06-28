#!/usr/bin/env python3
"""Fail when cross-repo model endpoint policy drifts between orama-system and Perpetua-Tools."""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

_POLICY_FUNCTIONS = ("_host_allowed", "validate_model_endpoint_url", "parse_model_endpoint_list")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_POLICY = _REPO_ROOT / "src" / "utils" / "model_endpoint_url.py"


def _extract_policy_source(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    chunks: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in _POLICY_FUNCTIONS:
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body = node.body[1:]
            ast.fix_missing_locations(node)
            chunks.append(ast.unparse(node))
    missing = sorted(set(_POLICY_FUNCTIONS) - {n.name for n in tree.body if isinstance(n, ast.FunctionDef)})
    if missing:
        raise SystemExit(f"{path}: missing policy functions: {', '.join(missing)}")
    return "\n\n".join(chunks)


def _sibling_policy_path() -> Path | None:
    env = os.getenv("ORAMA_SYSTEM_ROOT") or os.getenv("ORAMA_REPO_ROOT")
    if env:
        return Path(env) / "src" / "utils" / "model_endpoint_url.py"
    sibling = _REPO_ROOT.parent / "orama-system" / "src" / "utils" / "model_endpoint_url.py"
    if sibling.is_file():
        return sibling
    return None


def main() -> int:
    if not _LOCAL_POLICY.is_file():
        print(f"model-endpoint-policy-parity: local policy missing: {_LOCAL_POLICY}", file=sys.stderr)
        return 1

    peer = _sibling_policy_path()
    if peer is None:
        print("model-endpoint-policy-parity: skip (orama-system sibling not available)")
        return 0

    local_src = _extract_policy_source(_LOCAL_POLICY)
    peer_src = _extract_policy_source(peer)
    if local_src != peer_src:
        print("model-endpoint-policy-parity: FAIL — policy functions diverged", file=sys.stderr)
        print(f"  local: {_LOCAL_POLICY}", file=sys.stderr)
        print(f"  peer:  {peer}", file=sys.stderr)
        print(
            "  hint: on stacked cross-repo PRs, CI must checkout the sibling at the same "
            "PR branch (not main); after merge both repos should match on main.",
            file=sys.stderr,
        )
        import difflib

        for line in difflib.unified_diff(
            peer_src.splitlines(),
            local_src.splitlines(),
            fromfile=str(peer),
            tofile=str(_LOCAL_POLICY),
            lineterm="",
        ):
            print(line, file=sys.stderr)
        return 1

    print("model-endpoint-policy-parity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
