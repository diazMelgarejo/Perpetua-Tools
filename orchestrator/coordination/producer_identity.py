"""Random opaque producer identifiers for coordination events (closure row C4).

Coordination events used to carry ``<branch>@<absolute cwd>``, which exposes
branch names and workstation layout to every reader of the shared event log,
derived memory and LAN peers. A hash of that path would not help: the inputs
are predictable, so the hash can be confirmed by guessing.

Each worktree instead gets a random identifier ``ptp-<32 hex>`` that is created
once and then reused across restarts. It is stored in the worktree's own git
directory (never tracked) with owner-only permissions, so the only local
mapping from identifier to worktree is the location of that file. Outside a
git checkout the file lives in the runtime state directory instead.
"""
from __future__ import annotations

import os
import re
import secrets
import subprocess
import uuid
from pathlib import Path
from typing import Callable, FrozenSet, Optional

ID_PREFIX = "ptp-"
ID_FILE_NAME = "pt-producer-id"
UNAVAILABLE_PRODUCER_ID = "ptp-unavailable"
_MAX_ATTEMPTS = 5
_ID_RE = re.compile(r"^ptp-[0-9a-f]{32}$")


class ProducerIdError(Exception):
    """The producer identifier could not be read or created safely."""


def is_opaque_producer_id(value: object) -> bool:
    """Return True when ``value`` is a well-formed random producer identifier."""
    return isinstance(value, str) and bool(_ID_RE.match(value))


def _default_token() -> str:
    """Return 128 bits of randomness as 32 lowercase hex characters."""
    return secrets.token_hex(16)


def _git_path(flag: str) -> Optional[Path]:
    """Resolve a ``git rev-parse`` directory flag to an absolute path, or None."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", flag],
            text=True, encoding="utf-8", stderr=subprocess.DEVNULL, timeout=5,
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    return Path(out).resolve() if out else None


def producer_id_path() -> Path:
    """Return the per-worktree identifier file location.

    ``PT_PRODUCER_ID_FILE``, when set, names the file explicitly (tests and
    packaged deployments). Otherwise, inside git this is
    ``$(git rev-parse --git-dir)/pt-producer-id``, which is distinct per linked
    worktree and never part of the working tree. Outside git it falls back to
    the runtime state directory.
    """
    explicit = os.environ.get("PT_PRODUCER_ID_FILE", "").strip()
    if explicit:
        return Path(explicit)
    git_dir = _git_path("--git-dir")
    if git_dir is not None:
        return git_dir / ID_FILE_NAME
    from orchestrator.gossip_bus import resolve_default_state_dir

    return Path(resolve_default_state_dir()) / ID_FILE_NAME


def sibling_producer_ids(id_path: Path) -> FrozenSet[str]:
    """Return identifiers already used by other worktrees of the same repo.

    Reads ``<common-dir>/pt-producer-id`` and
    ``<common-dir>/worktrees/*/pt-producer-id``; only well-formed values count.
    A copied or restored git directory could otherwise reuse an identifier.
    """
    common = _git_path("--git-common-dir")
    if common is None:
        return frozenset()
    candidates = [common / ID_FILE_NAME, *sorted((common / "worktrees").glob(f"*/{ID_FILE_NAME}"))]
    found = set()
    for candidate in candidates:
        if candidate.resolve() == id_path.resolve():
            continue
        try:
            value = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if is_opaque_producer_id(value):
            found.add(value)
    return frozenset(found)


def _read_existing(id_path: Path) -> str:
    """Read and validate an existing identifier file; refuse malformed content."""
    value = id_path.read_text(encoding="utf-8").strip()
    if not is_opaque_producer_id(value):
        raise ProducerIdError(
            f"producer id file {ID_FILE_NAME} is malformed; refusing to rotate it silently"
        )
    return value


def _write_producer_id_file(id_path: Path, candidate: str) -> bool:
    """Write candidate to a private temporary file, flush/fsync, and atomically publish.

    Returns True if this process successfully published the file, or False if another
    process won the race (FileExistsError). Never leaves an empty or partial file at
    id_path.
    """
    tmp_path = id_path.with_name(f".{id_path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        try:
            os.write(fd, (candidate + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        if os.name == "posix":
            os.chmod(tmp_path, 0o600)
        try:
            os.link(str(tmp_path), str(id_path))
        except FileExistsError:
            return False
        except (AttributeError, NotImplementedError, OSError):
            if id_path.exists():
                return False
            try:
                if os.name == "nt":
                    os.rename(str(tmp_path), str(id_path))
                else:
                    if id_path.exists():
                        return False
                    os.replace(str(tmp_path), str(id_path))
            except FileExistsError:
                return False
        return True
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def load_or_create_producer_id(
    id_path: Path,
    *,
    token_hex: Callable[[], str] = _default_token,
    sibling_ids: Optional[FrozenSet[str]] = None,
) -> str:
    """Return the identifier stored at ``id_path``, creating it once if absent.

    Creation writes to a private temporary file first, flushes and fsyncs, then
    atomically publishes so concurrent readers never observe an empty or
    truncated file. Two processes racing on first use converge on whichever file
    landed first. Candidates that are malformed or already used by a sibling
    worktree are redrawn up to a small bound; after that the call fails closed
    with ``ProducerIdError``. An existing malformed file is reported, never
    overwritten.
    """
    id_path = Path(id_path)
    if id_path.exists():
        return _read_existing(id_path)
    taken = sibling_producer_ids(id_path) if sibling_ids is None else sibling_ids
    id_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    for _ in range(_MAX_ATTEMPTS):
        candidate = ID_PREFIX + token_hex()
        if not is_opaque_producer_id(candidate) or candidate in taken:
            continue
        if _write_producer_id_file(id_path, candidate):
            return candidate
        return _read_existing(id_path)
    raise ProducerIdError("could not draw a unique producer id")


def current_producer_id() -> str:
    """Return this worktree's identifier, or a fixed placeholder on any error.

    Coordination emit paths call this; identity problems must never crash them.
    """
    try:
        return load_or_create_producer_id(producer_id_path())
    except (ProducerIdError, OSError):
        return UNAVAILABLE_PRODUCER_ID
