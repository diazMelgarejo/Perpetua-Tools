"""Archive old, low-salience episodic entries instead of deleting them.

Responsibilities:
  1. Parse each entry timestamp without changing valid aware timestamps.
  2. Interpret legacy naive timestamps as host-local time, then normalize to UTC.
  3. Keep malformed or unparseable entries rather than discarding evidence.
  4. Archive only entries older than the retention window and below salience floor.
  5. Append archived rows as explicit UTF-8 JSONL using UTC-dated snapshots.
  6. Sanitize every string field at the persistence boundary.

Never:
  - delete episodic evidence outright;
  - reinterpret legacy naive timestamps as already-UTC;
  - persist workstation-specific paths or locale-dependent text.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
from salience import salience_score

from path_hygiene import sanitize_json_strings
from time_utils import legacy_local_to_utc

DECAY_DAYS = 90
SALIENCE_FLOOR = 2.0


def decay_old_entries(entries, archive_dir):
    """Partition entries by age/salience and append archived rows as UTF-8 JSONL."""
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=DECAY_DAYS)
    kept, archived = [], []
    for entry in entries:
        try:
            ts = legacy_local_to_utc(
                datetime.datetime.fromisoformat(entry.get("timestamp", ""))
            )
        except (TypeError, ValueError):
            kept.append(entry)
            continue
        if ts < cutoff and salience_score(entry) < SALIENCE_FLOOR:
            archived.append(entry)
        else:
            kept.append(entry)

    if archived:
        os.makedirs(archive_dir, exist_ok=True)
        today_utc = datetime.datetime.now(datetime.timezone.utc).date()
        path = os.path.join(archive_dir, f"archive_{today_utc}.jsonl")
        with open(path, "a", encoding="utf-8") as stream:
            for entry in archived:
                stream.write(json.dumps(sanitize_json_strings(entry)) + "\n")
    return kept, archived
