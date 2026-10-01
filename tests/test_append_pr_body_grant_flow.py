"""Hermetic append-pr-body.sh flow using fake gh (GH_BIN)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APPEND_SH = ROOT / "scripts/cursor/append-pr-body.sh"
GRANT_LIB = ROOT / "scripts/cursor/pr-body-grant-lib.py"

pytestmark = pytest.mark.integration


def _run(cmd: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        cmd,
        cwd=ROOT,
        env=merged,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.fixture()
def fake_gh(tmp_path: Path) -> tuple[Path, Path]:
    body_file = tmp_path / "pr-body.txt"
    body_file.write_text("summary\n<!-- CURSOR_AGENT_PR_BODY_END -->\n", encoding="utf-8")
    view_count_file = tmp_path / "view-count.txt"
    view_count_file.write_text("0", encoding="utf-8")
    gh = tmp_path / "gh"
    gh.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == pr && "$2" == view ]]; then
  count=$(cat '{view_count_file}')
  count=$((count + 1))
  printf '%s' "$count" > '{view_count_file}'
  if [[ "${{FAKE_GH_CONCURRENT_AFTER_SECOND_VIEW:-0}}" == 1 && "$count" == 2 ]]; then
    printf '%s\n' 'summary' 'concurrent operator edit' '<!-- CURSOR_AGENT_PR_BODY_END -->' > '{body_file}'
  fi
  if [[ -n "${{FAKE_GH_MUTATE_APPEND_FILE_ON_SECOND_VIEW:-}}" && "$count" == 2 ]]; then
    printf '%s' 'changed after snapshot' > "$FAKE_GH_MUTATE_APPEND_FILE_ON_SECOND_VIEW"
  fi
  cat '{body_file}'
  printf '\\n'
  exit 0
fi
if [[ "$1" == pr && "$2" == edit ]]; then
  shift 2
  body_path=""
  while [[ $# -gt 0 ]]; do
    if [[ "$1" == --body-file ]]; then
      body_path="$2"
      break
    fi
    shift
  done
  [[ -n "$body_path" ]] || {{ echo "fake gh: no --body-file" >&2; exit 1; }}
  cat "$body_path" > '{body_file}'
  exit 0
fi
echo "unexpected gh: $@" >&2
exit 1
""",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    return gh, body_file


def _mint_grant(gh_bin: Path, append: Path, tmp_path: Path) -> dict[str, str]:
    env = {
        "PR_BODY_GRANT_HMAC_SECRET": "append-flow-secret",
        "GH_BIN": str(gh_bin),
        "HOME": str(tmp_path),
    }
    mint = _run(
        [
            "python3",
            str(GRANT_LIB),
            "mint",
            "--repo",
            "owner/repo",
            "--pr",
            "99",
            "--file",
            str(append),
        ],
        env=env,
    )
    assert mint.returncode == 0, mint.stderr
    return env


def test_append_pr_body_consumes_grant(
    fake_gh: tuple[Path, Path], tmp_path: Path
) -> None:
    gh_bin, body_file = fake_gh
    append = tmp_path / "note.md"
    append.write_text("operator note", encoding="utf-8")
    env = _mint_grant(gh_bin, append, tmp_path)

    ack_path = tmp_path / ".cursor" / "pr-body-human-override-ack"
    assert ack_path.is_file()

    proc = _run(
        [
            "bash",
            str(APPEND_SH),
            "owner/repo",
            "99",
            "--file",
            str(append),
            "--title",
            "Follow-up: test",
        ],
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "updated:" in proc.stdout

    remote_body = body_file.read_text(encoding="utf-8")
    assert "## Follow-up: test" in remote_body
    assert "operator note" in remote_body

    consume_check = _run(
        [
            "python3",
            str(GRANT_LIB),
            "verify",
            "--repo",
            "owner/repo",
            "--pr",
            "99",
            "--file",
            str(append),
        ],
        env=env,
    )
    assert consume_check.returncode != 0


def test_append_pr_body_rejects_change_detected_on_reread(
    fake_gh: tuple[Path, Path], tmp_path: Path
) -> None:
    """The fake gh's concurrent-edit hook applies before the view response is
    emitted, so the script's own second view call (the first re-comparison
    against the initial read) sees the already-edited body immediately --
    not a later, separate pre-write recheck. Verified directly: an earlier
    fixture ordering (mutate after emitting the stale response) deferred
    visibility to a third call and a different error message; this ordering
    was confirmed empirically before choosing this test's name and
    assertions, not assumed from the fixture's own intent."""
    gh_bin, body_file = fake_gh
    append = tmp_path / "note.md"
    append.write_text("operator note", encoding="utf-8")
    env = _mint_grant(gh_bin, append, tmp_path)
    env["FAKE_GH_CONCURRENT_AFTER_SECOND_VIEW"] = "1"

    proc = _run(
        [
            "bash",
            str(APPEND_SH),
            "owner/repo",
            "99",
            "--file",
            str(append),
            "--title",
            "Follow-up: test",
        ],
        env=env,
    )

    assert proc.returncode != 0
    assert "changed since initial read" in proc.stderr
    remote_body = body_file.read_text(encoding="utf-8")
    assert "concurrent operator edit" in remote_body
    assert "operator note" not in remote_body


def test_append_pr_body_uses_one_immutable_append_snapshot(
    fake_gh: tuple[Path, Path], tmp_path: Path
) -> None:
    """Every grant lifecycle operation must use the payload snapshot made at entry."""
    gh_bin, body_file = fake_gh
    append = tmp_path / "note.md"
    append.write_text("authorized snapshot", encoding="utf-8")
    env = _mint_grant(gh_bin, append, tmp_path)
    env["FAKE_GH_MUTATE_APPEND_FILE_ON_SECOND_VIEW"] = str(append)

    proc = _run(
        ["bash", str(APPEND_SH), "owner/repo", "99", "--file", str(append)],
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    remote_body = body_file.read_text(encoding="utf-8")
    assert "authorized snapshot" in remote_body
    assert "changed after snapshot" not in remote_body


def test_append_pr_body_rejects_oversized_file_before_snapshot(
    fake_gh: tuple[Path, Path], tmp_path: Path
) -> None:
    """An oversized source must fail before any unbounded temporary copy."""
    gh_bin, body_file = fake_gh
    append = tmp_path / "too-large.md"
    append.write_bytes(b"x" * ((1024 * 1024) + 1))
    original_body = body_file.read_bytes()

    proc = _run(
        ["bash", str(APPEND_SH), "owner/repo", "99", "--file", str(append)],
        env={"GH_BIN": str(gh_bin), "HOME": str(tmp_path)},
    )

    assert proc.returncode != 0
    assert "exceeds size limit" in proc.stderr
    assert body_file.read_bytes() == original_body
