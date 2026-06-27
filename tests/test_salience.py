"""Tests for .agent/harness/salience.py — _parse_timestamp and salience_score."""
from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path

import pytest

# Load salience module from its non-package location in .agent/harness/
_SALIENCE_PATH = Path(__file__).resolve().parents[1] / ".agent" / "harness" / "salience.py"
_spec = importlib.util.spec_from_file_location("agent_harness_salience", _SALIENCE_PATH)
_salience = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_salience)  # type: ignore[union-attr]

_parse_timestamp = _salience._parse_timestamp
salience_score = _salience.salience_score


# ---------------------------------------------------------------------------
# _parse_timestamp
# ---------------------------------------------------------------------------


def test_parse_timestamp_utc_z_suffix():
    """'Z' suffix must be converted to +00:00 and returned as UTC-aware."""
    dt = _parse_timestamp("2026-06-27T01:52:47Z")
    assert dt.tzinfo is not None
    assert dt.tzinfo == datetime.timezone.utc
    assert dt.year == 2026
    assert dt.month == 6
    assert dt.day == 27
    assert dt.hour == 1


def test_parse_timestamp_utc_offset():
    """'+00:00' offset timestamps must be returned as UTC-aware."""
    dt = _parse_timestamp("2026-06-27T01:52:47.302407+00:00")
    assert dt.tzinfo == datetime.timezone.utc
    assert dt.second == 47


def test_parse_timestamp_naive_becomes_utc():
    """Naive ISO timestamps (no tzinfo) must be normalised to UTC."""
    dt = _parse_timestamp("2026-06-24T12:00:00")
    assert dt.tzinfo == datetime.timezone.utc
    assert dt.year == 2026
    assert dt.month == 6
    assert dt.day == 24
    assert dt.hour == 12


def test_parse_timestamp_non_utc_offset_converted():
    """+05:30 timezone must be converted to UTC (subtract 5h30m)."""
    dt = _parse_timestamp("2026-06-27T07:22:47+05:30")
    assert dt.tzinfo == datetime.timezone.utc
    # 07:22:47 +05:30  →  01:52:47 UTC
    assert dt.hour == 1
    assert dt.minute == 52
    assert dt.second == 47


def test_parse_timestamp_microseconds_preserved():
    """Microseconds must survive the parse + UTC conversion."""
    dt = _parse_timestamp("2026-06-27T01:52:47.302407+00:00")
    assert dt.microsecond == 302407


def test_parse_timestamp_midnight_naive():
    """Midnight naive timestamp normalises to UTC midnight."""
    dt = _parse_timestamp("2026-01-01T00:00:00")
    assert dt == datetime.datetime(2026, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)


# ---------------------------------------------------------------------------
# salience_score
# ---------------------------------------------------------------------------


def _now_utc_str(offset_days: int = 0) -> str:
    """Return an ISO-8601 UTC timestamp string offset_days in the past."""
    ts = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=offset_days)
    return ts.isoformat()


def test_salience_score_missing_timestamp_returns_zero():
    """Entry without a timestamp must return 0.0."""
    assert salience_score({}) == 0.0
    assert salience_score({"pain_score": 9}) == 0.0


def test_salience_score_empty_timestamp_returns_zero():
    """Empty string timestamp must return 0.0."""
    assert salience_score({"timestamp": ""}) == 0.0


def test_salience_score_invalid_timestamp_uses_age_999():
    """Unparseable timestamps fall back to age_days=999, giving recency ≤ 0."""
    score = salience_score({
        "timestamp": "not-a-date",
        "pain_score": 10,
        "importance": 10,
        "recurrence_count": 3,
    })
    # recency = max(0, 10 - 999*0.3) = 0  → score must be 0
    assert score == 0.0


def test_salience_score_fresh_entry_positive():
    """A very recent entry (age_days=0) must produce a positive score."""
    entry = {
        "timestamp": _now_utc_str(0),
        "pain_score": 10,
        "importance": 10,
        "recurrence_count": 1,
    }
    score = salience_score(entry)
    assert score > 0.0


def test_salience_score_old_entry_is_zero_or_near_zero():
    """An entry older than 34 days has recency ≤ 0, so score must be 0."""
    entry = {
        "timestamp": _now_utc_str(35),
        "pain_score": 10,
        "importance": 10,
        "recurrence_count": 3,
    }
    score = salience_score(entry)
    # recency = max(0, 10 - 35*0.3) = max(0, -0.5) = 0
    assert score == 0.0


def test_salience_score_uses_pain_and_importance():
    """Higher pain and importance must produce a higher score than lower values."""
    ts = _now_utc_str(0)
    high = salience_score({"timestamp": ts, "pain_score": 10, "importance": 10, "recurrence_count": 1})
    low = salience_score({"timestamp": ts, "pain_score": 1, "importance": 1, "recurrence_count": 1})
    assert high > low


def test_salience_score_recurrence_capped_at_3():
    """recurrence_count is capped at 3 — recurrence=4 must equal recurrence=3."""
    ts = _now_utc_str(0)
    base = {"timestamp": ts, "pain_score": 5, "importance": 5}
    score_3 = salience_score({**base, "recurrence_count": 3})
    score_4 = salience_score({**base, "recurrence_count": 4})
    score_10 = salience_score({**base, "recurrence_count": 10})
    assert score_3 == score_4 == score_10


def test_salience_score_recurrence_defaults_to_1():
    """Missing recurrence_count defaults to 1."""
    ts = _now_utc_str(0)
    score_default = salience_score({"timestamp": ts, "pain_score": 5, "importance": 5})
    score_explicit = salience_score({"timestamp": ts, "pain_score": 5, "importance": 5, "recurrence_count": 1})
    assert score_default == score_explicit


def test_salience_score_default_pain_and_importance():
    """Missing pain_score defaults to 5, missing importance defaults to 5."""
    ts = _now_utc_str(0)
    score_defaults = salience_score({"timestamp": ts})
    score_explicit = salience_score({"timestamp": ts, "pain_score": 5, "importance": 5, "recurrence_count": 1})
    assert score_defaults == score_explicit


def test_salience_score_aware_utc_offset_timestamp():
    """Episodic entries with +00:00 offset must not raise TypeError."""
    entry = {
        "timestamp": "2026-06-27T01:52:47.302407+00:00",
        "pain_score": 8,
        "importance": 7,
        "recurrence_count": 2,
    }
    # Must not raise — this is the core regression from the UTC fix
    score = salience_score(entry)
    assert isinstance(score, float)


def test_salience_score_z_suffix_timestamp_no_typeerror():
    """Timestamps ending in 'Z' must not raise TypeError."""
    entry = {
        "timestamp": "2026-06-27T01:52:47Z",
        "pain_score": 5,
        "importance": 5,
        "recurrence_count": 1,
    }
    score = salience_score(entry)
    assert isinstance(score, float)


def test_salience_score_formula_values():
    """Spot-check the formula: recency * (pain/10) * (importance/10) * min(rec, 3)."""
    # Use a timestamp exactly 0 days old — age_days will be 0
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    entry = {"timestamp": ts, "pain_score": 10, "importance": 10, "recurrence_count": 1}
    score = salience_score(entry)
    # recency = max(0, 10 - 0 * 0.3) = 10
    # score = 10 * (10/10) * (10/10) * min(1,3) = 10
    assert abs(score - 10.0) < 0.01