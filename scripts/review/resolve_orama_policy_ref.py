#!/usr/bin/env python3
"""Resolve the Orama ref paired with a PT endpoint-policy PR branch."""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping


_REPO_ROOT = Path(__file__).resolve().parents[2]
_STACKS_PATH = _REPO_ROOT / "config" / "cross-repo-policy-stacks.json"
_DEFAULT_PEER_REPOSITORY = "diazMelgarejo/orama-system"


class OramaPeerResolution:
    """Checkout target plus whether the stack mapping is declared."""

    __slots__ = ("peer_ref", "declared", "source", "merged", "head_ref")

    def __init__(
        self,
        peer_ref: str,
        declared: bool,
        source: str,
        merged: bool,
        head_ref: str,
    ) -> None:
        self.peer_ref = peer_ref
        self.declared = declared
        self.source = source
        self.merged = merged
        self.head_ref = head_ref


def load_policy_stacks() -> dict[str, Any]:
    """Return the cross-repo policy-stack document."""
    return json.loads(_STACKS_PATH.read_text(encoding="utf-8"))


def normalize_head_ref(head_ref: str) -> str:
    """Strip CI quoting and refs/heads/ so JSON keys match GITHUB_HEAD_REF."""
    value = (head_ref or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    if value.startswith("refs/heads/"):
        value = value[len("refs/heads/") :]
    return value


def _stack_entry(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return {"peer_ref": raw, "peer_pull": None, "equivalents": []}
    if isinstance(raw, Mapping):
        peer_ref = str(raw.get("peer_ref") or "").strip()
        if not peer_ref:
            raise ValueError("orama stack entry is missing peer_ref")
        pull = raw.get("peer_pull")
        return {
            "peer_ref": peer_ref,
            "peer_pull": int(pull) if pull is not None else None,
            "peer_repository": str(
                raw.get("peer_repository") or _DEFAULT_PEER_REPOSITORY
            ),
            "equivalents": list(raw.get("equivalents") or []),
        }
    raise ValueError(f"unsupported orama stack entry type: {type(raw)!r}")


def fetch_pull_merged(repository: str, pull_number: int) -> bool:
    """Return True when the GitHub pull request is merged into its base."""
    url = f"https://api.github.com/repos/{repository}/pulls/{int(pull_number)}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "perpetua-tools-orama-policy-ref",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"failed to read merge state for {repository}#{pull_number}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected pull payload for {repository}#{pull_number}")
    return bool(payload.get("merged"))


def resolve_orama_policy_stack(
    head_ref: str,
    *,
    pull_merged: bool | None = None,
    merge_checker: Callable[[str, int], bool] | None = None,
) -> OramaPeerResolution:
    """Return the Orama checkout ref for a PT head, preferring main after merge."""
    normalized = normalize_head_ref(head_ref)
    refs = load_policy_stacks().get("orama_system_refs", {})
    entry = _stack_entry(refs.get(normalized))
    if entry is None:
        return OramaPeerResolution(
            peer_ref=normalized,
            declared=False,
            source="same-named-ref",
            merged=False,
            head_ref=normalized,
        )
    peer_pull = entry.get("peer_pull")
    if peer_pull is None:
        return OramaPeerResolution(
            peer_ref=str(entry["peer_ref"]),
            declared=True,
            source="declared-ref",
            merged=False,
            head_ref=normalized,
        )
    if pull_merged is None:
        checker = merge_checker or fetch_pull_merged
        pull_merged = bool(checker(str(entry["peer_repository"]), int(peer_pull)))
    if pull_merged:
        return OramaPeerResolution(
            peer_ref="main",
            declared=True,
            source="merged-main",
            merged=True,
            head_ref=normalized,
        )
    return OramaPeerResolution(
        peer_ref=str(entry["peer_ref"]),
        declared=True,
        source="open-pr",
        merged=False,
        head_ref=normalized,
    )


def resolve_orama_policy_ref(
    head_ref: str,
    *,
    pull_merged: bool | None = None,
    merge_checker: Callable[[str, int], bool] | None = None,
) -> str:
    """Return the declared Orama peer ref, or the same-named ref by default."""
    return resolve_orama_policy_stack(
        head_ref, pull_merged=pull_merged, merge_checker=merge_checker
    ).peer_ref


def write_github_output(resolution: OramaPeerResolution, output_path: str) -> None:
    """Append checkout outputs without wrapping the ref in extra quotes."""
    declared = "true" if resolution.declared else "false"
    merged = "true" if resolution.merged else "false"
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"peer_ref={resolution.peer_ref}\n")
        handle.write(f"declared={declared}\n")
        handle.write(f"source={resolution.source}\n")
        handle.write(f"merged={merged}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("head_ref")
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="Log resolution and append GITHUB_OUTPUT fields for Actions.",
    )
    args = parser.parse_args()
    resolution = resolve_orama_policy_stack(args.head_ref)
    if args.github_output:
        print(f"GITHUB_HEAD_REF={args.head_ref}")
        print(f"normalized_head_ref={resolution.head_ref}")
        print(f"peer_ref={resolution.peer_ref}")
        print(f"declared={str(resolution.declared).lower()}")
        print(f"source={resolution.source}")
        print(f"merged={str(resolution.merged).lower()}")
        output_path = os.environ.get("GITHUB_OUTPUT", "").strip()
        if output_path:
            write_github_output(resolution, output_path)
        return 0
    print(resolution.peer_ref)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
