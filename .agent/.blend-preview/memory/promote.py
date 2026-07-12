"""Cluster, extract, and stage memory candidates; graduation stays explicit."""
import datetime
import hashlib
import json
import os

from cluster import content_cluster, extract_pattern
from validate import check_exact_duplicate, extract_lesson_lines


def cluster_and_extract(entries, threshold=0.3):
    clusters = content_cluster(entries, threshold=threshold)
    return {pattern["name"]: pattern for pattern in map(extract_pattern, clusters)}


def _slug(pattern_or_key):
    if isinstance(pattern_or_key, dict) and pattern_or_key.get("id"):
        return pattern_or_key["id"]
    # Compatibility identifier only, not a security digest.
    return hashlib.md5(
        str(pattern_or_key).encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:12]


def _load_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def _find_prior(slug, candidates_dir):
    staged_path = os.path.join(candidates_dir, f"{slug}.json")
    if os.path.isfile(staged_path):
        try:
            return _load_json(staged_path), "staged"
        except (OSError, json.JSONDecodeError):
            pass
    for location in ("rejected", "graduated"):
        path = os.path.join(candidates_dir, location, f"{slug}.json")
        if os.path.isfile(path):
            try:
                return _load_json(path), location
            except (OSError, json.JSONDecodeError):
                pass
    return {}, None


def _write_staged_atomically(candidate, staged_path, prior_path=None):
    """Write staged state, then remove prior state; roll back on cleanup failure."""
    with open(staged_path, "w", encoding="utf-8") as stream:
        json.dump(candidate, stream, indent=2)
        stream.write("\n")
    if prior_path is None:
        return
    try:
        os.remove(prior_path)
    except OSError:
        try:
            os.remove(staged_path)
        except OSError:
            pass
        raise


def write_candidates(patterns, candidates_dir):
    """Stage patterns while preserving lifecycle history and uniqueness."""
    if not patterns:
        return 0
    os.makedirs(candidates_dir, exist_ok=True)
    written = 0

    lessons_path = os.path.join(
        os.path.dirname(candidates_dir), "semantic", "LESSONS.md"
    )
    lessons_text = ""
    if os.path.exists(lessons_path):
        try:
            with open(lessons_path, encoding="utf-8") as stream:
                lessons_text = stream.read()
        except OSError:
            pass
    current_terminal_lessons = set(extract_lesson_lines(lessons_text))

    for key, pattern in patterns.items():
        claim = (pattern.get("claim") or "").strip()
        if not claim:
            continue
        if lessons_text and check_exact_duplicate(claim, lessons_text):
            continue

        slug = _slug(pattern)
        previous, previous_location = _find_prior(slug, candidates_dir)
        if (
            previous_location == "graduated"
            and previous.get("status") != "provisional"
        ):
            continue

        if previous_location in ("rejected", "graduated"):
            decisions = previous.get("decisions") or []
            last = decisions[-1] if decisions else {}
            previous_evidence = set(last.get("evidence_snapshot", []))
            new_evidence = set(pattern.get("evidence_ids", []))
            evidence_changed = bool(new_evidence - previous_evidence)
            duplicate_claims = last.get("duplicate_claims") or []
            blocker_still_present = (
                any(
                    duplicate in current_terminal_lessons
                    for duplicate in duplicate_claims
                )
                if duplicate_claims
                else True
            )
            if not evidence_changed and blocker_still_present:
                continue

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        decisions = list(previous.get("decisions", []))
        decisions.append(
            {"ts": now, "action": "staged", "reviewer": "auto_dream"}
        )
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
        prior_path = None
        if previous_location in ("rejected", "graduated"):
            prior_path = os.path.join(
                candidates_dir, previous_location, f"{slug}.json"
            )
        _write_staged_atomically(candidate, staged_path, prior_path)
        written += 1
    return written
