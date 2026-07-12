"""Archive old low-salience entries instead of deleting."""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
from salience import salience_score

DECAY_DAYS = 90
SALIENCE_FLOOR = 2.0


def decay_old_entries(entries, archive_dir):
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=DECAY_DAYS
    )
    kept, archived = [], []
    for entry in entries:
        ts_str = entry.get("timestamp", "")
        try:
            ts = datetime.datetime.fromisoformat(ts_str)
            # Repository timestamp convention: legacy naive values mean UTC,
            # never workstation-local time.
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            else:
                ts = ts.astimezone(datetime.timezone.utc)
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
                stream.write(json.dumps(entry) + "\n")
    return kept, archived
