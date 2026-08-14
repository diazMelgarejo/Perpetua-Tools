"""Rendered lessons preserve append-only historical records."""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY = REPO_ROOT / ".agent" / "memory"
sys.path.insert(0, str(MEMORY))

import render_lessons  # noqa: E402


pytestmark = pytest.mark.unit


def test_render_keeps_superseded_and_replacement_records_visible(
    tmp_path: Path,
) -> None:
    semantic = tmp_path / "semantic"
    semantic.mkdir()
    old_id = "lesson_original"
    replacement_id = "lesson_replacement"
    old_claim = "Original historical claim remains visible"
    replacement_claim = "Corrected claim supersedes the original"
    (semantic / "LESSONS.md").write_text(
        "# Lessons\n\n"
        "## Auto-promoted entries will be appended below\n",
        encoding="utf-8",
    )
    rows = [
        {
            "id": old_id,
            "claim": old_claim,
            "status": "accepted",
            "supersedes": None,
            "accepted_at": "2026-08-01T00:00:00+00:00",
        },
        {
            "id": replacement_id,
            "claim": replacement_claim,
            "status": "accepted",
            "supersedes": old_id,
            "accepted_at": "2026-08-02T00:00:00+00:00",
        },
    ]
    (semantic / "lessons.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    rendered = render_lessons.render_lessons_as_text(str(semantic))

    assert old_claim in rendered
    assert replacement_claim in rendered
    assert f"id={old_id}" in rendered
    assert f"id={replacement_id}" in rendered
    assert f"~~{old_claim}~~" not in rendered
    assert "superseded_by=" not in rendered
