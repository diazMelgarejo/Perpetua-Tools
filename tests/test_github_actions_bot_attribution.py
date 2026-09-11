"""Regression coverage for repo-scoped GitHub Actions attribution."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "git"))
import audit_engine  # noqa: E402


REAL_POLICY = Path(__file__).resolve().parent.parent / "scripts" / "git" / "identity-policy.json"


def test_github_actions_bot_numeric_noreply_is_allowed_for_perpetua_tools() -> None:
    """GitHub's numeric noreply prefix must normalize to the scoped bot identity."""
    result = audit_engine.is_approved_identity(
        "github-actions[bot]",
        "41898282+github-actions[bot]@users.noreply.github.com",
        root=Path("."),
        repo_name="Perpetua-Tools",
        policy_path=REAL_POLICY,
        profile="audit_relaxed",
    )

    assert result.approved
    assert result.matched_kind == "repo_bot"


def test_unlisted_github_bot_remains_rejected_for_perpetua_tools() -> None:
    """The allowlist is exact; adding GitHub Actions must not create a bot wildcard."""
    result = audit_engine.is_approved_identity(
        "unlisted-automation[bot]",
        "12345+unlisted-automation[bot]@users.noreply.github.com",
        root=Path("."),
        repo_name="Perpetua-Tools",
        policy_path=REAL_POLICY,
        profile="audit_relaxed",
    )

    assert not result.approved
