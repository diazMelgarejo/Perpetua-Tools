"""Staging-only dream cycle for the PT agent-memory lifecycle.

Responsibilities, in order:
  1. Load episodic JSONL under the shared sidecar lock.
  2. Replacement-decode malformed UTF-8 and skip malformed JSON rows.
  3. Cluster episodes and extract structured candidate patterns.
  4. Stage candidates with lifecycle metadata; never graduate subjectively.
  5. Heuristically reject obvious junk while preserving host review authority.
  6. Decay low-salience episodes and archive stale workspace artifacts.
  7. Atomically rewrite sanitized episodic state through fsynced temp replacement.
  8. Refresh REVIEW_QUEUE.md so the next host session sees pending work.

Durability and safety invariants:
  - One stable sidecar lock spans the complete read-modify-write cycle.
  - Every persisted JSON string passes through the tracked-path sanitizer.
  - The destination is replaced only after the temporary file is flushed/fsynced.
  - This module never graduates lessons and never commits unattended changes.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile

from archive import archive_stale_workspace
from decay import decay_old_entries
from promote import cluster_and_extract, write_candidates
from review_state import mark_rejected, write_review_queue_summary
from validate import heuristic_check

ROOT = os.path.abspath(os.path.dirname(__file__))
AGENT_ROOT = os.path.dirname(ROOT)
HARNESS_HOOKS = os.path.join(AGENT_ROOT, "harness", "hooks")
if HARNESS_HOOKS not in sys.path:
    sys.path.insert(0, HARNESS_HOOKS)
from _episodic_io import episodic_lock, is_legacy_episodic_row  # noqa: E402
from path_hygiene import sanitize_json_strings  # noqa: E402

EPISODIC = os.path.join(ROOT, "episodic/AGENT_LEARNINGS.jsonl")
CANDIDATES = os.path.join(ROOT, "candidates")
SEMANTIC = os.path.join(ROOT, "semantic")
REVIEW_QUEUE = os.path.join(ROOT, "working/REVIEW_QUEUE.md")
PROMOTION_THRESHOLD = 7.0
CLUSTER_SIMILARITY = 0.3


@contextlib.contextmanager
def _episodic_locked():
    """Hold the shared sidecar lock across the dream read-modify-write cycle."""
    with episodic_lock(EPISODIC, exclusive=True):
        yield None


def _load_entries_locked(_fd):
    """Read a replacement-decoded snapshot and skip malformed JSONL rows."""
    entries = []
    try:
        with open(EPISODIC, encoding="utf-8", errors="replace") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if is_legacy_episodic_row(entry):
                    continue
                entries.append(entry)
    except FileNotFoundError:
        pass
    return entries


def _write_all(fd, payload):
    """Write every byte, preserving the pre-atomic-rewrite helper contract.

    The production episodic rewrite uses temp-file persistence plus ``os.replace``.
    This helper remains for callers/tests that need a correct descriptor write-all
    primitive and for other durability code that may reuse it.
    """
    view = memoryview(payload)
    written = 0
    while written < len(view):
        try:
            count = os.write(fd, view[written:])
        except InterruptedError:
            continue
        if count <= 0:
            raise OSError("descriptor write made no progress")
        written += count


def _write_entries_locked(_fd, entries):
    """Atomically replace episodic JSONL after durable temp-file persistence.

    The sidecar lock remains stable across ``os.replace``. The temporary file is
    created in the destination directory so replacement stays on one filesystem.
    """
    os.makedirs(os.path.dirname(EPISODIC), exist_ok=True)
    payload = "".join(
        json.dumps(sanitize_json_strings(entry)) + "\n" for entry in entries
    )
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            errors="strict",
            dir=os.path.dirname(EPISODIC),
            prefix=".agent-learnings-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temp_path = stream.name
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, EPISODIC)
        temp_path = None
        try:
            dir_fd = os.open(os.path.dirname(EPISODIC), os.O_RDONLY)
        except OSError:
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


def _load_entries():
    with _episodic_locked() as fd:
        return _load_entries_locked(fd)


def _write_entries(entries):
    with _episodic_locked() as fd:
        _write_entries_locked(fd, entries)


def _heuristic_prefilter(candidates_dir, semantic_dir):
    """Move obvious junk to rejected while leaving subjective review to hosts."""
    if not os.path.isdir(candidates_dir):
        return 0
    lessons_path = os.path.join(semantic_dir, "LESSONS.md")
    if os.path.exists(lessons_path):
        with open(lessons_path, encoding="utf-8", errors="replace") as stream:
            existing = stream.read()
    else:
        existing = ""
    rejected = 0
    for fname in sorted(os.listdir(candidates_dir)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(candidates_dir, fname)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as stream:
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
    """Run one locked staging, decay, archive, and review-queue cycle."""
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
            entries, archive_dir=os.path.join(ROOT, "episodic/snapshots")
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
