"""Candidate lifecycle and append-only decision log."""
import datetime
import hashlib
import json
import logging
import os
import re

from path_hygiene import (
    REVIEW_QUEUE_DYNAMIC_MARKER,
    sanitize_json_strings,
    sanitize_tracked_path_leaks,
)

LOGGER = logging.getLogger(__name__)
_REVIEW_QUEUE_MARKER_LINE = re.compile(
    rf"^{re.escape(REVIEW_QUEUE_DYNAMIC_MARKER)}\s*$", re.MULTILINE
)
_CANDIDATE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _now():
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _validate_candidate_id(candidate_id):
    """Reject IDs containing path separators or unsupported characters."""
    if not isinstance(candidate_id, str) or not _CANDIDATE_ID.fullmatch(candidate_id):
        raise ValueError(f"invalid candidate id: {candidate_id!r}")
    return candidate_id


def _candidate_path(candidates_dir, candidate_id, lifecycle=None):
    """Build a contained candidate path, rejecting invalid or escaping IDs."""
    candidate_id = _validate_candidate_id(candidate_id)
    base = os.path.abspath(candidates_dir)
    if lifecycle:
        base = os.path.join(base, lifecycle)
    path = os.path.abspath(os.path.join(base, f"{candidate_id}.json"))
    if os.path.commonpath((base, path)) != base:
        raise ValueError(f"candidate path escapes candidates directory: {candidate_id!r}")
    return path


def _touch(candidate, action, reviewer, notes="", **fields):
    """Append a timestamped review decision to the candidate in memory."""
    candidate.setdefault("decisions", []).append({
        "ts": _now(),
        "action": action,
        "reviewer": reviewer,
        "notes": notes,
        **fields,
    })


def _lessons_sha(candidates_dir):
    """Return a short hash of rendered lessons, or an empty string if unavailable."""
    lessons_path = os.path.join(
        os.path.dirname(candidates_dir), "semantic", "LESSONS.md"
    )
    if not os.path.exists(lessons_path):
        return ""
    try:
        with open(lessons_path, "rb") as stream:
            return hashlib.sha256(stream.read()).hexdigest()[:12]
    except OSError:
        return ""


def _stamp_evidence_and_lessons(candidate, candidates_dir):
    """Attach the candidate's evidence and rendered lesson hash to its last decision."""
    if not candidate.get("decisions"):
        return
    last = candidate["decisions"][-1]
    last["evidence_snapshot"] = list(candidate.get("evidence_ids", []))
    last["lessons_sha"] = _lessons_sha(candidates_dir)


def load_candidate(path):
    """Read a candidate JSON file, propagating file and decoding errors."""
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def save_candidate(candidate, path):
    """Sanitize candidate strings and write a formatted JSON snapshot."""
    sanitized = sanitize_json_strings(candidate)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(sanitized, stream, indent=2)


def _move_candidate(candidate, source, destination):
    """Persist destination first; remove it again if source cleanup fails."""
    save_candidate(candidate, destination)
    try:
        os.remove(source)
    except OSError:
        try:
            os.remove(destination)
        except OSError:
            LOGGER.exception(
                "candidate rollback failed after source cleanup error: %s", destination
            )
        raise


def stage_candidate(candidate_path, reviewer="auto_dream"):
    """Record a staging decision in an existing candidate file."""
    candidate = load_candidate(candidate_path)
    candidate.setdefault("status", "staged")
    _touch(candidate, "staged", reviewer)
    save_candidate(candidate, candidate_path)


def _default_queue_path(candidates_dir):
    """Locate the working review queue beside the candidate directory."""
    return os.path.join(os.path.dirname(candidates_dir), "working", "REVIEW_QUEUE.md")


def _refresh_queue(candidates_dir):
    """Refresh the derived review queue, logging recoverable read or write failures."""
    try:
        write_review_queue_summary(candidates_dir, _default_queue_path(candidates_dir))
    except (OSError, ValueError, json.JSONDecodeError):
        LOGGER.warning(
            "review queue refresh failed for %s",
            candidates_dir,
            exc_info=True,
        )


def mark_graduated(candidate_id, reviewer, rationale, candidates_dir,
                    provisional=False, supersedes=None):
    """Move and return a reviewed candidate, recording its superseded lesson ID.

    ``supersedes`` is the semantic decision's ID or None for no known link.
    A missing staged candidate raises FileNotFoundError; the derived review queue
    is refreshed after the candidate moves.
    """
    source = _candidate_path(candidates_dir, candidate_id)
    if not os.path.exists(source):
        raise FileNotFoundError(f"candidate not found: {candidate_id}")
    candidate = load_candidate(source)
    candidate["status"] = "provisional" if provisional else "accepted"
    candidate["accepted_at"] = _now()
    candidate["reviewer"] = reviewer
    candidate["rationale"] = rationale
    candidate["supersedes"] = supersedes
    _touch(candidate, "graduated", reviewer, notes=rationale,
           provisional=provisional)
    _stamp_evidence_and_lessons(candidate, candidates_dir)
    destination_dir = os.path.join(candidates_dir, "graduated")
    os.makedirs(destination_dir, exist_ok=True)
    destination = _candidate_path(candidates_dir, candidate_id, "graduated")
    _move_candidate(candidate, source, destination)
    _refresh_queue(candidates_dir)
    return candidate


