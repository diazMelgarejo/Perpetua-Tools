"""Staging-only dream cycle. Mechanical work, no reasoning.

Responsibilities (in order):
  1. load episodic entries
  2. cluster + extract → structured patterns
  3. stage candidates (lifecycle metadata baked in)
  4. heuristic prefilter (length + exact-duplicate; obvious junk goes to rejected/)
  5. decay old episodes + archive stale workspace
  6. write REVIEW_QUEUE.md summary so the next host session sees the backlog
"""
import contextlib
import errno
import json
import os

from archive import archive_stale_workspace
from decay import decay_old_entries
from path_hygiene import sanitize_json_strings
from promote import cluster_and_extract, write_candidates
from review_state import mark_rejected, write_review_queue_summary
from validate import heuristic_check

try:
    import fcntl  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover — Windows
    fcntl = None  # type: ignore[assignment]

ROOT = os.path.abspath(os.path.dirname(__file__))
EPISODIC = os.path.join(ROOT, "episodic/AGENT_LEARNINGS.jsonl")
CANDIDATES = os.path.join(ROOT, "candidates")
SEMANTIC = os.path.join(ROOT, "semantic")
REVIEW_QUEUE = os.path.join(ROOT, "working/REVIEW_QUEUE.md")
PROMOTION_THRESHOLD = 7.0
CLUSTER_SIMILARITY = 0.3


@contextlib.contextmanager
def _episodic_locked():
    if fcntl is None:
        yield None
        return
    os.makedirs(os.path.dirname(EPISODIC), exist_ok=True)
    fd = os.open(EPISODIC, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _load_entries_locked(fd):
    entries = []
    if fd is None:
        if not os.path.exists(EPISODIC):
            return entries
        with open(EPISODIC, encoding="utf-8") as stream:
            content = stream.read()
    else:
        os.lseek(fd, 0, os.SEEK_SET)
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        content = b"".join(chunks).decode("utf-8", errors="replace")
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _write_all(fd, payload):
    """Write all bytes, retrying EINTR and rejecting zero-byte progress."""
    view = memoryview(payload)
    written = 0
    while written < len(view):
        try:
            count = os.write(fd, view[written:])
        except InterruptedError:
            continue
        except OSError as exc:
            if exc.errno == errno.EINTR:
                continue
            raise
        if count == 0:
            raise OSError("episodic rewrite made zero-byte progress")
        written += count


def _write_entries_locked(fd, entries):
    sanitized = [sanitize_json_strings(entry) for entry in entries]
    payload = "".join(json.dumps(entry) + "\n" for entry in sanitized).encode("utf-8")
    if fd is None:
        with open(EPISODIC, "w", encoding="utf-8") as stream:
            stream.write(payload.decode("utf-8"))
        return
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    _write_all(fd, payload)
    os.fsync(fd)


def _load_entries():
    with _episodic_locked() as fd:
        return _load_entries_locked(fd)


def _write_entries(entries):
    with _episodic_locked() as fd:
        _write_entries_locked(fd, entries)


def _heuristic_prefilter(candidates_dir, semantic_dir):
    if not os.path.isdir(candidates_dir):
        return 0
    lessons_path = os.path.join(semantic_dir, "LESSONS.md")
    if os.path.exists(lessons_path):
        with open(lessons_path, encoding="utf-8") as stream:
            existing = stream.read()
    else:
        existing = ""
    rejected = 0
    for filename in sorted(os.listdir(candidates_dir)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(candidates_dir, filename)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as stream:
                candidate = json.load(stream)
        except (OSError, json.JSONDecodeError):
            continue
        check = heuristic_check(candidate, existing)
        if not check["passed"]:
            mark_rejected(
                candidate["id"],
                "heuristic_prefilter",
                ", ".join(check["reasons"]),
                candidates_dir,
                duplicate_claims=check.get("duplicates", []),
            )
            rejected += 1
    return rejected


def run_dream_cycle():
    with _episodic_locked() as fd:
        entries = _load_entries_locked(fd)
        if not entries:
            pending = write_review_queue_summary(CANDIDATES, REVIEW_QUEUE)
            print(f"dream cycle: no entries (queue has {pending} pending)")
            return
        patterns = cluster_and_extract(entries, threshold=CLUSTER_SIMILARITY)
        promotable = {
            key: pattern
            for key, pattern in patterns.items()
            if pattern.get("canonical_salience", 0) >= PROMOTION_THRESHOLD
        }
        staged = write_candidates(promotable, CANDIDATES)
        prefiltered = _heuristic_prefilter(CANDIDATES, SEMANTIC)
        kept, archived = decay_old_entries(
            entries,
            archive_dir=os.path.join(ROOT, "episodic/snapshots"),
        )
        _write_entries_locked(fd, kept)
        archive_stale_workspace(
            working_dir=os.path.join(ROOT, "working"),
            archive_dir=os.path.join(ROOT, "episodic/snapshots"),
        )
        pending = write_review_queue_summary(CANDIDATES, REVIEW_QUEUE)
    print(
        f"dream cycle: patterns={len(patterns)} staged={staged} "
        f"prefiltered_out={prefiltered} pending_review={pending} "
        f"archived={len(archived)} kept={len(kept)}"
    )


if __name__ == "__main__":
    run_dream_cycle()
