"""show.py:lesson_stats() must not inflate accepted count via supersession or retraction."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / ".agent" / "tools"
sys.path.insert(0, str(TOOLS))

import show  # noqa: E402


def _write_lessons(tmp_path: Path, rows: list[dict]) -> Path:
    semantic = tmp_path / "semantic"
    semantic.mkdir(parents=True)
    path = semantic / "lessons.jsonl"
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def test_superseded_lesson_not_double_counted(monkeypatch, tmp_path):
    old_id = "lesson_old"
    new_id = "lesson_new"
    lessons_path = _write_lessons(
        tmp_path,
        [
            {"id": old_id, "claim": "old claim", "status": "accepted", "supersedes": None},
            {"id": new_id, "claim": "new claim", "status": "accepted", "supersedes": old_id},
        ],
    )
    monkeypatch.setattr(show, "LESSONS_JSONL", str(lessons_path))

    stats = show.lesson_stats()

    accepted_ids = [l["id"] for l in stats["accepted"]]
    assert accepted_ids == [new_id]
    assert stats["count"] == 2


def test_retracted_lesson_not_counted_as_accepted(monkeypatch, tmp_path):
    lesson_id = "lesson_retracted_case"
    lessons_path = _write_lessons(
        tmp_path,
        [
            {"id": lesson_id, "claim": "claim", "status": "accepted", "supersedes": None},
            {
                "id": lesson_id,
                "claim": "claim",
                "status": "retracted",
                "supersedes": None,
                "retraction_rationale": "no longer true",
            },
        ],
    )
    monkeypatch.setattr(show, "LESSONS_JSONL", str(lessons_path))

    stats = show.lesson_stats()

    assert stats["accepted"] == []
    assert stats["count"] == 1  # deduped by id, latest row wins


def test_provisional_supersession_does_not_retire_old_lesson(monkeypatch, tmp_path):
    old_id = "lesson_active"
    provisional_id = "lesson_provisional"
    lessons_path = _write_lessons(
        tmp_path,
        [
            {"id": old_id, "claim": "established claim", "status": "accepted", "supersedes": None},
            {
                "id": provisional_id,
                "claim": "experimental claim",
                "status": "provisional",
                "supersedes": old_id,
            },
        ],
    )
    monkeypatch.setattr(show, "LESSONS_JSONL", str(lessons_path))

    stats = show.lesson_stats()

    accepted_ids = [l["id"] for l in stats["accepted"]]
    assert accepted_ids == [old_id]
    assert stats["provisional"] == 1


def test_unrelated_accepted_lessons_all_counted(monkeypatch, tmp_path):
    lessons_path = _write_lessons(
        tmp_path,
        [
            {"id": "lesson_a", "claim": "a", "status": "accepted", "supersedes": None},
            {"id": "lesson_b", "claim": "b", "status": "accepted", "supersedes": None},
        ],
    )
    monkeypatch.setattr(show, "LESSONS_JSONL", str(lessons_path))

    stats = show.lesson_stats()

    accepted_ids = {l["id"] for l in stats["accepted"]}
    assert accepted_ids == {"lesson_a", "lesson_b"}
    assert stats["count"] == 2
