"""Tests for the explicit cross-repository endpoint-policy stack resolver."""
from __future__ import annotations

import importlib.util
from pathlib import Path


_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "review"
    / "resolve_orama_policy_ref.py"
)
_SPEC = importlib.util.spec_from_file_location("resolve_orama_policy_ref", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_PT_BRANCH = "fix/pt-pipeline-endpoint-tls-20260917"
_ORAMA_PEER_BRANCH = "cursor/tiered-pipeline-runtime-fb76"


def test_open_peer_pull_uses_orama_branch_not_pt_name() -> None:
    """A declared open stack selects its peer branch rather than the PT branch."""
    assert (
        _MODULE.resolve_orama_policy_ref(_PT_BRANCH, pull_merged=False)
        == _ORAMA_PEER_BRANCH
    )


def test_quoted_ci_head_ref_still_matches_stack_key() -> None:
    """Quoted CI input resolves to the same declared stack key."""
    quoted = f'"{_PT_BRANCH}"'
    resolution = _MODULE.resolve_orama_policy_stack(quoted, pull_merged=False)
    assert resolution.head_ref == _PT_BRANCH
    assert resolution.peer_ref == _ORAMA_PEER_BRANCH
    assert resolution.declared is True
    assert resolution.source == "open-pr"


def test_merged_peer_pull_uses_main() -> None:
    """A merged peer switches the declared stack to main."""
    resolution = _MODULE.resolve_orama_policy_stack(_PT_BRANCH, pull_merged=True)
    assert resolution.peer_ref == "main"
    assert resolution.declared is True
    assert resolution.merged is True
    assert resolution.source == "merged-main"


def test_uses_same_named_ref_when_no_stack_is_declared() -> None:
    """Undeclared stacks retain same-name resolution without a guessed mapping."""
    resolution = _MODULE.resolve_orama_policy_stack("feature/shared-policy")
    assert resolution.peer_ref == "feature/shared-policy"
    assert resolution.declared is False
    assert resolution.source == "same-named-ref"


def test_records_live_orama_pr_363_peer_equivalents() -> None:
    """Historical explicit peer metadata remains available after new stack entries."""
    data = _MODULE.load_policy_stacks()
    entry = data["orama_system_refs"][_PT_BRANCH]
    assert entry["peer_ref"] == _ORAMA_PEER_BRANCH
    assert entry["peer_pull"] == 363
    assert entry["equivalents"] == ["refs/pull/363/head"]


def test_github_output_writes_unquoted_peer_ref(tmp_path: Path) -> None:
    """GitHub output contains clean resolver fields rather than JSON quoting."""
    output = tmp_path / "github_output"
    resolution = _MODULE.resolve_orama_policy_stack(_PT_BRANCH, pull_merged=False)
    _MODULE.write_github_output(resolution, str(output))
    text = output.read_text(encoding="utf-8")
    assert "peer_ref=cursor/tiered-pipeline-runtime-fb76\n" in text
    assert "declared=true\n" in text
    assert "source=open-pr\n" in text
    assert '"' not in text


def test_windows_process_stack_selects_peer_with_shared_win_exec() -> None:
    """PT #475 selects Orama #464 while keeping missing-file parity fail-closed."""
    branch = "2026-11-02-001-windows-process-and-acl-hardening"
    resolution = _MODULE.resolve_orama_policy_stack(branch, pull_merged=False)
    assert resolution.peer_ref == "2026-10-27-004-windows-process-hygiene"
    assert resolution.declared is True
    entry = _MODULE.load_policy_stacks()["orama_system_refs"][branch]
    assert entry["peer_pull"] == 464
    assert entry["equivalents"] == ["refs/pull/464/head"]
    assert _MODULE.resolve_orama_policy_stack(branch, pull_merged=True).peer_ref == "main"
