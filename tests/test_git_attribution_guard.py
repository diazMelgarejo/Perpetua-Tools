"""Tests for Cursor cloud commit-attribution guard scripts."""
from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STRIP_HOOK = ROOT / "scripts/git/hooks/commit-msg.strip-coauthor"
SYNC_PRIVATE = ROOT / "scripts/cursor/sync-private-attribution-from-home.sh"
CI_BOOTSTRAP = ROOT / "scripts/cursor/ci-bootstrap-private-attribution.sh"
ENSURE_HOOKS = ROOT / "scripts/git/ensure_hooks_installed.sh"
ORAMA_WRITE = Path("/agent/repos/orama-system/scripts/cursor/write-openclaw-private-attribution.sh")


def _ensure_banned_patterns() -> None:
    """Load gitignored banned patterns; prefer self-contained CI bootstrap when present."""
    patterns = ROOT / ".cursor/private/banned-attribution-patterns"
    if patterns.is_file():
        return
    if CI_BOOTSTRAP.is_file():
        subprocess.run(["bash", str(CI_BOOTSTRAP)], check=True, cwd=ROOT)
        if patterns.is_file():
            return
    if ORAMA_WRITE.is_file():
        subprocess.run(["bash", str(ORAMA_WRITE)], check=True, cwd=ROOT)
    if SYNC_PRIVATE.is_file():
        subprocess.run(["bash", str(SYNC_PRIVATE)], check=True, cwd=ROOT)
    assert patterns.is_file(), "banned-attribution-patterns missing"


def _first_banned_token() -> str:
    _ensure_banned_patterns()
    for line in (ROOT / ".cursor/private/banned-attribution-patterns").read_text(
        encoding="utf-8"
    ).splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            return line
    raise AssertionError("no banned tokens in pattern file")


def test_strip_coauthor_hook_removes_cursor_trailers(tmp_path):
    legacy_domain = "bettermind" + ".ph"
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(
        "feat: example\n\n"
        "Co-authored-by: Cursor <cursoragent@cursor.com>\n"
        f"Co-authored-by: cyre <Lawrence@{legacy_domain}>\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["bash", str(STRIP_HOOK), str(msg)],
        check=True,
        cwd=ROOT,
    )
    text = msg.read_text(encoding="utf-8")
    assert "Co-authored-by" not in text
    assert "feat: example" in text


def test_cursor_hooks_id_matches_workspace():
    lib = ROOT / "scripts/git/cursor-hooks-id.sh"
    repo_abs = str(ROOT.resolve())
    out = subprocess.check_output(
        ["bash", "-c", f'source "{lib}" && cursor_hooks_id "{ROOT}"'],
        text=True,
        cwd=ROOT,
    ).strip()
    expected = base64.b64encode(repo_abs.encode()).decode().rstrip("=")
    assert out == expected


def test_check_commit_message_allows_well_known_coauthors(tmp_path):
    _ensure_banned_patterns()
    script = ROOT / "scripts/git/check_commit_message.sh"
    for body, label in (
        ("feat: x\n\nCo-authored-by: Codex <codex@openai.com>\n", "codex"),
        ("feat: x\n\nCo-authored-by: Cursor <cursoragent@cursor.com>\n", "cursor"),
    ):
        msg = tmp_path / f"msg-{label}"
        msg.write_text(body, encoding="utf-8")
        subprocess.run(["bash", str(script), str(msg)], check=True, cwd=ROOT)


