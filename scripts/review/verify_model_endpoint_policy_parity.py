#!/usr/bin/env python3
"""Fail when cross-repo shared endpoint-policy modules drift between
orama-system and Perpetua-Tools.

Two separately-owned shared modules are checked, each with its own
sync-drift risk:
  - model_endpoint_url.py: SSRF host-classification (ModelEndpointPolicyError)
  - endpoint_policy_core.py: transport-identity reconstruction
    (parse_transport_identity/build_transport_url), Perpetua-Tools canonical
"""
from __future__ import annotations

import ast
import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class _FileSpec:
    filename: str
    policy_functions: tuple[str, ...]


FILES_TO_CHECK: tuple[_FileSpec, ...] = (
    _FileSpec(
        "model_endpoint_url.py",
        ("_host_allowed", "validate_model_endpoint_url", "parse_model_endpoint_list"),
    ),
    _FileSpec(
        "endpoint_policy_core.py",
        ("parse_transport_identity", "build_transport_url"),
    ),
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_UTILS_DIR = _REPO_ROOT / "src" / "utils"


def _extract_policy_source(path: Path, policy_functions: tuple[str, ...]) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    chunks: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in policy_functions:
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body = node.body[1:]
            ast.fix_missing_locations(node)
            chunks.append(ast.dump(node))
    missing = sorted(set(policy_functions) - {n.name for n in tree.body if isinstance(n, ast.FunctionDef)})
    if missing:
        raise SystemExit(f"{path}: missing policy functions: {', '.join(missing)}")
    return "\n\n".join(chunks)


def _sibling_utils_dir() -> Path | None:
    env = os.getenv("ORAMA_SYSTEM_ROOT") or os.getenv("ORAMA_REPO_ROOT")
    if env:
        return Path(env) / "src" / "utils"
    sibling = _REPO_ROOT.parent / "orama-system" / "src" / "utils"
    if sibling.is_dir():
        return sibling
    return None


def _check_one(spec: _FileSpec, local_dir: Path, peer_dir: Path) -> bool:
    local_path = local_dir / spec.filename
    peer_path = peer_dir / spec.filename
    if not local_path.is_file():
        print(f"model-endpoint-policy-parity: local file missing: {local_path}", file=sys.stderr)
        return False
    if not peer_path.is_file():
        print(f"model-endpoint-policy-parity: peer file missing: {peer_path}", file=sys.stderr)
        return False

    local_src = _extract_policy_source(local_path, spec.policy_functions)
    peer_src = _extract_policy_source(peer_path, spec.policy_functions)
    if local_src != peer_src:
        print(f"model-endpoint-policy-parity: FAIL — {spec.filename} policy functions diverged", file=sys.stderr)
        print(f"  local: {local_path}", file=sys.stderr)
        print(f"  peer:  {peer_path}", file=sys.stderr)
        print(
            "  hint: on stacked cross-repo PRs, CI must checkout the sibling at the same "
            "PR branch (not main); after merge both repos should match on main.",
            file=sys.stderr,
        )
        import difflib

        for line in difflib.unified_diff(
            peer_src.splitlines(),
            local_src.splitlines(),
            fromfile=str(peer_path),
            tofile=str(local_path),
            lineterm="",
        ):
            print(line, file=sys.stderr)
        return False

    print(f"model-endpoint-policy-parity: PASS ({spec.filename})")
    return True


def main() -> int:
    peer_dir = _sibling_utils_dir()
    if peer_dir is None:
        print("model-endpoint-policy-parity: skip (orama-system sibling not available)")
        return 0

    ok = True
    for spec in FILES_TO_CHECK:
        if not _check_one(spec, _LOCAL_UTILS_DIR, peer_dir):
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
