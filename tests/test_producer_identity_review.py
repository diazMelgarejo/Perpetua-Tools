"""Security regressions for stable, private, no-clobber producer identities."""
from __future__ import annotations

import errno
import os
import stat
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from orchestrator.coordination import producer_identity as identity

FIRST = "ptp-" + "a" * 32
SECOND = "ptp-" + "b" * 32


def _git(cwd: Path, *args: str) -> str:
    """Run isolated fixture Git commands without inherited location overrides."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.check_output(
        ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", *args],
        cwd=cwd, env=env, text=True, stderr=subprocess.DEVNULL,
    ).strip()


@pytest.fixture
def worktrees(tmp_path: Path) -> tuple[Path, Path]:
    """Create a real repository and linked worktree with independent Git dirs."""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "commit", "--allow-empty", "-qm", "fixture")
    linked = tmp_path / "linked"
    _git(main, "worktree", "add", "-qb", "linked", str(linked))
    return main, linked


def test_discovery_ignores_stale_git_location_env(
    worktrees: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An inherited absolute Git location must not collapse two worktree IDs."""
    main, linked = worktrees
    main_dir = Path(_git(main, "rev-parse", "--absolute-git-dir"))
    linked_dir = Path(_git(linked, "rev-parse", "--absolute-git-dir"))
    monkeypatch.delenv("PT_PRODUCER_ID_FILE", raising=False)
    for key, value in {
        "GIT_DIR": main_dir, "GIT_WORK_TREE": main,
        "GIT_COMMON_DIR": main_dir, "GIT_INDEX_FILE": main_dir / "index",
    }.items():
        monkeypatch.setenv(key, str(value))
    monkeypatch.chdir(main)
    first = identity.current_producer_id()
    monkeypatch.chdir(linked)
    assert identity.producer_id_path() == linked_dir / identity.ID_FILE_NAME
    second = identity.current_producer_id()
    assert identity.is_opaque_producer_id(first)
    assert identity.is_opaque_producer_id(second)
    assert first != second
    assert first in identity.sibling_producer_ids(linked_dir / identity.ID_FILE_NAME)


@pytest.mark.parametrize("concurrent", [False, True])
def test_existing_and_winner_permissions_are_repaired(
    tmp_path: Path, concurrent: bool,
) -> None:
    """Both preexisting and racing winners become owner-only before return."""
    path = tmp_path / "id"

    def token() -> str:
        """Install a permissive racing winner before returning the losing draw."""
        path.write_text(FIRST + "\n", encoding="utf-8")
        path.chmod(0o644)
        return "b" * 32

    if not concurrent:
        token()
    assert identity.load_or_create_producer_id(path, token_hex=token) == FIRST
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("dangling", [False, True])
def test_symlink_identity_is_refused_without_touching_target(
    tmp_path: Path, dangling: bool,
) -> None:
    """Identity paths must never read, chmod, or overwrite symlink targets."""
    target = tmp_path / "target"
    if not dangling:
        target.write_text(FIRST, encoding="utf-8")
        target.chmod(0o644)
    path = tmp_path / "id"
    try:
        path.symlink_to(target)
    except OSError:
        if os.name == "nt":
            pytest.skip("symlink creation requires Windows account privileges")
        raise
    with pytest.raises((identity.ProducerIdError, OSError)):
        identity.load_or_create_producer_id(path)
    assert path.is_symlink()
    if not dangling:
        assert target.read_text(encoding="utf-8") == FIRST
        assert stat.S_IMODE(target.stat().st_mode) == 0o644
    else:
        assert not target.exists()


@pytest.mark.parametrize("concurrent", [False, True])
def test_existing_collision_is_preserved_and_refused(
    tmp_path: Path, concurrent: bool,
) -> None:
    """Stable or concurrent duplicate IDs fail closed without silent rotation."""
    path = tmp_path / "id"

    def token() -> str:
        """Create a colliding winner after the initial existence check."""
        path.write_text(FIRST + "\n", encoding="utf-8")
        return "b" * 32

    if not concurrent:
        token()
    with pytest.raises(identity.ProducerIdError):
        identity.load_or_create_producer_id(
            path, token_hex=token, sibling_ids=frozenset({FIRST}),
        )
    assert path.read_text(encoding="utf-8") == FIRST + "\n"


