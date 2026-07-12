"""Salience scoring: recent + painful + important + recurring = surface first."""
import datetime


def _parse_timestamp(ts: str) -> datetime.datetime:
    """Parse ISO timestamps; normalize naive values to UTC."""
    dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def salience_score(entry: dict) -> float:
    """Weighted score used for episodic retrieval and promotion thresholds."""
    ts = entry.get("timestamp")
    if not ts:
        return 0.0
    try:
        if not isinstance(ts, str):
            raise ValueError("timestamp must be a string")
        age_days = max(
            0,
            (
                datetime.datetime.now(datetime.timezone.utc)
                - _parse_timestamp(ts)
            ).days,
        )
    except (TypeError, ValueError):
        age_days = 999
    pain = entry.get("pain_score", 5)
    importance = entry.get("importance", 5)
    recurrence = entry.get("recurrence_count", 1)
    recency = max(0.0, min(10.0, 10.0 - age_days * 0.3))
    return recency * (pain / 10.0) * (importance / 10.0) * min(recurrence, 3)
