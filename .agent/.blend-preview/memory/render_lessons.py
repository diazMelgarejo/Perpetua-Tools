"""Render semantic/LESSONS.md from append-only semantic/lessons.jsonl.

The JSONL stream is authoritative. Markdown below the sentinel is a derived view
and may be migrated only when it does not identify or duplicate a structured
lesson already present in JSONL.
"""
import datetime
import hashlib
import json
import os
import re
import warnings
from collections import defaultdict
from contextlib import contextmanager

LESSONS_JSONL = "lessons.jsonl"
LESSONS_MD = "LESSONS.md"
SENTINEL = "## Auto-promoted entries will be appended below"
_ID_ANNOTATION = re.compile(r"\bid=([^\s>]+)")

try:
    import fcntl

    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False
    warnings.warn(
        "fcntl unavailable; lessons.jsonl concurrent-write protection disabled",
        RuntimeWarning,
        stacklevel=2,
    )


@contextmanager
def _locked_jsonl(path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    stream = open(path, "a+", encoding="utf-8")
    try:
        if _HAS_FLOCK:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield stream
    finally:
        if _HAS_FLOCK:
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        stream.close()


def _append_lesson_unlocked(stream, lesson):
    stream.seek(0, os.SEEK_END)
    stream.write(json.dumps(lesson) + "\n")
    stream.flush()


def append_lesson(lesson, semantic_dir):
    os.makedirs(semantic_dir, exist_ok=True)
    path = os.path.join(semantic_dir, LESSONS_JSONL)
    with _locked_jsonl(path) as stream:
        _append_lesson_unlocked(stream, lesson)
    return path


def load_lessons(semantic_dir):
    path = os.path.join(semantic_dir, LESSONS_JSONL)
    if not os.path.exists(path):
        return []
    lessons = []
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                lessons.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return lessons


def _bullet_for(lesson, superseded_by):
    claim = lesson.get("claim", "")
    confidence = lesson.get("confidence", "?")
    status = lesson.get("status", "accepted")
    evidence = lesson.get("evidence_ids", [])
    lesson_id = lesson.get("id", "?")
    annotation = (
        f"status={status} confidence={confidence} "
        f"evidence={len(evidence)} id={lesson_id}"
    )
    successor = superseded_by.get(lesson_id)
    if successor:
        return f"- ~~{claim}~~  <!-- {annotation} superseded_by={successor} -->"
    if status == "retracted":
        return f"- ~~[RETRACTED] {claim}~~  <!-- {annotation} -->"
    if status == "provisional":
        return f"- [PROVISIONAL] {claim}  <!-- {annotation} -->"
    return f"- {claim}  <!-- {annotation} -->"


def _build_auto_section(lessons):
    superseded_by = {
        lesson.get("supersedes"): lesson.get("id")
        for lesson in lessons
        if lesson.get("status") == "accepted" and lesson.get("supersedes")
    }
    groups = defaultdict(list)
    for lesson in lessons:
        month = (lesson.get("accepted_at") or "")[:7] or "unknown"
        groups[month].append(lesson)
    lines = []
    for month in sorted(groups, reverse=True):
        lines.extend([f"### {month}", ""])
        lines.extend(_bullet_for(lesson, superseded_by) for lesson in groups[month])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n" if lines else ""


def _normalize_claim(claim):
    return " ".join((claim or "").strip().lower().split())


def _parse_legacy_bullet(line):
    stripped = line.strip()
    if not stripped.startswith("- ") or len(stripped) <= 2:
        return None
    comment = ""
    text = stripped[2:]
    if "<!--" in text:
        text, comment = text.split("<!--", 1)
    text = text.strip()
    if text.startswith("~~") and text.endswith("~~"):
        return None
    if text.startswith("[PROVISIONAL]"):
        text = text[len("[PROVISIONAL]") :].strip()
    if not text:
        return None
    match = _ID_ANNOTATION.search(comment)
    return text, (match.group(1) if match else None)


def migrate_legacy_bullets(semantic_dir):
    """Import only genuinely unstructured legacy bullets.

    A stale Markdown row carrying an ID already present in JSONL is ignored even
    when its displayed claim text is old. This guarantees the structured row
    wins and prevents a render from reverting current guidance.
    """
    md_path = os.path.join(semantic_dir, LESSONS_MD)
    if not os.path.exists(md_path):
        return 0
    with open(md_path, encoding="utf-8") as stream:
        content = stream.read()
    if SENTINEL not in content:
        return 0

    current = _dedupe_by_id(load_lessons(semantic_dir))
    existing_ids = {lesson.get("id") for lesson in current if lesson.get("id")}
    existing_claims = {
        _normalize_claim(lesson.get("claim"))
        for lesson in current
        if lesson.get("claim")
    }
    try:
        accepted_at = datetime.datetime.fromtimestamp(
            os.path.getmtime(md_path), tz=datetime.timezone.utc
        ).isoformat()
    except OSError:
        accepted_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    migrated = 0
    for line in content.split(SENTINEL, 1)[1].splitlines():
        parsed = _parse_legacy_bullet(line)
        if parsed is None:
            continue
        claim, annotated_id = parsed
        normalized = _normalize_claim(claim)
        if annotated_id in existing_ids or normalized in existing_claims:
            continue
        lesson_id = annotated_id or (
            "lesson_legacy_"
            + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
        )
        if lesson_id in existing_ids:
            continue
        lesson = {
            "id": lesson_id,
            "claim": claim,
            "conditions": [],
            "evidence_ids": [],
            "status": "legacy",
            "accepted_at": accepted_at,
            "reviewer": "render_lessons_migration",
            "rationale": "Imported from pre-restructure LESSONS.md bullets below sentinel",
            "cluster_size": 1,
            "canonical_salience": 5.0,
            "confidence": 0.7,
            "support_count": 0,
            "contradiction_count": 0,
            "supersedes": None,
            "source_candidate": None,
        }
        append_lesson(lesson, semantic_dir)
        existing_ids.add(lesson_id)
        existing_claims.add(normalized)
        migrated += 1
    return migrated


def _dedupe_by_id(lessons):
    """Keep the latest structured state per lesson ID."""
    latest = {}
    order = []
    for lesson in lessons:
        lesson_id = lesson.get("id") or f"_anon_{len(order)}"
        if lesson_id not in latest:
            order.append(lesson_id)
        latest[lesson_id] = lesson
    return [latest[lesson_id] for lesson_id in order]


def render_lessons(semantic_dir):
    migrate_legacy_bullets(semantic_dir)
    jsonl_path = os.path.join(semantic_dir, LESSONS_JSONL)
    md_path = os.path.join(semantic_dir, LESSONS_MD)
    os.makedirs(semantic_dir, exist_ok=True)

    with _locked_jsonl(jsonl_path):
        lessons = _dedupe_by_id(load_lessons(semantic_dir))
        auto_section = _build_auto_section(lessons)
        if os.path.exists(md_path):
            with open(md_path, encoding="utf-8") as stream:
                existing = stream.read()
            if SENTINEL in existing:
                prefix = existing.split(SENTINEL, 1)[0].rstrip()
                rendered = f"{prefix}\n\n{SENTINEL}\n\n{auto_section}"
            else:
                rendered = existing.rstrip() + f"\n\n{SENTINEL}\n\n{auto_section}"
        else:
            rendered = (
                "# Lessons\n\n"
                "> _Auto-managed below. Hand-curated preamble + seed lessons "
                "above the sentinel are preserved across renders._\n\n"
                f"{SENTINEL}\n\n{auto_section}"
            )
        tmp_path = md_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as stream:
            stream.write(rendered)
        os.replace(tmp_path, md_path)
    return md_path


def render_lessons_as_text(semantic_dir):
    with open(render_lessons(semantic_dir), encoding="utf-8") as stream:
        return stream.read()


if __name__ == "__main__":
    import sys

    semantic = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "semantic"
    )
    print(f"rendered: {render_lessons(semantic)}")
