"""Append-only corrections must keep both histories and make current guidance truthful."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agent/tools"))


def _fixture(tmp_path: Path, status: str = "provisional") -> tuple[Path, Path, bytes]:
    """Seed an immutable original row and an already-existing audit record."""
    semantic = tmp_path / "semantic"
    semantic.mkdir()
    raw = (json.dumps({"id": "lesson_case", "claim": "The wrong topic was assigned to this ID",
                       "status": status, "conditions": ["topic"], "evidence_ids": ["prior"],
                       "source_candidate": "case", "accepted_at": "2026-11-07"}) + "\n").encode()
    (semantic / "lessons.jsonl").write_bytes(raw)
    (semantic / "LESSONS.md").write_text(
        "# Lessons\n\n## Auto-promoted entries will be appended below\n", encoding="utf-8"
    )
    audit = tmp_path / "episodic/AGENT_LEARNINGS.jsonl"
    audit.parent.mkdir()
    audit.write_bytes(b'{"timestamp":"prior","detail":"historical bytes"}\n')
    return semantic, audit, raw


def _correct(semantic: Path, audit: Path, **kwargs: Any) -> dict[str, Any]:
    """Invoke the real native correction operation, not a file-writing test double."""
    module = importlib.import_module("correct_lesson")
    return module.correct_lesson(
        "lesson_case", "This ID records its original filesystem topic correctly",
        "Correct mismatched topic without rewriting evidence", "test-reviewer",
        semantic_dir=semantic, episodic_path=audit, **kwargs,
    )


@pytest.mark.parametrize("initial", ["accepted", "provisional", "legacy"])
def test_correction_appends_both_histories_and_renders_provisional(tmp_path: Path, initial: str) -> None:
    """Repair guidance without rewriting the original row or granting accepted status."""
    semantic, audit, original = _fixture(tmp_path, initial)
    audit_before = audit.read_bytes()
    result = _correct(semantic, audit)
    assert (semantic / "lessons.jsonl").read_bytes().startswith(original)
    assert audit.read_bytes().startswith(audit_before)
    assert result["id"] == "lesson_case" and result["status"] == "provisional"
    assert result["source_candidate"] == "case"
    episode = json.loads(audit.read_text().splitlines()[-1])
    assert episode["timestamp"] in result["evidence_ids"]
    assert "lesson_case" in episode["detail"] and "filesystem topic" in episode["detail"]
    rendered = (semantic / "LESSONS.md").read_text()
    assert "[PROVISIONAL] This ID records its original filesystem topic correctly" in rendered
    assert "The wrong topic" not in rendered


def test_identical_correction_retry_does_not_duplicate_history(tmp_path: Path) -> None:
    """An identical retry repairs derived output without another semantic or audit row."""
    semantic, audit, _ = _fixture(tmp_path)
    first = _correct(semantic, audit)
    semantic_bytes, audit_bytes = (semantic / "lessons.jsonl").read_bytes(), audit.read_bytes()
    (semantic / "LESSONS.md").write_text("# Missing derived view\n", encoding="utf-8")
    assert _correct(semantic, audit) == first
    assert (semantic / "lessons.jsonl").read_bytes() == semantic_bytes
    assert audit.read_bytes() == audit_bytes
    assert "[PROVISIONAL]" in (semantic / "LESSONS.md").read_text()


def test_correction_audit_failure_does_not_publish_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing correction evidence must not advance the semantic snapshot."""
    semantic, audit, original = _fixture(tmp_path)
    module = importlib.import_module("correct_lesson")

    def refuse(*args: Any, **kwargs: Any) -> None:
        """Model an unavailable audit destination."""
        raise OSError("audit unavailable")

    monkeypatch.setattr(module, "append_jsonl", refuse)
    with pytest.raises(OSError, match="audit unavailable"):
        _correct(semantic, audit)
    assert (semantic / "lessons.jsonl").read_bytes() == original


@pytest.mark.parametrize("initial", ["retracted", "staged", "unknown"])
def test_correction_cannot_resurrect_closed_or_unknown_state(tmp_path: Path, initial: str) -> None:
    """A correction is not authority to revive a retired lesson or invent a lifecycle."""
    semantic, audit, original = _fixture(tmp_path, initial)
    with pytest.raises(ValueError, match="not correctable"):
        _correct(semantic, audit)
    assert (semantic / "lessons.jsonl").read_bytes() == original


def test_retry_after_semantic_failure_reuses_the_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful audit followed by a failed semantic append remains retryable."""
    semantic, audit, original = _fixture(tmp_path)
    module = importlib.import_module("correct_lesson")
    real_append = module._append_lesson_unlocked

    def refuse(*args: Any, **kwargs: Any) -> None:
        """Model a semantic destination refusing the correction."""
        raise OSError("semantic unavailable")

    monkeypatch.setattr(module, "_append_lesson_unlocked", refuse)
    with pytest.raises(OSError, match="semantic unavailable"):
        _correct(semantic, audit)
    assert (semantic / "lessons.jsonl").read_bytes() == original
    audit_bytes = audit.read_bytes()
    monkeypatch.setattr(module, "_append_lesson_unlocked", real_append)
    result = _correct(semantic, audit)
    assert audit.read_bytes() == audit_bytes
    assert json.loads(audit.read_text().splitlines()[-1])["timestamp"] in result["evidence_ids"]


def test_retry_after_render_failure_keeps_both_histories_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed derived-view write does not require a second correction snapshot."""
    semantic, audit, _ = _fixture(tmp_path)
    module = importlib.import_module("correct_lesson")
    real_render = module.render_lessons

    def refuse(*args: Any, **kwargs: Any) -> None:
        """Model a temporarily unwritable generated view."""
        raise OSError("render unavailable")

    monkeypatch.setattr(module, "render_lessons", refuse)
    with pytest.raises(OSError, match="render unavailable"):
        _correct(semantic, audit)
    semantic_bytes, audit_bytes = (semantic / "lessons.jsonl").read_bytes(), audit.read_bytes()
    monkeypatch.setattr(module, "render_lessons", real_render)
    _correct(semantic, audit)
    assert (semantic / "lessons.jsonl").read_bytes() == semantic_bytes
    assert audit.read_bytes() == audit_bytes
    assert "[PROVISIONAL]" in (semantic / "LESSONS.md").read_text()


