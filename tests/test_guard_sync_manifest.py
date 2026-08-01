"""Guard sync manifest — single source of truth for attribution guard distribution."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GIT = ROOT / "scripts" / "git"
MANIFEST = GIT / "guard-sync-manifest.sh"
SYNC = GIT / "sync-attribution-guard-scripts.sh"
VERIFY = GIT / "verify-guard-parity.sh"


def _extract_sync_binding_pattern() -> str:
    """Pull the actual grep -Eq pattern out of verify-guard-parity.sh's own
    SYNC BINDING check, rather than hardcoding a copy of it here. A
    hardcoded literal doesn't change when the production pattern does --
    this test would keep passing (or failing) against a stale definition
    while a real regression in the production check goes undetected.
    Reading it from the source means drift between the two is impossible
    by construction: there is only one pattern, extracted at test time."""
    text = VERIFY.read_text(encoding="utf-8")
    match = re.search(
        r"grep -Eq '(\^\[\[:space:\]\].*guard-sync-manifest\\\.sh)'",
        text,
    )
    assert match, (
        "could not find the SYNC BINDING grep pattern in "
        f"{VERIFY} -- verify-guard-parity.sh's check may have been "
        "rewritten in a way this extraction no longer matches"
    )
    return match.group(1)


_SYNC_BINDING_PATTERN = _extract_sync_binding_pattern()


def _run_sync_binding_check(sync_script: Path) -> subprocess.CompletedProcess[str]:
    """Same grep as verify-guard-parity.sh SYNC BINDING check."""
    return subprocess.run(
        ["grep", "-Eq", _SYNC_BINDING_PATTERN, str(sync_script)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _bash_array(name: str) -> list[str]:
    result = subprocess.run(
        [
            "bash",
            "-c",
            f'source "$1" && printf "%s\\n" "${{{name}[@]}}"',
            "_",
            str(MANIFEST),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


@pytest.mark.unit
def test_manifest_files_exist_on_disk() -> None:
    all_paths = _bash_array("GUARD_SYNC_EXECUTABLES") + _bash_array("GUARD_SYNC_DATA_FILES")
    missing = [rel for rel in all_paths if not (GIT / rel).is_file()]
    assert not missing, f"manifest lists missing files: {missing}"


@pytest.mark.unit
def test_parity_required_expands_in_bash() -> None:
    """GUARD_PARITY_REQUIRED is assembled at source time from the two sync arrays."""
    parity = _bash_array("GUARD_PARITY_REQUIRED")
    expected = set(_bash_array("GUARD_SYNC_EXECUTABLES")) | set(
        _bash_array("GUARD_SYNC_DATA_FILES")
    )
    assert set(parity) == expected


@pytest.mark.unit
def test_sync_and_verify_source_manifest() -> None:
    pattern = r'^\s*(source|\.)\s+.*guard-sync-manifest\.sh'
    for script in (SYNC, VERIFY):
        body = script.read_text(encoding="utf-8")
        assert re.search(pattern, body, re.MULTILINE), (
            f"{script.name} must source guard-sync-manifest.sh via an uncommented command"
        )


@pytest.mark.unit
def test_verify_rejects_comment_only_manifest_reference(tmp_path: Path) -> None:
    """Comment-only 'source guard-sync-manifest.sh' must not satisfy the binding check."""
    fake_sync = tmp_path / "sync-attribution-guard-scripts.sh"
    fake_sync.write_text(
        "# source guard-sync-manifest.sh\n",
        encoding="utf-8",
    )
    fake_result = _run_sync_binding_check(fake_sync)
    assert fake_result.returncode != 0, (
        "production binding grep must reject comment-only manifest reference"
    )
    real_result = _run_sync_binding_check(SYNC)
    assert real_result.returncode == 0, (
        "canonical sync-attribution-guard-scripts.sh must satisfy binding check"
    )


@pytest.mark.unit
def test_verify_guard_parity_passes_in_canonical_repo() -> None:
    result = subprocess.run(
        ["bash", str(VERIFY)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
