"""recall.py must not surface superseded lessons from lessons.jsonl."""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / ".agent" / "tools"
sys.path.insert(0, str(TOOLS))

import recall  # noqa: E402


def _write_lessons(tmp_path: Path, rows: list[dict]) -> Path:
    semantic = tmp_path / "semantic"
    semantic.mkdir(parents=True)
    path = semantic / "lessons.jsonl"
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.unit
def test_load_structured_skips_superseded_lesson(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    old_id = "lesson_old_git_tip"
    new_id = "lesson_new_git_tip"
    lessons_path = _write_lessons(
        tmp_path,
        [
            {
                "id": old_id,
                "claim": "git branch -f silently no-ops on checked-out branch",
                "conditions": ["git branch -f"],
                "status": "accepted",
                "supersedes": None,
            },
            {
                "id": new_id,
                "claim": "git branch -f refuses with exit 128 on checked-out branch",
                "conditions": ["git branch -f", "rollback"],
                "status": "accepted",
                "supersedes": old_id,
            },
        ],
    )
    monkeypatch.setattr(recall, "LESSONS_JSONL", str(lessons_path))
    monkeypatch.setattr(recall, "LESSONS_MD", str(tmp_path / "missing.md"))

    loaded = recall._load_structured()
    ids = [row["id"] for row in loaded]

    assert new_id in ids
    assert old_id not in ids


@pytest.mark.unit
def test_recall_prefers_replacement_over_superseded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    old_id = "lesson_old_git_tip"
    new_id = "lesson_new_git_tip"
    lessons_path = _write_lessons(
        tmp_path,
        [
            {
                "id": old_id,
                "claim": (
                    "git branch -f <name> <sha> silently no-ops when checked out"
                ),
                "conditions": ["git branch -f", "cherry-pick loop"],
                "status": "accepted",
                "supersedes": None,
            },
            {
                "id": new_id,
                "claim": (
                    "git branch -f <name> <sha> refuses to move the checked-out "
                    "branch; use git update-ref then git restore"
                ),
                "conditions": ["git branch -f", "git update-ref", "rollback"],
                "status": "accepted",
                "supersedes": old_id,
            },
        ],
    )
    monkeypatch.setattr(recall, "LESSONS_JSONL", str(lessons_path))
    monkeypatch.setattr(recall, "LESSONS_MD", str(tmp_path / "missing.md"))

    result, meta = recall.recall(
        "git branch -f cherry-pick rollback update-ref",
        top_k=5,
        min_score=0.01,
    )
    returned_ids = [row["id"] for row in result if row.get("id")]

    assert new_id in returned_ids
    assert old_id not in returned_ids
    assert meta["considered"] == 1


@pytest.mark.unit
def test_provisional_supersession_does_not_retire_old_lesson(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    old_id = "lesson_active"
    provisional_id = "lesson_provisional"
    lessons_path = _write_lessons(
        tmp_path,
        [
            {
                "id": old_id,
                "claim": "Keep using the established rollback procedure",
                "conditions": ["rollback"],
                "status": "accepted",
                "supersedes": None,
            },
            {
                "id": provisional_id,
                "claim": "Experimental rollback procedure under review",
                "conditions": ["rollback"],
                "status": "provisional",
                "supersedes": old_id,
            },
        ],
    )
    monkeypatch.setattr(recall, "LESSONS_JSONL", str(lessons_path))
    monkeypatch.setattr(recall, "LESSONS_MD", str(tmp_path / "missing.md"))

    loaded = recall._load_structured()
    ids = [row["id"] for row in loaded]

    assert old_id in ids
    assert provisional_id not in ids
