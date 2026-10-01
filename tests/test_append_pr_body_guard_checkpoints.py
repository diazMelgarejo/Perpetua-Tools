"""Runtime-proven coverage of append-pr-body.sh's integrity checkpoints.

Additive companion to test_append_pr_body_grant_flow.py, which keeps its own
two scenarios unchanged. This module adds what that file cannot currently
prove: that each integrity guard is reached by an *executed* scenario, with
the observed transport behaviour asserted, not merely that an error string
appears somewhere in a source file.

Design follows two independent audit reviews of an earlier, rejected plan.
That plan proposed enumerating guard codes from the shell script and checking
each code appeared somewhere in the test file's *source text*. Both audits
rejected it for the same reason, and they were right: a source scan is
satisfied by a comment, an `if False:` block, a skipped test, the scanning
regex seeing itself, or a test that asserts the code after some *other* guard
short-circuited the run. None of those prove a guard works. Worse, deriving
the required set from the script makes deletion invisible -- remove a guard
and the requirement silently shrinks, reporting success exactly when it
should demand review.

So the contract here is inverted and split in two:

1. REQUIRED_CHECKPOINTS below is an explicit, hand-maintained manifest. It is
   the policy surface. Removing an entry must be a deliberate, reviewed code
   change with a rationale -- never an incidental set subtraction.
2. Each manifest entry is proven by a real subprocess run against a fake
   transport that records an event ledger (view count, edit attempts, what
   was actually persisted). Tests assert the guard code reached *and* the
   observed behaviour -- notably that a stale-detection failure performed
   ZERO edits, which is the property that actually matters and which no
   source scan can establish.

A separate structural test compares the manifest against the codes the script
really implements, failing on addition *and* deletion. It is a supplement to
the runtime proofs, never a substitute.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APPEND_SH = ROOT / "scripts/cursor/append-pr-body.sh"
GRANT_LIB = ROOT / "scripts/cursor/pr-body-grant-lib.py"

pytestmark = pytest.mark.integration

CURSOR_END = "<!-- CURSOR_AGENT_PR_BODY_END -->"
ORIGINAL_BODY = f"## Summary\n\noriginal operator summary\n{CURSOR_END}"


@dataclass(frozen=True)
class GuardScenario:
    """One executable proof that a named guard is genuinely reachable."""

    expected_code: str
    # Mutate the remote body immediately BEFORE emitting this view call's
    # response. The ordinal is a fixture implementation detail; the test
    # names and assertions describe the boundary event, never "view 3".
    mutate_before_view: int | None = None
    # "normal" persists what it was handed; "corrupt" persists something else.
    edit_mode: str = "normal"
    expected_edit_count: int = 0


REQUIRED_CHECKPOINTS: dict[str, GuardScenario] = {
    "PR_BODY_E_STALE_ON_REREAD": GuardScenario(
        expected_code="PR_BODY_E_STALE_ON_REREAD",
        mutate_before_view=2,
        expected_edit_count=0,
    ),
    "PR_BODY_E_STALE_PREWRITE": GuardScenario(
        expected_code="PR_BODY_E_STALE_PREWRITE",
        mutate_before_view=3,
        expected_edit_count=0,
    ),
    "PR_BODY_E_POSTWRITE_MISMATCH": GuardScenario(
        expected_code="PR_BODY_E_POSTWRITE_MISMATCH",
        edit_mode="corrupt",
        expected_edit_count=1,
    ),
}


def _run(
    cmd: list[str], env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        cmd, cwd=ROOT, env=merged, text=True, capture_output=True, check=False
    )


@pytest.fixture()
def ledgered_gh(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Fake gh that records an event ledger and supports scripted mutation.

    Records one line per transport event so tests can assert what actually
    happened: view:N for each read, edit_attempt / edit_commit for writes.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    body_file = tmp_path / "remote_body.txt"
    body_file.write_text(ORIGINAL_BODY, encoding="utf-8")
    ledger = tmp_path / "ledger.txt"
    ledger.write_text("", encoding="utf-8")
    count_file = tmp_path / "view_count.txt"
    count_file.write_text("0", encoding="utf-8")

    gh = bin_dir / "gh"
    gh.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == pr && "$2" == view ]]; then
  count=$(cat '{count_file}')
  count=$((count + 1))
  printf '%s' "$count" > '{count_file}'
  printf 'view:%s\\n' "$count" >> '{ledger}'
  if [[ -n "${{FAKE_GH_MUTATE_BEFORE_VIEW:-}}" \\
        && "$count" == "${{FAKE_GH_MUTATE_BEFORE_VIEW}}" ]]; then
    printf '%s\\n' 'remote_mutation' >> '{ledger}'
    printf '%s' '## Summary

concurrent operator edit
{CURSOR_END}' > '{body_file}'
  fi
  cat '{body_file}'
  printf '\\n'
  exit 0
fi
if [[ "$1" == pr && "$2" == edit ]]; then
  printf '%s\\n' 'edit_attempt' >> '{ledger}'
  body_path=""
  while [[ $# -gt 0 ]]; do
    if [[ "$1" == --body-file ]]; then body_path="$2"; shift 2; continue; fi
    shift
  done
  if [[ "${{FAKE_GH_EDIT_MODE:-normal}}" == corrupt ]]; then
    printf '%s' 'corrupted by transport' > '{body_file}'
  else
    printf '%s' "$(cat "$body_path")" > '{body_file}'
  fi
  printf '%s\\n' 'edit_commit' >> '{ledger}'
  exit 0
fi
exit 0
""",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    return gh, body_file, ledger


