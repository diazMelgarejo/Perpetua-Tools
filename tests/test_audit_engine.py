"""Phase 1 tests for scripts/git/audit_engine.py.

Covers a focused subset of docs/plans/2026-07-24-unified-identity-audit-
integrated-plan.md section 9.1's full test list -- Phase 1 scope is the
engine itself, not the wrapper integration (Phase 2, not yet done).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "git"))
import audit_engine  # noqa: E402


REAL_POLICY = Path(__file__).resolve().parent.parent / "scripts" / "git" / "identity-policy.json"


def test_real_policy_file_loads_and_validates():
    """The actual tracked policy file must load without error."""
    policy = audit_engine.load_policy(REAL_POLICY)
    assert policy["version"] == 1


def test_exact_human_identity_approved():
    result = audit_engine.is_approved_identity(
        "cyre", "lawrence@cyre.me", root=Path("."), policy_path=REAL_POLICY
    )
    assert result.approved
    assert result.matched_kind == "human"


def test_explicit_gmail_alias_approved():
    result = audit_engine.is_approved_identity(
        "cyre", "lawrence.melgarejo@gmail.com", root=Path("."), policy_path=REAL_POLICY
    )
    assert result.approved
    assert result.matched_kind == "human_alias"


def test_wrong_name_with_approved_email_rejected():
    """Name-bound: the email alone isn't sufficient."""
    result = audit_engine.is_approved_identity(
        "someone else", "lawrence@cyre.me", root=Path("."), policy_path=REAL_POLICY
    )
    assert not result.approved


def test_exact_agent_identity_approved():
    result = audit_engine.is_approved_identity(
        "Codex", "codex@openai.com", root=Path("."), policy_path=REAL_POLICY
    )
    assert result.approved
    assert result.matched_kind == "agent"


def test_disallowed_agent_name_rejected():
    result = audit_engine.is_approved_identity(
        "Not Codex", "codex@openai.com", root=Path("."), policy_path=REAL_POLICY
    )
    assert not result.approved


def test_repo_scoped_bot_approved_in_correct_repo():
    result = audit_engine.is_approved_identity(
        "cursor[bot]", "cursor[bot]@users.noreply.github.com",
        root=Path("."), repo_name="orama-system", policy_path=REAL_POLICY,
    )
    assert result.approved
    assert result.matched_kind == "repo_bot"


def test_bot_approved_in_one_repo_rejected_in_another():
    """A bot scoped to orama-system must NOT be silently approved for PT."""
    result = audit_engine.is_approved_identity(
        "cursor[bot]", "cursor[bot]@users.noreply.github.com",
        root=Path("."), repo_name="Perpetua-Tools", policy_path=REAL_POLICY,
    )
    assert not result.approved


@pytest.mark.unit
def test_repo_scoped_bot_approved_with_github_numeric_prefix() -> None:
    """GitHub prefixes bot noreply emails with '<id>+' — normalize before matching policy."""
    result = audit_engine.is_approved_identity(
        "cursor[bot]", "206951365+cursor[bot]@users.noreply.github.com",
        root=Path("."), repo_name="orama-system", policy_path=REAL_POLICY,
        profile="audit_relaxed",
    )
    assert result.approved
    assert result.matched_kind == "repo_bot"


def test_unknown_github_bot_rejected():
    """No universal *[bot]@users.noreply.github.com wildcard."""
    result = audit_engine.is_approved_identity(
        "some-random[bot]", "some-random[bot]@users.noreply.github.com",
        root=Path("."), repo_name="orama-system", policy_path=REAL_POLICY,
    )
    assert not result.approved


def test_vendor_domain_address_rejected():
    """No broad vendor-domain approval as a trust mechanism."""
    result = audit_engine.is_approved_identity(
        "Random Employee", "random.employee@openai.com",
        root=Path("."), policy_path=REAL_POLICY,
    )
    assert not result.approved


def test_private_owner_email_approved_via_injected_resolver(tmp_path):
    def fake_private_literal_values(root, key):
        if key == "owner_gmail":
            return ["synthetic.private.owner@example.invalid"]
        if key == "owner_name":
            return ["cyre"]
        return []

    result = audit_engine.is_approved_identity(
        "cyre", "synthetic.private.owner@example.invalid",
        root=tmp_path, policy_path=REAL_POLICY,
        private_literal_values_fn=fake_private_literal_values,
    )
    assert result.approved
    assert result.matched_kind == "private"


