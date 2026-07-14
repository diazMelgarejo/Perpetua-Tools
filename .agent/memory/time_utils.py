"""Shared timestamp compatibility helpers for tracked memory records."""
from __future__ import annotations

import datetime


def legacy_local_to_utc(ts: datetime.datetime) -> datetime.datetime:
    """Normalize a timestamp to UTC, treating legacy naive values as local wall time.

    Older memory records were written without an offset. Their historical meaning
    is the host's local wall clock, not UTC. Attach the current local timezone only
    for those naive values, then normalize both naive and aware timestamps to UTC.
    """
    if ts.tzinfo is None:
        local_tz = datetime.datetime.now().astimezone().tzinfo
        ts = ts.replace(tzinfo=local_tz)
    return ts.astimezone(datetime.timezone.utc)
