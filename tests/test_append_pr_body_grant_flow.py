"""Hermetic append-pr-body.sh flow using fake gh (GH_BIN)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APPEND_SH = ROOT / "scripts/cursor/append-pr-body.sh"
GRANT_LIB = ROOT / "scripts/cursor/pr-body-grant-lib.py"

pytestmark = pytest.mark.unit


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
    gh = tmp_path / "gh"
    gh.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == pr && "$2" == view ]]; then
  printf '%s' "$(cat '{body_file}')"
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


def test_append_pr_body_consumes_grant(fake_gh: tuple[Path, Path], tmp_path: Path):
    gh_bin, body_file = fake_gh
    append = tmp_path / "note.md"
    append.write_text("operator note", encoding="utf-8")
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
