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
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
from salience import salience_score

from path_hygiene import sanitize_json_strings
from time_utils import legacy_local_to_utc

DECAY_DAYS = 90
SALIENCE_FLOOR = 2.0


def _archive_entry_id(entry):
    """Stable id used to make archive appends idempotent across retries."""
    for key in ("id", "timestamp", "event_id"):
        value = entry.get(key) if isinstance(entry, dict) else None
        if value:
            return f"{key}:{value}"
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
        seen_ids = set()
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="replace") as stream:
                for raw in stream:
                    try:
                        existing = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(existing, dict):
                        seen_ids.add(_archive_entry_id(existing))
        with open(path, "a", encoding="utf-8") as stream:
            for entry in archived:
                entry_id = _archive_entry_id(entry)
                if entry_id in seen_ids:
                    continue
                stream.write(json.dumps(sanitize_json_strings(entry)) + "\n")
                seen_ids.add(entry_id)
    return kept, archived
