"""Runs after every action. Appends a structured entry to episodic memory."""
import datetime
import os
import sys

from ._episodic_io import append_jsonl
from ._provenance import build_source

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REPO_ROOT = os.path.abspath(os.path.join(ROOT, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "memory"))
sys.path.insert(0, REPO_ROOT)

from orchestrator.redaction import redact_text  # noqa: E402
from path_hygiene import sanitize_tracked_path_leaks  # noqa: E402

EPISODIC = os.path.join(ROOT, "memory/episodic/AGENT_LEARNINGS.jsonl")


def _safe_text(value, limit):
    """Normalize, truncate, sanitize paths, then redact secrets before storage."""
    text = str(value)[:limit]
    return redact_text(sanitize_tracked_path_leaks(text))


def log_execution(skill_name, action, result, success, reflection="",
                  importance=5, confidence=0.5, evidence_ids=None,
                  pain_score=None):
    """Log a structured, persistence-safe episodic entry."""
    if pain_score is None:
        pain_score = 2 if success else 7
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "skill": skill_name,
        "action": _safe_text(action, 200),
        "result": "success" if success else "failure",
        "detail": _safe_text(result, 500),
        "pain_score": pain_score,
        "importance": importance,
        "reflection": _safe_text(reflection, 500),
        "confidence": confidence,
        "source": build_source(skill_name),
        "evidence_ids": list(evidence_ids) if evidence_ids else [],
    }
    return append_jsonl(EPISODIC, entry)