def _mint_grant(gh_bin: Path, append: Path, tmp_path: Path) -> dict[str, str]:
    env = {
        "PR_BODY_GRANT_HMAC_SECRET": "ledger-secret",
        "GH_BIN": str(gh_bin),
        "HOME": str(tmp_path),
    }
    mint = _run(
        [
            "python3", str(GRANT_LIB), "mint",
            "--repo", "owner/repo", "--pr", "99", "--file", str(append),
        ],
        env=env,
    )
    assert mint.returncode == 0, mint.stderr
    return env


@pytest.mark.parametrize(
    "code", sorted(REQUIRED_CHECKPOINTS), ids=sorted(REQUIRED_CHECKPOINTS)
)
def test_required_integrity_checkpoint_is_reachable_at_runtime(
    code: str, ledgered_gh: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Each manifest checkpoint is proven by a real run, not a source scan.

    Asserts three independent facts per scenario: the guard's trace records
    that exact code (and only it), the process failed, and the transport
    ledger shows the expected number of edits -- zero for stale detection,
    which is the property that actually protects the remote body.
    """
    scenario = REQUIRED_CHECKPOINTS[code]
    gh_bin, _body_file, ledger = ledgered_gh
    append = tmp_path / "note.md"
    append.write_text("operator note", encoding="utf-8")
    env = _mint_grant(gh_bin, append, tmp_path)

    trace = tmp_path / "guard_trace.txt"
    env["PR_BODY_GUARD_TRACE_FILE"] = str(trace)
    env["FAKE_GH_EDIT_MODE"] = scenario.edit_mode
    if scenario.mutate_before_view is not None:
        env["FAKE_GH_MUTATE_BEFORE_VIEW"] = str(scenario.mutate_before_view)

    proc = _run(
        [
            "bash", str(APPEND_SH), "owner/repo", "99",
            "--file", str(append), "--title", "Follow-up: test",
        ],
        env=env,
    )

    assert proc.returncode != 0, f"guard {code} did not fail the run: {proc.stdout}"

    traced = trace.read_text(encoding="utf-8").split() if trace.exists() else []
    assert traced == [scenario.expected_code], (
        f"expected exactly one guard event {scenario.expected_code!r}, "
        f"got {traced!r}. A different guard short-circuited this scenario, "
        f"so it does not prove {code} is reachable."
    )

    events = ledger.read_text(encoding="utf-8").split()
    edits = events.count("edit_attempt")
    assert edits == scenario.expected_edit_count, (
        f"expected {scenario.expected_edit_count} edit attempt(s), saw {edits}. "
        f"ledger={events!r}"
    )


def test_stale_detection_leaves_the_remote_body_untouched(
    ledgered_gh: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """The point of the pre-write guards is not the error message -- it is
    that the operator's concurrent edit survives. Asserted directly on the
    fake remote's final content, independently of any guard code."""
    gh_bin, body_file, ledger = ledgered_gh
    append = tmp_path / "note.md"
    append.write_text("operator note", encoding="utf-8")
    env = _mint_grant(gh_bin, append, tmp_path)
    env["FAKE_GH_MUTATE_BEFORE_VIEW"] = "3"

    proc = _run(
        [
            "bash", str(APPEND_SH), "owner/repo", "99",
            "--file", str(append), "--title", "Follow-up: test",
        ],
        env=env,
    )

    assert proc.returncode != 0
    remote = body_file.read_text(encoding="utf-8")
    assert "concurrent operator edit" in remote
    assert "operator note" not in remote
    assert "edit_attempt" not in ledger.read_text(encoding="utf-8")


def test_manifest_and_implementation_agree_in_both_directions() -> None:
    """Structural supplement to the runtime proofs above -- never a substitute.

    Fails on ADDITION (a new guard code ships with no required scenario) and
    on DELETION (a required checkpoint disappears from the script). The
    deletion direction is the one a script-derived registry cannot provide:
    if the script were the source of truth, removing a guard would silently
    shrink the requirement and report success.
    """
    script = APPEND_SH.read_text(encoding="utf-8")
    implemented = set(re.findall(r"guard_trace (PR_BODY_E_[A-Z_]+)", script))
    required = set(REQUIRED_CHECKPOINTS)

    assert implemented == required, (
        f"manifest/implementation drift.\n"
        f"  implemented but not required: {sorted(implemented - required)}\n"
        f"  required but not implemented: {sorted(required - implemented)}\n"
        "Adding a guard requires adding a runtime scenario above. Removing "
        "one requires a deliberate manifest change with a rationale."
    )


def test_postwrite_mismatch_does_not_release_the_grant_reservation(
    ledgered_gh: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """A real gap, demonstrated by an independent review before this fix:
    mark-applied previously ran AFTER post-write verification, so a write
    that succeeded but then failed that verification never recorded
    remote_applied -- leaving the exit trap's own release path free to
    delete the reservation despite a write having genuinely landed,
    permitting replay. Proven here by reading the actual nonce-state file
    a real run produces, not by inspecting the script's control flow."""
    import json as jsonlib

    gh_bin, body_file, ledger = ledgered_gh
    append = tmp_path / "note.md"
    append.write_text("operator note", encoding="utf-8")
    env = _mint_grant(gh_bin, append, tmp_path)
    env["FAKE_GH_EDIT_MODE"] = "corrupt"

    proc = _run(
        [
            "bash", str(APPEND_SH), "owner/repo", "99",
            "--file", str(append), "--title", "Follow-up: test",
        ],
        env=env,
    )

    assert proc.returncode != 0

    state_path = tmp_path / ".cursor" / "pr-body-grant-nonces.json"
    assert state_path.is_file(), "expected a nonce-state file after a write attempt"
    state = jsonlib.loads(state_path.read_text(encoding="utf-8"))
    reservations = state.get("reservations", {})
    assert reservations, (
        "reservation was deleted after a write that genuinely reached the "
        "remote -- this permits replay of the same grant"
    )
    (entry,) = reservations.values()
    assert entry.get("remote_applied") is True, (
        "remote_applied was not recorded before the post-write mismatch "
        "failure could exit the script"
    )


def test_merge_preserves_meaningful_trailing_newlines(
    ledgered_gh: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Only the fake `gh --jq` presentation LF may be removed.

    The stored body ends in two meaningful LFs. The old command-substitution
    path removed both, so this exact-byte assertion is a regression test for
    the data-loss report, independent of the stale-write checkpoint tests.
    """
    gh_bin, body_file, _ledger = ledgered_gh
    original = b"## Summary\n\nhistorical body\n\n"
    body_file.write_bytes(original)
    append = tmp_path / "note.md"
    append.write_bytes(b"operator note")
    env = _mint_grant(gh_bin, append, tmp_path)

    proc = _run(
        [
            "bash", str(APPEND_SH), "owner/repo", "99",
            "--file", str(append), "--title", "Follow-up: test",
        ],
        env=env,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert body_file.read_bytes() == (
        original + b"\n\n## Follow-up: test\n\noperator note"
    )