def mark_rejected(candidate_id, reviewer, reason, candidates_dir, **extra_stamp):
    """Record a rejection, move the candidate, and refresh the derived queue."""
    source = _candidate_path(candidates_dir, candidate_id)
    if not os.path.exists(source):
        raise FileNotFoundError(f"candidate not found: {candidate_id}")
    candidate = load_candidate(source)
    candidate["status"] = "rejected"
    candidate["rejection_count"] = candidate.get("rejection_count", 0) + 1
    _touch(candidate, "rejected", reviewer, notes=reason, **extra_stamp)
    _stamp_evidence_and_lessons(candidate, candidates_dir)
    destination_dir = os.path.join(candidates_dir, "rejected")
    os.makedirs(destination_dir, exist_ok=True)
    destination = _candidate_path(candidates_dir, candidate_id, "rejected")
    _move_candidate(candidate, source, destination)
    _refresh_queue(candidates_dir)
    return candidate


def mark_reopened(candidate_id, reviewer, candidates_dir):
    """Move a rejected candidate back to staging with a reopening decision."""
    source = _candidate_path(candidates_dir, candidate_id, "rejected")
    if not os.path.exists(source):
        raise FileNotFoundError(f"rejected candidate not found: {candidate_id}")
    candidate = load_candidate(source)
    candidate["status"] = "staged"
    _touch(candidate, "reopened", reviewer)
    destination = _candidate_path(candidates_dir, candidate_id)
    _move_candidate(candidate, source, destination)
    _refresh_queue(candidates_dir)
    return candidate


def _age_factor(staged_at):
    """Scale priority with age, defaulting to one for invalid timestamps."""
    try:
        staged = datetime.datetime.fromisoformat(staged_at)
    except (ValueError, TypeError):
        return 1.0
    if staged.tzinfo is None:
        staged = staged.replace(tzinfo=datetime.timezone.utc)
    age_days = (datetime.datetime.now(datetime.timezone.utc) - staged).days
    return 1.0 + min(1.0, age_days / 14.0)


def candidate_priority(candidate):
    """Rank a candidate using cluster size, salience, and time in staging."""
    return (
        max(1, candidate.get("cluster_size", 1))
        * max(0.1, candidate.get("canonical_salience", 0.1))
        * _age_factor(candidate.get("staged_at", ""))
    )


def list_candidates(candidates_dir, status="staged", sort_by="priority"):
    """Read valid candidate files for a lifecycle state and sort the results.

    Missing directories return an empty list; unreadable or invalid JSON files
    are skipped.
    """
    search_dir = candidates_dir if status == "staged" else os.path.join(candidates_dir, status)
    if not os.path.isdir(search_dir):
        return []
    candidates = []
    for filename in os.listdir(search_dir):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(search_dir, filename)
        if not os.path.isfile(path):
            continue
        try:
            candidates.append(load_candidate(path))
        except (OSError, json.JSONDecodeError):
            continue
    if sort_by == "priority":
        candidates.sort(key=candidate_priority, reverse=True)
    elif sort_by == "age":
        candidates.sort(key=lambda candidate: candidate.get("staged_at", ""))
    return candidates


def _read_review_queue_preamble(summary_path):
    """Preserve the static queue preamble ahead of generated candidate details."""
    if not os.path.exists(summary_path):
        return "# Review Queue\n\n"
    with open(summary_path, encoding="utf-8") as stream:
        text = stream.read()
    marker_lines = list(_REVIEW_QUEUE_MARKER_LINE.finditer(text))
    if marker_lines:
        return text[: marker_lines[-1].start()].rstrip() + "\n\n"
    for separator in (
        "\n\n**Pending:**",
        "\n\n_No pending candidates._",
        "\n## Priority order",
    ):
        if separator in text:
            return text.split(separator)[0].rstrip() + "\n\n"
    return text if text.startswith("# Review Queue") else "# Review Queue\n\n"


def write_review_queue_summary(candidates_dir, summary_path):
    """Regenerate the queue projection and return the number of staged candidates."""
    pending = list_candidates(candidates_dir, status="staged")
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    preamble = _read_review_queue_preamble(summary_path)
    if not pending:
        with open(summary_path, "w", encoding="utf-8") as stream:
            stream.write(
                f"{preamble}{REVIEW_QUEUE_DYNAMIC_MARKER}\n\n"
                "_No pending candidates._\n"
            )
        return 0
    staged_ats = [candidate.get("staged_at", "") for candidate in pending if candidate.get("staged_at")]
    oldest = min(staged_ats) if staged_ats else ""
    lines = [REVIEW_QUEUE_DYNAMIC_MARKER, "", f"**Pending:** {len(pending)}"]
    if oldest:
        lines.append(f"**Oldest staged:** {oldest}")
    lines.extend([
        "",
        "Run `python .agent/tools/list_candidates.py` for detail, then:",
        "- `python .agent/tools/graduate.py <id> --rationale \"...\"` to accept",
        "- `python .agent/tools/reject.py <id> --reason \"...\"` to reject",
        "- Review in a batch so cross-candidate contradictions are caught.",
        "",
        "## Priority order (top 10)",
        "",
    ])
    for candidate in pending[:10]:
        priority = candidate_priority(candidate)
        claim = sanitize_tracked_path_leaks((candidate.get("claim") or "")[:80])
        lines.append(
            f"- **{candidate.get('id')}** (priority={priority:.2f}, "
            f"size={candidate.get('cluster_size', '?')}, "
            f"rejections={candidate.get('rejection_count', 0)}) — {claim}"
        )
    with open(summary_path, "w", encoding="utf-8") as stream:
        stream.write(preamble + "\n".join(lines) + "\n")
    return len(pending)