def test_private_identities_never_appear_in_tracked_policy():
    """Regression: the tracked public policy file must never contain a
    private-owner-identity lookup key -- those stay in the local-only
    private_literal_values() mechanism, resolved separately by the caller."""
    policy = audit_engine.load_policy(REAL_POLICY)
    text = json.dumps(policy)
    assert "owner_gmail" not in text
    assert "owner_name" not in text


def test_malformed_config_fails_closed(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    with pytest.raises(audit_engine.IdentityPolicyError):
        audit_engine.load_policy(bad)


def test_unsupported_version_fails_closed(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "version": 999, "human_identities": [], "agent_identities": [],
        "repo_bot_identities": {},
    }))
    with pytest.raises(audit_engine.IdentityPolicyError):
        audit_engine.load_policy(bad)


def test_missing_policy_file_fails_closed(tmp_path):
    with pytest.raises(audit_engine.IdentityPolicyError):
        audit_engine.load_policy(tmp_path / "does-not-exist.json")


def test_bash_attribution_helper_raises_on_execution_failure(tmp_path, monkeypatch):
    """Regression: a missing/broken banned_attribution_lib.sh must raise
    AttributionCheckError, not silently return False (which would be
    indistinguishable from a genuine 'no banned attribution' result --
    fail-open on exactly the check meant to catch banned attribution)."""
    monkeypatch.setattr(audit_engine, "_engine_dir", lambda: tmp_path)  # no lib file here
    with pytest.raises(audit_engine.AttributionCheckError):
        audit_engine._bash_banned_attribution_hit(
            tmp_path, "a@b.com", "name", "c@d.com", "cname", "body text",
        )


def test_missing_required_key_fails_closed(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"version": 1, "human_identities": []}))
    with pytest.raises(audit_engine.IdentityPolicyError):
        audit_engine.load_policy(bad)


@pytest.mark.unit
def test_wrong_container_type_fails_closed(tmp_path: Path) -> None:
    """Regression: valid JSON can still have the wrong shape (an int
    where a list is expected, a list where a mapping is expected) --
    must raise IdentityPolicyError, not an uncaught TypeError/
    AttributeError from iterating/`.items()`-ing the wrong type."""
    cases = [
        {"version": 1, "human_identities": 42, "agent_identities": [], "repo_bot_identities": {}},
        {"version": 1, "human_identities": [], "agent_identities": "not-a-list", "repo_bot_identities": {}},
        {"version": 1, "human_identities": [], "agent_identities": [], "repo_bot_identities": ["not-a-dict"]},
    ]
    for i, case in enumerate(cases):
        bad = tmp_path / f"bad{i}.json"
        bad.write_text(json.dumps(case))
        with pytest.raises(audit_engine.IdentityPolicyError):
            audit_engine.load_policy(bad)


@pytest.mark.unit
def test_malformed_nested_entries_fail_closed(tmp_path: Path) -> None:
    """Regression: a syntactically valid list/dict container can still
    have malformed VALUES inside it -- an entry missing 'email', a
    non-string alias, a non-list 'aliases' field, a non-string bot name.
    Each must raise IdentityPolicyError before any string/list operation
    (`.casefold()`, `"*" in bot`, iterating a non-list) that would
    otherwise raise a different, uncaught exception type."""
    cases = [
        # human_identities entry missing 'email'
        {"version": 1, "human_identities": [{"name": "x"}], "agent_identities": [], "repo_bot_identities": {}},
        # human_identities 'aliases' is not a list
        {
            "version": 1,
            "human_identities": [{"name": "x", "email": "x@example.invalid", "aliases": "not-a-list"}],
            "agent_identities": [],
            "repo_bot_identities": {},
        },
        # human_identities alias is not a string
        {
            "version": 1,
            "human_identities": [{"name": "x", "email": "x@example.invalid", "aliases": [42]}],
            "agent_identities": [],
            "repo_bot_identities": {},
        },
        # agent_identities entry missing 'email'
        {"version": 1, "human_identities": [], "agent_identities": [{"allowed_names": []}], "repo_bot_identities": {}},
        # repo_bot_identities entry is not a string
        {"version": 1, "human_identities": [], "agent_identities": [], "repo_bot_identities": {"repo": [42]}},
        # repo_bot_identities entry is an empty string
        {"version": 1, "human_identities": [], "agent_identities": [], "repo_bot_identities": {"repo": [""]}},
    ]
    for i, case in enumerate(cases):
        bad = tmp_path / f"malformed{i}.json"
        bad.write_text(json.dumps(case))
        with pytest.raises(audit_engine.IdentityPolicyError):
            audit_engine.load_policy(bad)


