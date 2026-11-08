"""Append an audited correction snapshot; never rewrite a lesson or candidate.

Corrections are provisional or retracted, never accepted. The existing semantic
lock serializes read/check/append on POSIX; its documented Windows single-writer
limit still applies. Immutable candidate snapshots retain their original claims.
Malformed or torn historical JSONL refuses correction. Recovering such bytes
needs a separate preservation procedure; this command never skips or truncates them.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "memory"))
sys.path.insert(0, str(BASE / "harness/hooks"))

from _episodic_io import append_jsonl, episodic_lock
from path_hygiene import sanitize_tracked_path_leaks
from render_lessons import _append_lesson_unlocked, _locked_jsonl, render_lessons


def _audit(path: Path, action: str, detail: str, reviewer: str, *, require_existing: bool = False) -> dict[str, Any]:
    """Reuse a completed audit append if semantic publication previously failed."""
    match = None
    with episodic_lock(str(path), exclusive=False):
        if path.exists():
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if row.get("action") == action:
                        match = row
    if match is not None:
        return match
    if require_existing:
        raise ValueError("correction audit record is missing")
    timestamp = datetime.now(timezone.utc).isoformat()
    return append_jsonl(str(path), {
        "timestamp": timestamp, "skill": "perpetua-memory", "action": action,
        "result": "success", "detail": detail, "importance": 8, "pain_score": 2,
        "reflection": "Correction is not acceptance or platform qualification.",
        "confidence": 0.9, "evidence_ids": [timestamp],
        "source": {"skill": "correct_lesson", "profile": "review-correction",
                   "run_id": action, "reviewer": reviewer},
    })


def correct_lesson(
    lesson_id: str, claim: str, rationale: str, reviewer: str = "host-agent", *,
    semantic_dir: Path = BASE / "memory/semantic",
    episodic_path: Path = BASE / "memory/episodic/AGENT_LEARNINGS.jsonl",
    status: str = "provisional",
) -> dict[str, Any]:
    """Append a latest-by-ID correction plus evidence, preserving every prior byte.

    The ID still identifies the original lesson topic. Explicit correction
    metadata distinguishes the new claim from its historical candidate snapshot.
    Retraction withdraws guidance; it is not authority to resurrect a retired ID.
    """
    claim = sanitize_tracked_path_leaks(claim.strip())
    rationale = sanitize_tracked_path_leaks(rationale.strip())
    reviewer = sanitize_tracked_path_leaks(reviewer.strip())
    if len(claim) < 20 or not rationale or not reviewer:
        raise ValueError("claim (at least 20 characters), rationale and reviewer are required")
    if status not in {"provisional", "retracted"}:
        raise ValueError("correction status must be provisional or retracted")
    with _locked_jsonl(str(semantic_dir / "lessons.jsonl")) as stream:
        stream.seek(0)
        latest = None
        for line in stream:
            if line.strip():
                row = json.loads(line)
                if row.get("id") == lesson_id:
                    latest = row
        if latest is None:
            raise ValueError(f"lesson not found: {lesson_id}")
        identical = (latest.get("claim") == claim and latest.get("status") == status
                     and latest.get("rationale") == rationale and latest.get("reviewer") == reviewer
                     and bool(latest.get("correction")))
        if identical:
            _audit(episodic_path, latest["correction"]["action"], "", reviewer, require_existing=True)
            updated = latest
        else:
            if latest.get("status") not in {"accepted", "provisional", "legacy"}:
                raise ValueError(f"lesson {lesson_id} is not correctable from {latest.get('status')}")
            if latest.get("status") == "accepted" and latest.get("supersedes"):
                raise ValueError("accepted supersession lineage requires separate review before correction")
            original_digest = hashlib.sha256(json.dumps(latest, sort_keys=True).encode()).hexdigest()
            intent = json.dumps([lesson_id, original_digest, claim, status, rationale, reviewer])
            action = "lesson-correction:" + hashlib.sha256(intent.encode()).hexdigest()
            audit = _audit(episodic_path, action,
                           f"{lesson_id}: {claim} Correction: {rationale}", reviewer)
            updated = {**latest, "claim": claim, "status": status, "rationale": rationale,
                       "reviewer": reviewer,
                       "evidence_ids": [*latest.get("evidence_ids", []), audit["timestamp"]],
                       "correction": {"previous_record_sha256": original_digest,
                                      "at": audit["timestamp"], "action": action}}
            _append_lesson_unlocked(stream, updated)
    # Rendering takes the same semantic lock, so it must be outside that scope.
    render_lessons(str(semantic_dir))
    return updated


def main() -> None:
    """Apply an explicit review correction without modifying old rows or candidates."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lesson_id")
    parser.add_argument("--claim", required=True)
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--reviewer", default="host-agent")
    parser.add_argument("--status", choices=("provisional", "retracted"), default="provisional")
    args = parser.parse_args()
    result = correct_lesson(args.lesson_id, args.claim, args.rationale, args.reviewer, status=args.status)
    print(f"{result['id']}: appended/verified {result['status']} correction and rendered lessons")


if __name__ == "__main__":
    main()
