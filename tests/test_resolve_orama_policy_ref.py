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


def test_resolves_declared_pt_to_orama_stack_ref() -> None:
    assert (
        _MODULE.resolve_orama_policy_ref("fix/pt-pipeline-endpoint-tls-20260917")
        == "refs/pull/363/head"
    )


def test_uses_same_named_ref_when_no_stack_is_declared() -> None:
    assert _MODULE.resolve_orama_policy_ref("feature/shared-policy") == "feature/shared-policy"


def test_records_live_orama_pr_363_peer_equivalents() -> None:
    """Checkout uses refs/pull/363/head; the open PR branch is recorded as equivalent."""
    data = _MODULE.load_policy_stacks()
    assert data["orama_system_refs"]["fix/pt-pipeline-endpoint-tls-20260917"] == (
        "refs/pull/363/head"
    )
    assert data["orama_system_peer_equivalents"]["refs/pull/363/head"] == [
        "cursor/tiered-pipeline-runtime-fb76"
    ]
