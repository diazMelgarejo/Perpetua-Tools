"""Candidate lifecycle + decision log.

Each candidate JSON under memory/candidates/ carries:
  status:    staged | provisional | accepted | rejected | superseded
  decisions: append-only list of {ts, action, reviewer, notes, **fields}

Host-agent CLI tools call into this module to transition state. Rejection and
re-stage preserve full history so recurring candidates remain visible as churn.
"""
import datetime
import hashlib
import json
import logging
import os
import re

from path_hygiene import REVIEW_QUEUE_DYNAMIC_MARKER, sanitize_tracked_path_leaks

_LOG = logging.getLogger(__name__)
_REVIEW_QUEUE_MARKER_LINE = re.compile(
    rf"^{re.escape(REVIEW_QUEUE_DYNAMIC_MARKER)}\s*$",
    re.MULTILINE,
)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _touch(candidate, action, reviewer, notes="", **fields):
    decisions = candidate.setdefault("decisions", [])
    decisions.append({
        "ts": _now(),
        "action": action,
        "reviewer": reviewer,
        "notes": notes,
        **fields,
    })


def _lessons_sha(candidates_dir):
    """Short compatibility hash of current LESSONS.md, used to stamp decisions."""
    lessons_path = os.path.join(
        os.path.dirname(candidates_dir), "semantic", "LESSONS.md"
    )
    if not os.path.exists(lessons_path):
        return ""
    try:
        with open(lessons_path, "rb") as stream:
            return hashlib.md5(stream.read(), usedforsecurity=False).hexdigest()[:12]
    except OSError:
        return ""


def _stamp_evidence_and_lessons(candidate, candidates_dir):
    """Attach evidence + lessons snapshots to the most recent decision."""
    if not candidate.get("decisions"):
        return
    last = candidate["decisions"][-1]
    last["evidence_snapshot"] = list(candidate.get("evidence_ids", []))
    last["lessons_sha"] = _lessons_sha(candidates_dir)


