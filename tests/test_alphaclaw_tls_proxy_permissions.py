"""orchestrator/alphaclaw_tls_proxy.py -- cross-platform permission tests.

Companion plan: docs/next/2026-07-24-plan-windows-acl-alphaclaw-tls-proxy.md.

Windows ACL logic (_secure_path_win32) is tested here with a mocked
win32security so it runs on any CI runner. It has NOT been independently
verified against real Windows ACL behavior on actual hardware this
session -- see the plan doc's provenance note and the module docstring.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orchestrator import alphaclaw_tls_proxy as tls_proxy


@pytest.fixture
def mock_win32():
    """Provide a mock win32security/win32api/ntsecuritycon module set for
    testing Windows ACL logic on non-Windows platforms."""
    mock_con = MagicMock()
    mock_con.FILE_ALL_ACCESS = 0x1F01FF
    mock_con.FILE_DELETE_CHILD = 0x0040

    mock_win32 = MagicMock()
    mock_win32.ACL_REVISION = 2
    mock_win32.DACL_SECURITY_INFORMATION = 0x4
    mock_win32.SE_FILE_OBJECT = 1
    mock_win32.LookupAccountName = MagicMock(
        side_effect=lambda _, name: (f"SID-{name}", "DOMAIN", 1)
    )
    mock_win32.ConvertStringSidToSid = MagicMock(return_value="SID-Administrators")
    mock_win32.SetNamedSecurityInfo = MagicMock()

    mock_acl = MagicMock()
    mock_win32.ACL = MagicMock(return_value=mock_acl)

    mock_win32api = MagicMock(GetUserName=MagicMock(return_value="testuser"))

    with patch.object(tls_proxy, "win32security", mock_win32, create=True), \
         patch.object(tls_proxy, "win32api", mock_win32api, create=True), \
         patch.object(tls_proxy, "con", mock_con, create=True):
        yield mock_win32, mock_acl


def test_secure_path_win32_creates_allow_only_dacl(mock_win32):
    """Windows ACL path grants owner + Administrators only. An explicit
    DENY for Everyone must not be used -- the owner is in Everyone and
    deny ACEs take precedence over allow ACEs, which would lock the
    process out of its own cert/key files."""
    mock_sec, mock_acl = mock_win32
    test_path = Path("C:/test/key.pem")

    tls_proxy._secure_path_win32(test_path, is_directory=False)

    mock_acl.AddAccessDeniedAce.assert_not_called()
    assert mock_acl.AddAccessAllowedAce.call_count == 2
    mock_sec.ConvertStringSidToSid.assert_called_once_with("S-1-5-32-544")
    mock_sec.SetNamedSecurityInfo.assert_called_once()


def test_secure_path_win32_directory_includes_delete_child(mock_win32):
    """Directories get FILE_DELETE_CHILD folded into the access mask so
    the owner can still manage files created inside the restricted dir."""
    mock_sec, mock_acl = mock_win32
    test_path = Path("C:/test/certdir")

    tls_proxy._secure_path_win32(test_path, is_directory=True)

    # Every AddAccessAllowedAce call's access_mask argument (2nd positional)
    # must include the FILE_DELETE_CHILD bit for a directory.
    for call in mock_acl.AddAccessAllowedAce.call_args_list:
        access_mask = call.args[1]
        assert access_mask & 0x0040, "FILE_DELETE_CHILD bit missing for directory ACE"


def test_secure_path_dispatches_to_win32_when_available(mock_win32):
    """_secure_path() calls the win32 path when on Windows with pywin32
    available, not the icacls fallback."""
    with patch.object(tls_proxy, "_IS_WINDOWS", True), \
         patch.object(tls_proxy, "_WIN32_AVAILABLE", True), \
         patch.object(tls_proxy, "_secure_path_win32") as mock_win32_fn, \
         patch.object(tls_proxy, "_secure_path_icacls") as mock_icacls_fn:
        tls_proxy._secure_path(Path("C:/test/key.pem"), is_directory=False)

    mock_win32_fn.assert_called_once()
    mock_icacls_fn.assert_not_called()


def test_secure_path_falls_back_to_icacls_when_pywin32_unavailable():
    """_secure_path() falls back to the icacls subprocess path when
    pywin32 failed to import, rather than raising or silently no-op'ing."""
    with patch.object(tls_proxy, "_IS_WINDOWS", True), \
         patch.object(tls_proxy, "_WIN32_AVAILABLE", False), \
         patch.object(tls_proxy, "_secure_path_win32") as mock_win32_fn, \
         patch.object(tls_proxy, "_secure_path_icacls") as mock_icacls_fn:
        tls_proxy._secure_path(Path("C:/test/key.pem"), is_directory=False)

    mock_icacls_fn.assert_called_once()
    mock_win32_fn.assert_not_called()


def test_secure_path_icacls_builds_expected_command():
    """The icacls fallback uses allow-only grants after /inheritance:r.
    It must not /deny Everyone -- that would lock the owner out."""
    with patch("subprocess.run") as mock_run, \
         patch("getpass.getuser", return_value="testuser"):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        tls_proxy._secure_path_icacls(Path("/test/certdir"), is_directory=True)

    cmd = mock_run.call_args.args[0]
    assert cmd[0] == "icacls"
    assert "/inheritance:r" in cmd
    assert "/deny" not in cmd
    assert any("testuser" in c and "(OI)(CI)(F)" in c for c in cmd)
    assert any("S-1-5-32-544" in c and "(OI)(CI)(F)" in c for c in cmd)


def test_secure_path_icacls_logs_warning_on_failure(caplog):
    """A non-zero icacls exit is logged as a warning, not raised or
    silently swallowed -- operators need to know the fallback failed."""
    with patch("subprocess.run") as mock_run, \
         patch("getpass.getuser", return_value="testuser"):
        mock_run.return_value = MagicMock(returncode=1, stderr="Access is denied.")
        with caplog.at_level("WARNING"):
            tls_proxy._secure_path_icacls(Path("/test/key.pem"), is_directory=False)

    assert any("icacls failed" in rec.message for rec in caplog.records)


def test_secure_path_posix_sets_correct_mode(tmp_path):
    """POSIX path sets 0o600 for files, 0o700 for dirs."""
    test_file = tmp_path / "key.pem"
    test_file.write_text("test key")

    with patch.object(tls_proxy, "_IS_WINDOWS", False):
        tls_proxy._secure_path(test_file, is_directory=False)

    mode = test_file.stat().st_mode & 0o777
    assert mode == 0o600, f"Expected 0o600, got 0o{mode:o}"


def test_secure_path_posix_sets_correct_mode_for_directory(tmp_path):
    test_dir = tmp_path / "certdir"
    test_dir.mkdir()

    with patch.object(tls_proxy, "_IS_WINDOWS", False):
        tls_proxy._secure_path(test_dir, is_directory=True)

    mode = test_dir.stat().st_mode & 0o777
    assert mode == 0o700, f"Expected 0o700, got 0o{mode:o}"
