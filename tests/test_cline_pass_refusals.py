"""ClinePass refusals distinguish unavailable models from unsupported fast mode."""

from datetime import datetime, timedelta, timezone

import pytest

from perpetua_tools.model_governance import (
    EscalationProof,
    LaunchSpec,
    ModelGovernanceError,
    assert_launch_allowed,
)


@pytest.mark.parametrize("with_proof", [False, True])
def test_listed_cline_fast_is_unsupported_even_with_proof(with_proof: bool) -> None:
    """A token cannot grant a transport mode that the listed route does not support."""
    spec = LaunchSpec("cline_pass", "muse-spark-1.3-contributor", effort="medium", fast=True)
    proof = EscalationProof(
        "control_plane_online_signer", "synthetic-reference", spec.launch_id,
        datetime.now(timezone.utc) + timedelta(minutes=1), effort="medium", fast=True,
        path="cline_pass",
    ) if with_proof else None
    with pytest.raises(ModelGovernanceError, match="fast mode is unsupported"):
        assert_launch_allowed(spec, proof=proof)


@pytest.mark.parametrize("fast", [False, True])
def test_unlisted_cline_model_reports_allowlist_refusal(fast: bool) -> None:
    """An unknown model remains an allowlist refusal regardless of its fast flag."""
    with pytest.raises(ModelGovernanceError, match="unlisted ClinePass model"):
        assert_launch_allowed(LaunchSpec("cline_pass", "unlisted-synthetic", effort="medium", fast=fast))