def load_candidate(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def save_candidate(candidate, path):
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(candidate, stream, indent=2)
        stream.write("\n")


def stage_candidate(candidate_path, reviewer="auto_dream"):
    """Mark a freshly-written candidate as staged with an initial decision entry."""
    candidate = load_candidate(candidate_path)
    candidate.setdefault("status", "staged")
    _touch(candidate, "staged", reviewer)
    save_candidate(candidate, candidate_path)


def _default_queue_path(candidates_dir):
    memory_dir = os.path.dirname(candidates_dir)
    return os.path.join(memory_dir, "working", "REVIEW_QUEUE.md")


def _refresh_queue(candidates_dir):
    """Refresh the review queue without interrupting lifecycle transitions."""
    queue_path = _default_queue_path(candidates_dir)
    try:
        write_review_queue_summary(candidates_dir, queue_path)
    except Exception:
        _LOG.exception(
            "failed to refresh candidate review queue",
            extra={"candidates_dir": candidates_dir, "queue_path": queue_path},
        )


def _move_candidate(candidate, dst, src):
    """Write the candidate to its new lifecycle location, then remove the
    old one — with rollback if the removal fails.

    save_candidate() followed by a bare os.remove(src) leaves BOTH src and
    dst present if the remove step raises (permissions, disk, concurrent
    delete) after the write already succeeded — the candidate would then
    exist in two lifecycle locations simultaneously, and callers scanning
    by directory (staged/rejected/graduated) would double-count it. Roll
    the destination write back if src removal fails, so exactly one
    authoritative copy exists at all times.
    """
    save_candidate(candidate, dst)
    try:
        os.remove(src)
    except OSError:
        try:
            os.remove(dst)
        except OSError:
            pass
        raise


def mark_graduated(candidate_id, reviewer, rationale, candidates_dir,
                    provisional=False):
    """Move a staged candidate to candidates/graduated/ with an accept decision."""
    src = os.path.join(candidates_dir, f"{candidate_id}.json")
    if not os.path.exists(src):
        raise FileNotFoundError(f"candidate not found: {candidate_id}")
    candidate = load_candidate(src)
    candidate["status"] = "provisional" if provisional else "accepted"
    candidate["accepted_at"] = _now()
    candidate["reviewer"] = reviewer
    candidate["rationale"] = rationale
    _touch(
        candidate,
        "graduated",
        reviewer,
        notes=rationale,
        provisional=provisional,
    )
    _stamp_evidence_and_lessons(candidate, candidates_dir)

    graduated_dir = os.path.join(candidates_dir, "graduated")
    os.makedirs(graduated_dir, exist_ok=True)
    dst = os.path.join(graduated_dir, f"{candidate_id}.json")
    _move_candidate(candidate, dst, src)
    _refresh_queue(candidates_dir)
    return candidate


def mark_rejected(candidate_id, reviewer, reason, candidates_dir, **extra_stamp):
    """Move a staged candidate to candidates/rejected/ with a reject decision."""
    src = os.path.join(candidates_dir, f"{candidate_id}.json")
    if not os.path.exists(src):
        raise FileNotFoundError(f"candidate not found: {candidate_id}")
    candidate = load_candidate(src)
    candidate["status"] = "rejected"
    candidate["rejection_count"] = candidate.get("rejection_count", 0) + 1
    _touch(candidate, "rejected", reviewer, notes=reason, **extra_stamp)
    _stamp_evidence_and_lessons(candidate, candidates_dir)

    rejected_dir = os.path.join(candidates_dir, "rejected")
    os.makedirs(rejected_dir, exist_ok=True)
    dst = os.path.join(rejected_dir, f"{candidate_id}.json")
    _move_candidate(candidate, dst, src)
    _refresh_queue(candidates_dir)
    return candidate


def mark_reopened(candidate_id, reviewer, candidates_dir):
    """Move a rejected candidate back to the staged pool with history intact."""
    src = os.path.join(candidates_dir, "rejected", f"{candidate_id}.json")
    if not os.path.exists(src):
        raise FileNotFoundError(f"rejected candidate not found: {candidate_id}")
    candidate = load_candidate(src)
    candidate["status"] = "staged"
    _touch(candidate, "reopened", reviewer)

    dst = os.path.join(candidates_dir, f"{candidate_id}.json")
    _move_candidate(candidate, dst, src)
    _refresh_queue(candidates_dir)
    return candidate


def _age_factor(staged_at):
    """1.0 at stage time, grows to 2.0 for candidates about 14 days old."""
    try:
        staged = datetime.datetime.fromisoformat(staged_at)
    except (ValueError, TypeError):
        return 1.0
    if staged.tzinfo is None:
        staged = staged.replace(tzinfo=datetime.timezone.utc)
    age_days = (datetime.datetime.now(datetime.timezone.utc) - staged).days
    return 1.0 + min(1.0, age_days / 14.0)


def candidate_priority(candidate):
    """priority = cluster_size * canonical_salience * age_factor."""
    return (
        max(1, candidate.get("cluster_size", 1))
        * max(0.1, candidate.get("canonical_salience", 0.1))
        * _age_factor(candidate.get("staged_at", ""))
    )


def list_candidates(candidates_dir, status="staged", sort_by="priority"):
    """Return candidate dicts with the given status, sorted by the key."""
    search_dir = (
        candidates_dir
        if status == "staged"
        else os.path.join(candidates_dir, status)
    )
    if not os.path.isdir(search_dir):
        return []

    output = []
    for filename in os.listdir(search_dir):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(search_dir, filename)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as stream:
                output.append(json.load(stream))
        except (OSError, json.JSONDecodeError):
            continue

    if sort_by == "priority":
        output.sort(key=candidate_priority, reverse=True)
    elif sort_by == "age":
        output.sort(key=lambda candidate: candidate.get("staged_at", ""))
    return output


def _read_review_queue_preamble(summary_path: str) -> str:
    """Preserve curated preamble; only replace the auto-generated tail."""
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
    if text.startswith("# Review Queue"):
        return text
    return "# Review Queue\n\n"


def write_review_queue_summary(candidates_dir, summary_path):
    """Emit a compact REVIEW_QUEUE.md so the host agent sees the backlog."""
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

    staged_ats = [
        candidate.get("staged_at", "")
        for candidate in pending
        if candidate.get("staged_at")
    ]
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
        "## Priority order",
        "",
    ])
    for candidate in pending:
        lines.append(
            f"- `{candidate.get('id', '?')}` — "
            f"{sanitize_tracked_path_leaks(candidate.get('claim', ''))}"
        )

    with open(summary_path, "w", encoding="utf-8") as stream:
        stream.write(preamble + "\n".join(lines).rstrip() + "\n")
    return len(pending)
