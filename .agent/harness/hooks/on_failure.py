"""Failures are learning. High pain score + rewrite flag after repeat offenses."""
import datetime
import json
import os
import sys

from ._episodic_io import append_jsonl
from ._provenance import build_source

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "memory"))
from path_hygiene import sanitize_json_strings  # noqa: E402

EPISODIC = os.path.join(ROOT, "memory/episodic/AGENT_LEARNINGS.jsonl")
FAILURE_THRESHOLD = 3
WINDOW_DAYS = 14


def _legacy_local_to_utc(ts):
    """Interpret legacy naive timestamps as local wall time, then normalize."""
    if ts.tzinfo is None:
        local_tz = datetime.datetime.now().astimezone().tzinfo
        ts = ts.replace(tzinfo=local_tz)
    return ts.astimezone(datetime.timezone.utc)


def _count_recent_failures(skill_name):
    if not os.path.exists(EPISODIC):
        return 0
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=WINDOW_DAYS)
    count = 0
    with open(EPISODIC, encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("skill") != skill_name or entry.get("result") != "failure":
                continue
            try:
                ts = _legacy_local_to_utc(datetime.datetime.fromisoformat(entry["timestamp"]))
                if ts > cutoff:
                    count += 1
            except (KeyError, TypeError, ValueError):
                continue
    return count


def on_failure(skill_name, action, error, context="", confidence=0.9,
               evidence_ids=None, importance=None, pain_score=None):
    if isinstance(error, Exception):
        reflection = (
            f"FAILURE in {skill_name}: {type(error).__name__}: "
            f"{str(error)[:200]}"
        )
    else:
        reflection = f"FAILURE in {skill_name}: {str(error)[:200]}"

    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "skill": skill_name,
        "action": action[:200],
        "result": "failure",
        "detail": str(error)[:500],
        "pain_score": pain_score if pain_score is not None else 8,
        "importance": importance if importance is not None else 7,
        "reflection": reflection,
        "context": context[:300],
        "confidence": confidence,
        "source": build_source(skill_name),
        "evidence_ids": list(evidence_ids) if evidence_ids else [],
    }
    recent = _count_recent_failures(skill_name) + 1
    if recent >= FAILURE_THRESHOLD:
        entry["reflection"] += (
            f" | THIS SKILL HAS FAILED {recent} TIMES IN {WINDOW_DAYS}d. "
            "Flag for rewrite."
        )
        entry["pain_score"] = 10
    return append_jsonl(EPISODIC, sanitize_json_strings(entry))