def test_unique_existing_identity_stays_stable(tmp_path: Path) -> None:
    """Sibling checking must not rotate a valid unique existing identity."""
    path = tmp_path / "id"
    path.write_text(FIRST + "\n", encoding="utf-8")
    assert identity.load_or_create_producer_id(path, sibling_ids=frozenset({SECOND})) == FIRST


@pytest.mark.parametrize("sibling", [False, True])
def test_invalid_utf8_is_unavailable_not_emission_failure(
    worktrees: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, sibling: bool,
) -> None:
    """Undecodable own or sibling data cannot escape the emission boundary."""
    main, linked = worktrees
    monkeypatch.delenv("PT_PRODUCER_ID_FILE", raising=False)
    monkeypatch.chdir(linked)
    own = identity.producer_id_path()
    corrupt = main / ".git" / identity.ID_FILE_NAME if sibling else own
    corrupt.write_bytes(b"\xff\xfe")
    assert identity.current_producer_id() == identity.UNAVAILABLE_PRODUCER_ID
    assert corrupt.read_bytes() == b"\xff\xfe"
    if sibling:
        assert not own.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX hard-link publication interleaving")
def test_synchronized_creators_converge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Creators publish only complete content and adopt the same atomic winner."""
    path = tmp_path / "id"
    barrier = Barrier(2)
    real_link = os.link

    def link(src: str, dst: str) -> None:
        """Force both fully written temporary files to reach publication together."""
        assert Path(src).read_text(encoding="utf-8") in (FIRST + "\n", SECOND + "\n")
        barrier.wait(timeout=10)
        real_link(src, dst)

    monkeypatch.setattr(identity.os, "link", link)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(identity.load_or_create_producer_id, path, token_hex=lambda: "a" * 32),
                   pool.submit(identity.load_or_create_producer_id, path, token_hex=lambda: "b" * 32)]
        results = [future.result(timeout=15) for future in futures]
    assert results[0] == results[1] == path.read_text(encoding="utf-8").strip()
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize("winner", [False, True])
@pytest.mark.skipif(os.name != "posix", reason="POSIX unsupported hard-link refusal")
def test_unsupported_link_fails_closed_without_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, winner: bool,
) -> None:
    """Unsupported links must never enter a racy exists-plus-replace fallback."""
    path = tmp_path / "id"

    def unsupported(src: str, dst: str) -> None:
        """Simulate an unsupported publication primitive, optionally after a winner."""
        if winner:
            Path(dst).write_text(FIRST, encoding="utf-8")
        raise OSError(errno.EOPNOTSUPP, "links unavailable")

    monkeypatch.setattr(identity.os, "link", unsupported)
    with pytest.raises((identity.ProducerIdError, OSError)):
        identity.load_or_create_producer_id(path)
    assert path.read_text(encoding="utf-8") == FIRST if winner else not path.exists()
    assert not list(tmp_path.glob(".*.tmp"))


def test_partial_writes_are_completed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Short writes must be retried before fsync and publication."""
    path = tmp_path / "id"
    real_write = os.write

    def short_write(fd: int, data: bytes) -> int:
        """Write at most three bytes to exercise the retry loop."""
        return real_write(fd, data[:3])

    monkeypatch.setattr(identity.os, "write", short_write)
    result = identity.load_or_create_producer_id(path)
    assert path.read_text(encoding="utf-8") == result + "\n"
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize("failure", ["write", "fsync", "zero"])
def test_failed_write_or_fsync_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    """Incomplete or unsynced candidates must never be published or left behind."""
    path = tmp_path / "id"

    def fail(*args: object) -> int:
        """Inject a storage failure or a non-progressing write."""
        if failure == "zero":
            return 0
        raise OSError(errno.EIO, "storage failure")

    monkeypatch.setattr(identity.os, "fsync" if failure == "fsync" else "write", fail)
    with pytest.raises((identity.ProducerIdError, OSError)):
        identity.load_or_create_producer_id(path)
    assert not path.exists()
    assert not list(tmp_path.glob(".*.tmp"))