def test_agent_name_casefold_approved():
    result = audit_engine.is_approved_identity(
        "codex", "codex@openai.com", root=Path("."), policy_path=REAL_POLICY
    )
    assert result.approved
    assert result.matched_kind == "agent"


def test_configured_profile_allows_human_email_without_name_binding():
    result = audit_engine.is_approved_identity(
        "any display name", "lawrence@cyre.me",
        root=Path("."), policy_path=REAL_POLICY, profile="configured",
    )
    assert result.approved


def test_audit_relaxed_profile_allows_human_email_only():
    result = audit_engine.is_approved_identity(
        "not cyre", "lawrence@cyre.me",
        root=Path("."), policy_path=REAL_POLICY, profile="audit_relaxed",
    )
    assert result.approved


def test_vendor_domains_key_rejected_in_policy(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "version": 1,
        "human_identities": [],
        "agent_identities": [],
        "repo_bot_identities": {},
        "vendor_domains": ["openai.com"],
    }))
    with pytest.raises(audit_engine.IdentityPolicyError):
        audit_engine.load_policy(bad)


def test_wildcard_bot_in_policy_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "version": 1,
        "human_identities": [],
        "agent_identities": [],
        "repo_bot_identities": {"orama-system": ["*[bot]@users.noreply.github.com"]},
    }))
    with pytest.raises(audit_engine.IdentityPolicyError):
        audit_engine.load_policy(bad)


def test_same_bot_approved_across_multiple_repos(tmp_path):
    """The same bot (e.g. coderabbitai[bot]) legitimately reviews/commits
    across every repo in this stack -- the real policy file already lists
    it under both orama-system and Perpetua-Tools. That must load cleanly.
    """
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps({
        "version": 1,
        "human_identities": [],
        "agent_identities": [],
        "repo_bot_identities": {
            "repo-a": ["samebot[bot]@users.noreply.github.com"],
            "repo-b": ["samebot[bot]@users.noreply.github.com"],
        },
    }))
    policy = audit_engine.load_policy(ok)
    assert policy["repo_bot_identities"]["repo-a"] == policy["repo_bot_identities"]["repo-b"]


def test_duplicate_bot_within_same_repo_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "version": 1,
        "human_identities": [],
        "agent_identities": [],
        "repo_bot_identities": {
            "repo-a": [
                "samebot[bot]@users.noreply.github.com",
                "SameBot[bot]@Users.NoReply.GitHub.com",
            ],
        },
    }))
    with pytest.raises(audit_engine.IdentityPolicyError):
        audit_engine.load_policy(bad)


def test_check_configured_identity_passes_non_cursor(tmp_path, monkeypatch):
    monkeypatch.delenv("CURSOR_AGENT", raising=False)
    monkeypatch.delenv("CURSOR_TRACE_ID", raising=False)
    monkeypatch.delenv("CURSOR_SESSION_ID", raising=False)
    result = audit_engine.check_configured_identity(
        tmp_path, cursor_scoped=True, policy_path=REAL_POLICY
    )
    assert result.approved
    assert result.exit_code == 0


def test_audit_attribution_wrapper_is_shell_valid():
    import subprocess
    root = Path(__file__).resolve().parent.parent
    bash = os.environ.get("HERMES_GIT_BASH_PATH", "bash")
    subprocess.check_call([bash, "-n", str(root / "scripts/git/audit_attribution.sh")])


def test_check_identity_wrapper_is_shell_valid():
    import subprocess
    root = Path(__file__).resolve().parent.parent
    bash = os.environ.get("HERMES_GIT_BASH_PATH", "bash")
    subprocess.check_call([bash, "-n", str(root / "scripts/git/check_identity.sh")])


def test_case_and_whitespace_normalized():
    result = audit_engine.is_approved_identity(
        "  CYRE  ", "  LAWRENCE@CYRE.ME  ", root=Path("."), policy_path=REAL_POLICY
    )
    assert result.approved
