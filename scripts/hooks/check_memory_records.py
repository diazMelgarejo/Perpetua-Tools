#!/usr/bin/env python3
"""Validate staged .agent/memory/** records (PT Agentic-Stack memory).

Checks, in order of what actually failed in the 848da335af02 incident:
1. Strict JSON (duplicate keys and NaN/Infinity are errors, not warnings).
2. JSONL line strictness for episodic/semantic files.
3. Candidate schema: required fields (id, key, name, claim, status,
   decisions[]); known top-level fields only.
4. Id derivation: id == sha256(claim).hexdigest()[:12] (catches ids minted
   outside the memory tooling).
5. Normalized-claim duplicate detection against the tracked corpus (the
   validate.py heuristic, applied at the hook).
6. Supersedes/links must reference records that exist in the tracked
   candidates/graduated set (no dangling supersession).

Exit 1 lists every failing staged file. Reference cards and working
narratives (.md) are not schema-validated (repo_hygiene covers their
content). This is PT's own memory discipline per the OSSF-1 saga boundary
-- not a copy of the orama OSSF-1 hook, which gates SKILL.md files only.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

MEMORY_ROOT = Path(".agent/memory")


def _no_duplicate_pairs(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate JSON key: {key}")
        seen[key] = value
    return seen


def _reject_constant(name):
    raise ValueError(f"non-finite JSON constant: {name}")


def strict_json(text: str, origin: str):
    try:
        return json.loads(
            text,
            object_pairs_hook=_no_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except ValueError as exc:
        raise ValueError(f"{origin}: invalid JSON: {exc}") from exc


def staged_files() -> list[Path]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    return [Path(p) for p in out if p.startswith(str(MEMORY_ROOT)) and (p.endswith(".json") or p.endswith(".jsonl"))]


def tracked_candidate_records() -> dict[str, dict]:
    out = subprocess.run(
        ["git", "ls-files", str(MEMORY_ROOT / "candidates")],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    records: dict[str, dict] = {}
    for line in out:
        data = json.loads(Path(line).read_text(encoding="utf-8-sig"))
        if isinstance(data, dict) and data.get("id"):
            records[data["id"]] = data
    return records


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (text or "").lower())).strip()


def validate_candidate(path: Path, problems: list[str], tracked: dict[str, dict], tracked_claims: set[str]) -> None:
    data = strict_json(path.read_text(encoding="utf-8-sig"), str(path))
    if not isinstance(data, dict):
        problems.append(f"{path}: top-level JSON must be an object")
        return
    required = {"id", "key", "name", "claim", "status", "decisions"}
    missing = sorted(required - data.keys())
    if missing:
        problems.append(f"{path}: missing required fields: {missing}")
        return
    derived = hashlib.sha256(data["claim"].encode("utf-8")).hexdigest()[:12]
    if data["id"] != derived:
        problems.append(
            f"{path}: id {data['id']!r} is not the memory-tooling derivation of "
            f"the claim (expected {derived!r}) -- ids must be minted by learn.py,"
            f" never hand-written"
        )
    if data.get("status") not in {"staged", "accepted", "graduated", "rejected"}:
        problems.append(f"{path}: unknown status {data.get('status')!r}")
    if normalized(data["claim"]) in tracked_claims and data["id"] not in tracked:
        problems.append(
            f"{path}: normalized claim duplicates an already-tracked graduated "
            f"record -- supersede via a link to the existing record, never duplicate"
        )
    supersedes = data.get("supersedes")
    if supersedes and supersedes.replace("lesson_", "") not in tracked:
        problems.append(
            f"{path}: supersedes target {supersedes!r} does not exist in the "
            f"tracked graduated corpus"
        )


def main() -> int:
    paths = staged_files()
    if not paths:
        return 0
    problems: list[str] = []
    try:
        tracked = tracked_candidate_records()
    except ValueError as exc:
        problems.append(f"tracked corpus: {exc}")
        tracked = {}
    tracked_claims = {
        normalized(record["claim"]) for record in tracked.values() if record.get("claim")
    }
    for path in paths:
        if path.suffix == ".jsonl":
            for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
                if line.strip():
                    try:
                        strict_json(line, f"{path}:{number}")
                    except ValueError as exc:
                        problems.append(str(exc))
        elif path.suffix == ".json" and "candidates" in path.parts:
            try:
                validate_candidate(path, problems, tracked, tracked_claims)
            except ValueError as exc:
                problems.append(str(exc))
        elif path.suffix == ".json":
            try:
                strict_json(path.read_text(encoding="utf-8-sig"), str(path))
            except ValueError as exc:
                problems.append(str(exc))
    for problem in problems:
        print(f"MEMORY-RECORDS: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
