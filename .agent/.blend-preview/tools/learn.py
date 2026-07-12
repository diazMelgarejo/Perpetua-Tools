#!/usr/bin/env python3
"""One-shot lesson teaching.

    python3 .agent/tools/learn.py "Always serialize timestamps in UTC" \
        --rationale "prior bugs from mixed local/UTC comparisons"

Stages a candidate and graduates it in a single command. Removes the
stage-then-graduate ceremony for the common case: you already know the
lesson, you just want the agent to know it too.

The candidate id comes from the shared `cluster.pattern_id` helper (same
algorithm auto-dream uses) so repeat calls are idempotent within the manual
path: same claim + same conditions → same id → safe retry. IDs will differ
from auto-dream's ids for the same claim because auto-dream infers
conditions from a cluster's common vocabulary, not from the claim alone;
that's intentional (different birth paths, different context).

If graduation fails (e.g., exact-duplicate heuristic reject), the staged
candidate file is removed so `show.py` / `REVIEW_QUEUE.md` don't show
orphaned dead-ends.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CANDIDATES = os.path.join(BASE, "memory/candidates")
sys.path.insert(0, os.path.join(BASE, "harness"))
sys.path.insert(0, os.path.join(BASE, "memory"))
from text import word_set  # noqa: E402
from cluster import pattern_id  # noqa: E402
from path_hygiene import sanitize_tracked_path_leaks  # noqa: E402


def _lesson_already_appended(cid):
    """Did graduate.py get as far as writing the lesson to lessons.jsonl?"""
    lessons_path = os.path.join(BASE, "memory/semantic/lessons.jsonl")
    if not os.path.exists(lessons_path):
        return False
    target = f"lesson_{cid}"
    try:
        with open(lessons_path, encoding="utf-8") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("id") == target:
                    return True
    except OSError:
        return False
    return False


def _load_existing_candidate(path, cid):
    """Return a valid staged candidate unchanged; reject corrupt collisions."""
    try:
        with open(path, encoding="utf-8") as stream:
            candidate = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"existing candidate is unreadable: {path}") from exc
    if candidate.get("id") != cid:
        raise RuntimeError(
            f"candidate path collision: expected id {cid}, found {candidate.get('id')!r}"
        )
    if not isinstance(candidate.get("decisions"), list) or not candidate.get("staged_at"):
        raise RuntimeError(f"existing candidate is missing lifecycle state: {path}")
    return candidate


def stage(claim, conditions, source="learn", importance=7):
    os.makedirs(CANDIDATES, exist_ok=True)
    cid = pattern_id(claim, conditions)
    path = os.path.join(CANDIDATES, f"{cid}.json")
    if os.path.exists(path):
        _load_existing_candidate(path, cid)
        return cid, path

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    candidate = {
        "id": cid,
        "key": f"manual_{cid[:6]}",
        "name": f"manual_{cid[:6]}",
        "claim": claim,
        "conditions": sorted(conditions),
        "evidence_ids": [now],
        "cluster_size": 1,
        "canonical_salience": 8.0,
        "staged_at": now,
        "status": "staged",
        "decisions": [{"ts": now, "action": "staged", "reviewer": source}],
        "rejection_count": 0,
    }
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(candidate, stream, indent=2)
        stream.write("\n")
    return cid, path


def main():
    parser = argparse.ArgumentParser(
        description="Teach the agent a lesson in one command."
    )
    parser.add_argument("claim", help="The lesson, phrased as a rule or principle.")
    parser.add_argument(
        "--rationale",
        default=None,
        help=(
            "Why this lesson holds. Recommended. If omitted, a timestamp-only "
            "rationale is used."
        ),
    )
    parser.add_argument(
        "--conditions",
        nargs="*",
        default=None,
        help="Optional trigger keywords. Inferred from claim words if omitted.",
    )
    parser.add_argument(
        "--provisional",
        action="store_true",
        help="Graduate as provisional (probationary) — safer for experimental rules.",
    )
    parser.add_argument(
        "--stage-only",
        action="store_true",
        help="Stage the candidate but don't auto-graduate.",
    )
    args = parser.parse_args()

    claim = sanitize_tracked_path_leaks(args.claim.strip())
    if len(claim) < 20:
        print(
            f"ERROR: claim too short ({len(claim)} chars, need >=20). "
            "Heuristic check would reject this.",
            file=sys.stderr,
        )
        sys.exit(2)

    conditions = args.conditions
    if conditions is None:
        conditions = sorted(word_set(claim))

    cid, path = stage(claim, conditions)
    print(f"staged candidate {cid}")
    print(f"  path: {path}")
    print(f"  conditions: {conditions}")

    if args.stage_only:
        print("\n(stopping here — run graduate.py to accept)")
        return

    rationale = sanitize_tracked_path_leaks(
        args.rationale
        or f"manual via learn.py at {datetime.datetime.now(datetime.timezone.utc).isoformat()}"
    )
    grad_args = [
        sys.executable,
        os.path.join(BASE, "tools", "graduate.py"),
        cid,
        "--rationale",
        rationale,
        "--reviewer",
        "learn.py",
    ]
    if args.provisional:
        grad_args.append("--provisional")
    result = subprocess.run(grad_args, capture_output=True, text=True)
    if result.returncode != 0:
        print(
            f"\nERROR: graduation failed (exit {result.returncode})",
            file=sys.stderr,
        )
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        lesson_written = _lesson_already_appended(cid)
        is_heuristic_reject = result.returncode == 2 and not lesson_written
        if os.path.isfile(path) and is_heuristic_reject:
            try:
                os.remove(path)
                print(f"(cleaned up orphaned candidate at {path})", file=sys.stderr)
            except OSError:
                pass
        elif lesson_written:
            print(
                f"(preserved staged file {path} — lesson_{cid} already in "
                "lessons.jsonl; re-run graduate.py to complete the move)",
                file=sys.stderr,
            )
        else:
            print(
                f"(preserved staged file {path} — graduation exited "
                f"{result.returncode}; inspect or re-run graduate.py)",
                file=sys.stderr,
            )
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
