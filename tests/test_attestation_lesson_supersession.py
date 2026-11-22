"""The attestation wording corrections must formally retire the older wording.

``render_lessons.superseded_by_map`` retires a lesson only when an accepted
record names it in ``supersedes``. Prose such as "this corrects X" does not
create that link, so the first-round attestation wording stayed active.
"""

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY = REPO_ROOT / ".agent" / "memory"
sys.path.insert(0, str(MEMORY))

import render_lessons  # noqa: E402

OVERCLAIM = "lesson_762380426dc7"
FIRST_CORRECTION = "lesson_371473e17ad0"
FIRST_CORRECTION_SHA256 = "d261f490e062a5c57c5ce78bb3af2490c0e15e2ed6109fff86b8e4a953494429"


def _rows() -> list[dict]:
    """Return the structured lesson rows exactly as the renderer loads them."""
    return render_lessons.load_lessons(str(MEMORY / "semantic"))


def test_overclaiming_attestation_lesson_is_retired() -> None:
    """An accepted record must name the over-claiming lesson in supersedes."""
    mapping = render_lessons.superseded_by_map(_rows())
    assert OVERCLAIM in mapping, "lesson_762380426dc7 is still active"
    replacement = next(r for r in _rows() if r["id"] == mapping[OVERCLAIM])
    assert replacement["status"] == "accepted"
    claim = replacement["claim"]
    assert "same OS user" in claim and "attest" in claim
    assert "cannot force a human confirmation" in claim


def test_historical_correction_row_is_unchanged() -> None:
    """The earlier correction row must stay byte-identical (additive history)."""
    raw = (MEMORY / "semantic" / "lessons.jsonl").read_text(encoding="utf-8")
    line = next(x for x in raw.splitlines() if f'"id": "{FIRST_CORRECTION}"' in x)
    assert hashlib.sha256(line.encode("utf-8")).hexdigest() == FIRST_CORRECTION_SHA256


def test_original_attestation_overclaim_is_retired() -> None:
    """lesson_15733a3316ad ('a file only the operator writes') must be retired."""
    mapping = render_lessons.superseded_by_map(_rows())
    assert "lesson_15733a3316ad" in mapping, "lesson_15733a3316ad is still active"
    replacement = next(r for r in _rows() if r["id"] == mapping["lesson_15733a3316ad"])
    assert replacement["status"] == "accepted"
    claim = replacement["claim"]
    for kept in ("Free", "pay-as-you-go", "seven days", "max_retries=0", "402", "429",
                 "provider_limits verify"):
        assert kept in claim, kept
    assert "same OS user" in claim and "cannot prove who wrote" in claim
    assert "over-claimed" in claim  # the quoted phrases are named only as the over-claim
