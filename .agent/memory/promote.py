"""Cluster, extract, and stage memory candidates."""
import datetime
import hashlib
import json
import os

from cluster import content_cluster, extract_pattern
from path_hygiene import sanitize_json_strings
from validate import check_exact_duplicate, extract_lesson_lines


def cluster_and_extract(entries, threshold=0.3):
    clusters = content_cluster(entries, threshold=threshold)
    return {pattern["name"]: pattern for pattern in (extract_pattern(c) for c in clusters)}


def _slug(pattern_or_key):
    if isinstance(pattern_or_key, dict) and pattern_or_key.get("id"):
        return pattern_or_key["id"]
    return hashlib.md5(str(pattern_or_key).encode()).hexdigest()[:12]


def _find_prior(slug, candidates_dir):
    staged_path = os.path.join(candidates_dir, f"{slug}.json")
    if os.path.isfile(staged_path):
        try:
            with open(staged_path, encoding="utf-8") as stream:
                return json.load(stream), "staged"
        except (OSError, json.JSONDecodeError):
            pass
    for subdir in ("rejected", "graduated"):
        path = os.path.join(candidates_dir, subdir, f"{slug}.json")
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as stream:
                    return json.load(stream), subdir
            except (OSError, json.JSONDecodeError):
                pass
    return {}, None


def _persist_candidate(candidate, path):
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(sanitize_json_strings(candidate), stream, indent=2)


def write_candidates(patterns, candidates_dir):
    if not patterns:
        return 0
    os.makedirs(candidates_dir, exist_ok=True)
    lessons_path = os.path.join(os.path.dirname(candidates_dir), "semantic", "LESSONS.md")
    lessons_text = ""
    if os.path.exists(lessons_path):
        try:
            with open(lessons_path, encoding="utf-8") as stream:
                lessons_text = stream.read()
        except OSError:
            pass
    current_terminal_lessons = set(extract_lesson_lines(lessons_text))
    written = 0

    for key, pattern in patterns.items():
        claim = (pattern.get("claim") or "").strip()
        if not claim or (lessons_text and check_exact_duplicate(claim, lessons_text)):
            continue
        slug = _slug(pattern)
        previous, previous_location = _find_prior(slug, candidates_dir)
        if previous_location == "graduated" and previous.get("status") != "provisional":
            continue

        if previous_location in ("rejected", "graduated"):
            last = (previous.get("decisions") or [])[-1] if previous.get("decisions") else {}
            previous_evidence = set(last.get("evidence_snapshot", []))
            new_evidence = set(pattern.get("evidence_ids", []))
            evidence_changed = bool(new_evidence - previous_evidence)
            stamped_duplicates = last.get("duplicate_claims") or []
            blocker_still_present = (
                any(item in current_terminal_lessons for item in stamped_duplicates)
                if stamped_duplicates
                else True
            )
            if not evidence_changed and blocker_still_present:
                continue

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        decisions = list(previous.get("decisions", []))
        decisions.append({"ts": now, "action": "staged", "reviewer": "auto_dream"})
        candidate = {
            "id": slug,
            "key": key,
            "name": pattern.get("name", key),
            "claim": claim,
            "conditions": pattern.get("conditions", []),
            "evidence_ids": pattern.get("evidence_ids", []),
            "cluster_size": pattern.get("cluster_size", 1),
            "canonical_salience": pattern.get("canonical_salience", 0.0),
            "staged_at": previous.get("staged_at") or now,
            "status": "staged",
            "decisions": decisions,
            "rejection_count": previous.get("rejection_count", 0),
        }
        staged_path = os.path.join(candidates_dir, f"{slug}.json")
        _persist_candidate(candidate, staged_path)

        if previous_location in ("rejected", "graduated"):
            previous_path = os.path.join(
                candidates_dir, previous_location, f"{slug}.json"
            )
            try:
                os.remove(previous_path)
            except OSError:
                try:
                    os.remove(staged_path)
                except OSError:
                    pass
                raise
        written += 1
    return written
