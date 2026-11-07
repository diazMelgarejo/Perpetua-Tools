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
import stat
import subprocess
import uuid
from pathlib import Path
from typing import Callable, FrozenSet, Optional

ID_PREFIX = "ptp-"
ID_FILE_NAME = "pt-producer-id"
UNAVAILABLE_PRODUCER_ID = "ptp-unavailable"
_MAX_ATTEMPTS = 5
_ID_RE = re.compile(r"^ptp-[0-9a-f]{32}$")
_GIT_LOCATION_ENV = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES", "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_IMPLICIT_WORK_TREE", "GIT_PREFIX", "GIT_NAMESPACE",
})


class ProducerIdError(Exception):
    """The producer identifier could not be read or created safely."""


def is_opaque_producer_id(value: object) -> bool:
    """Return True when ``value`` is a well-formed random producer identifier."""
    return isinstance(value, str) and bool(_ID_RE.match(value))


def _default_token() -> str:
    """Return 128 bits of randomness as 32 lowercase hex characters."""
    return secrets.token_hex(16)


def _git_path(flag: str) -> Optional[Path]:
    """Discover Git directories from cwd, ignoring inherited repository locations."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", flag],
            env={key: value for key, value in os.environ.items() if key not in _GIT_LOCATION_ENV},
            text=True, encoding="utf-8", stderr=subprocess.DEVNULL, timeout=5,
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, UnicodeError):
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
        except FileNotFoundError:
            continue
        except (OSError, UnicodeError) as exc:
            raise ProducerIdError("sibling producer id cannot be read safely") from exc
        if is_opaque_producer_id(value):
            found.add(value)
    return frozenset(found)


def _read_existing(id_path: Path, sibling_ids: FrozenSet[str] = frozenset()) -> str:
    """Secure the opened regular file, validate it, and refuse stable ID collisions.

    Never chmod a pathname that could have been replaced by a symlink. Platforms
    without O_NOFOLLOW additionally compare the opened descriptor to lstat.
    """
    before = id_path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ProducerIdError("producer id must be a regular file, not a symlink")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(str(id_path), flags)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or (before.st_dev, before.st_ino) != (
            opened.st_dev, opened.st_ino,
        ):
            raise ProducerIdError("producer id file changed while opening")
        if os.name == "posix":
            if opened.st_uid != os.geteuid():
                raise ProducerIdError("producer id file is not owned by the current user")
            os.fchmod(fd, 0o600)
            if stat.S_IMODE(os.fstat(fd).st_mode) != 0o600:
                raise ProducerIdError("producer id permissions could not be secured")
        with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as stream:
            value = stream.read().strip()
    except UnicodeError as exc:
        raise ProducerIdError("producer id file is not valid UTF-8") from exc
    finally:
        os.close(fd)
    if not is_opaque_producer_id(value):
        raise ProducerIdError(
            f"producer id file {ID_FILE_NAME} is malformed; refusing to rotate it silently"
        )
    if value in sibling_ids:
        raise ProducerIdError("existing producer id collides with a sibling; refusing to rotate it silently")
    return value


def _publish_no_clobber(tmp_path: Path, id_path: Path) -> None:
    """Publish complete bytes without replacing a winner, or fail closed.

    Windows rename refuses an existing destination. POSIX rename/replace does
    not, so only hard-link publication is allowed there; unsupported filesystems
    must report identity unavailable instead of using an unsafe fallback.
    """
    try:
        if os.name == "nt":
            os.rename(str(tmp_path), str(id_path))
        else:
            os.link(str(tmp_path), str(id_path))
    except (AttributeError, NotImplementedError) as exc:
        raise ProducerIdError("atomic no-clobber identity publication is unavailable") from exc


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
            if os.name == "posix":
                os.fchmod(fd, 0o600)
            data = (candidate + "\n").encode("utf-8")
            while data:
                written = os.write(fd, data)
                if written <= 0:
                    raise ProducerIdError("producer id write made no progress")
                data = data[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            _publish_no_clobber(tmp_path, id_path)
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
    overwritten. Existing collisions also fail closed without rotating a stable
    identity; resolution requires explicit operator action.
    """
    id_path = Path(id_path)
    taken = sibling_producer_ids(id_path) if sibling_ids is None else sibling_ids
    try:
        return _read_existing(id_path, taken)
    except FileNotFoundError:
        pass
    id_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    for _ in range(_MAX_ATTEMPTS):
        candidate = ID_PREFIX + token_hex()
        if not is_opaque_producer_id(candidate) or candidate in taken:
            continue
        _write_producer_id_file(id_path, candidate)
        taken = sibling_producer_ids(id_path) if sibling_ids is None else sibling_ids
        return _read_existing(id_path, taken)
    raise ProducerIdError("could not draw a unique producer id")


def current_producer_id() -> str:
    """Return this worktree's identifier, or a fixed placeholder on any error.

    Coordination emit paths call this; identity problems must never crash them.
    """
    try:
        return load_or_create_producer_id(producer_id_path())
    except (ProducerIdError, OSError):
        return UNAVAILABLE_PRODUCER_ID
