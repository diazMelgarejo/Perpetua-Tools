"""Operator-controlled authority records never infer or create a ledger."""
import json
import os
from pathlib import Path
import subprocess

import pytest

from orchestrator.state_dir import _canonical_repo_state_dir

Authority = tuple[Path, Path, Path, Path, dict[str, object]]


@pytest.fixture
def authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Authority:
    """Prepare an external Git directory and a private reviewed record."""
    if os.name != "posix":
        pytest.skip("POSIX ownership and mode test")
    monkeypatch.delenv("PT_STATE_DIR", raising=False)
    checkout = tmp_path / "checkout"
    common = tmp_path / "meta" / ".git"
    common.parent.mkdir()
    subprocess.run(["git", "init", "-q", "--separate-git-dir", str(common), str(checkout)], check=True)
    ledger = tmp_path / "ledger"
    ledger.mkdir(mode=0o700)
    (ledger / "perpetua_core.db").write_bytes(b"existing")
    (ledger / "perpetua_core.db").chmod(0o600)
    private = tmp_path / "authority"
    private.mkdir(mode=0o700)
    record = private / "record.json"
    metadata_stat = common.stat()
    ledger_stat = ledger.stat()
    db_stat = (ledger / "perpetua_core.db").stat()
    data = {"schema_version": 1, "owner": str(os.getuid()), "git_common_dir": str(common.resolve()),
            "git_device": metadata_stat.st_dev, "git_inode": metadata_stat.st_ino,
            "ledger_dir": str(ledger.resolve()), "ledger_device": ledger_stat.st_dev,
            "ledger_inode": ledger_stat.st_ino, "db_device": db_stat.st_dev, "db_inode": db_stat.st_ino}
    record.write_text(json.dumps(data), encoding="utf-8")
    record.chmod(0o600)
    monkeypatch.setenv("PT_STATE_AUTHORITY_FILE", str(record))
    return checkout, common, ledger, record, data


def test_valid_record_is_read_only(authority: Authority) -> None:
    """Resolution does not create or mutate the record or the existing ledger."""
    checkout, _, ledger, record, _ = authority
    before = (record.read_bytes(), (ledger / "perpetua_core.db").read_bytes())
    assert _canonical_repo_state_dir(checkout) == ledger
    assert before == (record.read_bytes(), (ledger / "perpetua_core.db").read_bytes())


@pytest.mark.parametrize("field,value", [("owner", "forged"), ("git_inode", -1),
                                       ("ledger_inode", -1), ("db_inode", -1), ("git_common_dir", "/wrong"),
                                       ("schema_version", 2)])
def test_tampered_record_refused(authority: Authority, field: str, value: object) -> None:
    """An incorrect identity or schema cannot authorize a ledger."""
    checkout, _, _, record, data = authority
    data[field] = value
    record.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid or unprotected"):
        _canonical_repo_state_dir(checkout)


@pytest.mark.parametrize("target", ["record", "directory"])
def test_insecure_mode_refused(authority: Authority, target: str) -> None:
    """The record and its containing directory must both be private."""
    checkout, _, _, record, _ = authority
    (record if target == "record" else record.parent).chmod(0o755)
    with pytest.raises(RuntimeError, match="invalid or unprotected"):
        _canonical_repo_state_dir(checkout)


def test_symlink_record_refused(authority: Authority) -> None:
    """A record symlink is never followed."""
    checkout, _, _, record, _ = authority
    target = record.parent / "actual"
    record.rename(target)
    record.symlink_to(target)
    with pytest.raises(RuntimeError, match="invalid or unprotected"):
        _canonical_repo_state_dir(checkout)


def test_missing_authority_refuses_external_checkout(authority: Authority, monkeypatch: pytest.MonkeyPatch) -> None:
    """No record means no inferred ownership of an external .git directory."""
    checkout, _, _, _, _ = authority
    monkeypatch.delenv("PT_STATE_AUTHORITY_FILE")
    with pytest.raises(RuntimeError, match="requires a verified"):
        _canonical_repo_state_dir(checkout)


def test_missing_ledger_refused(authority: Authority) -> None:
    """A record cannot bootstrap a new ledger."""
    checkout, _, ledger, _, _ = authority
    (ledger / "perpetua_core.db").unlink()
    with pytest.raises(RuntimeError, match="invalid or unprotected"):
        _canonical_repo_state_dir(checkout)


def test_duplicate_record_keys_refused(authority: Authority) -> None:
    """Ambiguous duplicate keys cannot authorize a ledger."""
    checkout, _, _, record, _ = authority
    record.write_text('{"schema_version": 1, "schema_version": 1}')
    with pytest.raises(RuntimeError, match="invalid or unprotected"):
        _canonical_repo_state_dir(checkout)


def test_symlink_authority_directory_refused(authority: Authority, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Symlinks in ancestor components are not followed."""
    checkout, _, _, record, _ = authority
    alias = tmp_path / "alias"
    alias.symlink_to(record.parent, target_is_directory=True)
    monkeypatch.setenv("PT_STATE_AUTHORITY_FILE", str(alias / record.name))
    with pytest.raises(RuntimeError, match="invalid or unprotected"):
        _canonical_repo_state_dir(checkout)


def test_non_posix_record_verification_refused(authority: Authority, monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows does not inherit a POSIX ownership claim."""
    from orchestrator.state_dir import _verified_authority_file

    _, common, _, record, _ = authority
    with monkeypatch.context() as context:
        context.setattr(os, "name", "nt")
        with pytest.raises(RuntimeError, match="unavailable"):
            _verified_authority_file(str(record), common)


@pytest.mark.parametrize("target,mode", [("directory", 0o777), ("database", 0o644)])
def test_unprotected_ledger_refused(authority: Authority, target: str, mode: int) -> None:
    """An authority record cannot make writable or disclosed ledger storage safe."""
    checkout, _, ledger, _, _ = authority
    (ledger if target == "directory" else ledger / "perpetua_core.db").chmod(mode)
    with pytest.raises(RuntimeError, match="invalid or unprotected"):
        _canonical_repo_state_dir(checkout)


def test_fifo_record_refused_without_waiting(authority: Authority) -> None:
    """A non-regular record must be rejected before any blocking read or open."""
    checkout, _, _, record, _ = authority
    record.unlink()
    os.mkfifo(record, 0o600)
    with pytest.raises(RuntimeError, match="invalid or unprotected"):
        _canonical_repo_state_dir(checkout)


def test_hardlinked_record_refused(authority: Authority) -> None:
    """An extra name cannot silently retain authority after record retirement."""
    checkout, _, _, record, _ = authority
    os.link(record, record.parent / "alias.json")
    with pytest.raises(RuntimeError, match="invalid or unprotected"):
        _canonical_repo_state_dir(checkout)


def test_oversized_record_refused(authority: Authority) -> None:
    """A protected record remains subject to a bounded parser input size."""
    checkout, _, _, record, _ = authority
    record.write_bytes(b" " * 16385)
    with pytest.raises(RuntimeError, match="invalid or unprotected"):
        _canonical_repo_state_dir(checkout)