def test_correction_cannot_promote_to_accepted(tmp_path: Path) -> None:
    """Correction authority never substitutes for lesson acceptance review."""
    semantic, audit, original = _fixture(tmp_path)
    with pytest.raises(ValueError, match="provisional or retracted"):
        _correct(semantic, audit, status="accepted")
    assert (semantic / "lessons.jsonl").read_bytes() == original


@pytest.mark.parametrize("status", ["provisional", "retracted"])
def test_correction_cannot_revive_a_superseded_predecessor(tmp_path: Path, status: str) -> None:
    """Downgrading a superseder needs lineage review, not silent resurrection."""
    semantic, audit, _ = _fixture(tmp_path, "accepted")
    rows = [
        {"id": "lesson_old", "claim": "Previously retired unsafe guidance", "status": "accepted"},
        {"id": "lesson_case", "claim": "Replacement guidance that retired the old rule",
         "status": "accepted", "supersedes": "lesson_old"},
    ]
    original = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
    (semantic / "lessons.jsonl").write_bytes(original)
    audit_bytes = audit.read_bytes()
    with pytest.raises(ValueError, match="supersession lineage"):
        _correct(semantic, audit, status=status)
    assert (semantic / "lessons.jsonl").read_bytes() == original
    assert audit.read_bytes() == audit_bytes


@pytest.mark.parametrize("damaged", ["semantic", "audit"])
def test_torn_history_is_preserved_and_refuses_correction(tmp_path: Path, damaged: str) -> None:
    """Malformed history needs explicit recovery, never silent skipping or truncation."""
    semantic, audit, _ = _fixture(tmp_path)
    target = semantic / "lessons.jsonl" if damaged == "semantic" else audit
    target.write_bytes(target.read_bytes() + b'{"incomplete":')
    semantic_bytes, audit_bytes = (semantic / "lessons.jsonl").read_bytes(), audit.read_bytes()
    with pytest.raises(json.JSONDecodeError):
        _correct(semantic, audit)
    assert (semantic / "lessons.jsonl").read_bytes() == semantic_bytes
    assert audit.read_bytes() == audit_bytes


def test_matching_audit_followed_by_torn_row_refuses_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A matching audit cannot hide malformed later history on a semantic retry."""
    semantic, audit, _ = _fixture(tmp_path)
    module = importlib.import_module("correct_lesson")
    original = module._append_lesson_unlocked

    def refuse(*args: Any, **kwargs: Any) -> None:
        """Interrupt after the audit append."""
        raise OSError("interrupted")

    monkeypatch.setattr(module, "_append_lesson_unlocked", refuse)
    with pytest.raises(OSError):
        _correct(semantic, audit)
    monkeypatch.setattr(module, "_append_lesson_unlocked", original)
    audit.write_bytes(audit.read_bytes() + b'{"torn":')
    before = (semantic / "lessons.jsonl").read_bytes(), audit.read_bytes()
    with pytest.raises(json.JSONDecodeError):
        _correct(semantic, audit)
    assert before == ((semantic / "lessons.jsonl").read_bytes(), audit.read_bytes())


def test_identical_retry_validates_audit_before_render(tmp_path: Path) -> None:
    """A retry cannot publish a derived view from a damaged audit history."""
    semantic, audit, _ = _fixture(tmp_path)
    _correct(semantic, audit)
    audit.write_bytes(audit.read_bytes() + b'{"torn":')
    view = semantic / "LESSONS.md"
    view.write_text("stale view", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        _correct(semantic, audit)
    assert view.read_text() == "stale view"


def test_correction_separates_complete_unterminated_rows(tmp_path: Path) -> None:
    """Both native appenders preserve the old prefix and separate complete records."""
    semantic, audit, _ = _fixture(tmp_path)
    lesson = semantic / "lessons.jsonl"
    lesson.write_bytes(lesson.read_bytes().rstrip(b"\n"))
    audit.write_bytes(audit.read_bytes().rstrip(b"\n"))
    prefixes = lesson.read_bytes(), audit.read_bytes()
    _correct(semantic, audit)
    for path, prefix in zip((lesson, audit), prefixes):
        assert path.read_bytes().startswith(prefix + b"\n")
        assert len([json.loads(line) for line in path.read_text().splitlines()]) == 2


def test_retraction_and_retry_remain_visibly_retracted(tmp_path: Path) -> None:
    """Retraction remains latest and visible after an identical retry."""
    semantic, audit, _ = _fixture(tmp_path, "accepted")
    first = _correct(semantic, audit, status="retracted")
    semantic_bytes, audit_bytes = (semantic / "lessons.jsonl").read_bytes(), audit.read_bytes()
    assert _correct(semantic, audit, status="retracted") == first
    assert (semantic / "lessons.jsonl").read_bytes() == semantic_bytes
    assert audit.read_bytes() == audit_bytes
    assert json.loads(semantic_bytes.splitlines()[-1])["status"] == "retracted"
    assert "~~[RETRACTED]" in (semantic / "LESSONS.md").read_text()
