"""Shared timestamp compatibility helpers for tracked memory records."""
from __future__ import annotations

import datetime


def legacy_local_to_utc(ts: datetime.datetime) -> datetime.datetime:
    """Normalize a timestamp to UTC, treating legacy naive values as local wall time.

    Older memory records were written without an offset. Their historical meaning
    is the host's local wall clock, not UTC. For naive values, astimezone(UTC)
    asks the runtime to interpret the wall time using the local offset that
    applied on that timestamp's date, not today's possibly-different offset.
    """
    return ts.astimezone(datetime.timezone.utc)