def test_check_commit_message_rejects_banned_coauthor_fixture(tmp_path):
    token = _first_banned_token()
    script = ROOT / "scripts/git/check_commit_message.sh"
    msg = tmp_path / "msg-banned-fixture"
    msg.write_text(
        f"feat: x\n\nCo-authored-by: X <{token}@example.invalid>\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["bash", str(script), str(msg)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0


def test_check_identity_allows_cursor_agent_at_cursor_dot_com():
    # Policy updated: cursor.com is in the WELL_KNOWN_AUTHOR_DOMAIN_SUFFIXES
    # allowlist, so cursoragent@cursor.com is now an approved git author.
    # (Previously this test expected rejection; the script was updated in
    # "fix(git-hooks): scope Cursor identity enforcement to Cursor agent commits
    # only" which added cursor.com to the well-known AI/vendor domain list.)
    proc = subprocess.run(
        ["bash", str(ROOT / "scripts/git/check_identity.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **dict(__import__("os").environ),
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "user.name",
            "GIT_CONFIG_VALUE_0": "Cursor Agent",
            "GIT_CONFIG_KEY_1": "user.email",
            "GIT_CONFIG_VALUE_1": "cursoragent@cursor.com",
        },
    )
    assert proc.returncode == 0
    assert "approved" in proc.stdout


def test_ensure_banned_patterns_prefers_ci_bootstrap(tmp_path, monkeypatch):
    """CI bootstrap must satisfy the fixture without calling legacy orama/home sync."""
    # Pytest may collect this file as either a top-level module or a package
    # module depending on checkout/package layout. Use the already-loaded module
    # instead of re-importing ``tests.test_git_attribution_guard`` so the test
    # validates bootstrap precedence, not Python import topology.
    module = sys.modules[__name__]

    fake_root = tmp_path / "repo"
    fake_private = fake_root / ".cursor/private"
    fake_private.mkdir(parents=True)
    patterns_path = fake_private / "banned-attribution-patterns"
    ran: list[list[str]] = []

    monkeypatch.setattr(module, "ROOT", fake_root)
    monkeypatch.setattr(module, "ORAMA_WRITE", fake_root / "missing/orama-write.sh")

    def mock_run(args, **kwargs):
        ran.append(list(args))
        if "ci-bootstrap-private-attribution" in str(args[1]):
            patterns_path.write_text("fixture-token\n", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", mock_run)
    module._ensure_banned_patterns()
    assert patterns_path.is_file()
    assert any("ci-bootstrap-private-attribution" in " ".join(cmd) for cmd in ran)
    assert not any("orama" in " ".join(cmd).lower() for cmd in ran)


def test_verify_git_guards_github_actions_skips_hooks_json_check():
    """On GHA, verify-git-guards must not fail on missing ~/.cursor/hooks.json."""
    subprocess.run(["bash", str(CI_BOOTSTRAP)], check=True, cwd=ROOT)
    home = os.environ.get("HOME", "/home/ubuntu")
    hooks_path = os.path.join(home, ".cursor", "hooks.json")
    proc = subprocess.run(
        ["bash", str(ROOT / "scripts/git/verify-git-guards.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "GITHUB_ACTIONS": "true"},
    )
    combined = proc.stdout + proc.stderr
    assert "skip user-level Cursor session hook checks" in combined
    assert f"missing {hooks_path}" not in combined


def test_check_commit_message_rejects_unknown_gmail(tmp_path):
    script = ROOT / "scripts/git/check_commit_message.sh"
    msg = tmp_path / "msg-bad"
    msg.write_text(
        "feat: x\n\nCo-authored-by: Random <randomperson@gmail.com>\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["bash", str(script), str(msg)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0


def test_check_commit_message_rejects_tool_marker_with_bad_email(tmp_path):
    """Display-name markers must not override a rejected email address."""
    script = ROOT / "scripts/git/check_commit_message.sh"
    msg = tmp_path / "msg-marker-bad-email"
    msg.write_text(
        "feat: x\n\nCo-authored-by: Claude <attacker@evil.com>\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["bash", str(script), str(msg)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "not on approved co-author policy" in proc.stderr


def test_check_commit_message_rejects_hermes_display_name_with_bad_email(tmp_path):
    """Hermes in display name must not bypass email allowlist."""
    script = ROOT / "scripts/git/check_commit_message.sh"
    msg = tmp_path / "msg-hermes-bad-email"
    msg.write_text(
        "feat: x\n\nCo-authored-by: Hermes <attacker@evil.com>\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["bash", str(script), str(msg)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0


@pytest.mark.parametrize(
    ("body", "should_pass"),
    [
        ("feat: x\n\nCo-authored-by: Hermes <<attacker@evil.com>>\n", False),
        ("feat: x\n\nCo-authored-by: Claude <noreply@anthropic.com\n", True),
        ("feat: x\n\nCo-authored-by: <noreply@anthropic.com>\n", True),
        ("feat: x\n\nCo-Authored-By: Qwen <ünïcödé@evil.com>\n", False),
        ("feat: x\n\nco-authored-by: hermes\n", True),
        ("feat: x\n\nCo-authored-by: Random Person <random@gmail.com>\n", False),
    ],
    ids=[
        "double-angle-email",
        "unclosed-bracket-claude",
        "no-display-name-anthropic",
        "non-ascii-email",
        "display-name-only-hermes",
        "unknown-gmail",
    ],
)
def test_check_commit_message_malformed_coauthor_fuzz(tmp_path, body, should_pass):
    """Edge-case Co-authored-by lines from security plan T3-B."""
    script = ROOT / "scripts/git/check_commit_message.sh"
    msg = tmp_path / "msg-fuzz"
    msg.write_text(body, encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(script), str(msg)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if should_pass:
        assert proc.returncode == 0, proc.stderr
    else:
        assert proc.returncode != 0
