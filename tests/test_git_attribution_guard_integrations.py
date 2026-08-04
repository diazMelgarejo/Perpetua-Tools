"""Integration coverage for git attribution guard scripts.

PR #211 briefly narrowed ``tests/test_git_attribution_guard.py`` to the fast
commit-message cases. This companion file restores the slower shell integration
contracts as first-class tests without weakening the attribution policy.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENSURE_HOOKS = ROOT / "scripts/git/ensure_hooks_installed.sh"
CI_BOOTSTRAP = ROOT / "scripts/cursor/ci-bootstrap-private-attribution.sh"
VERIFY_GUARDS = ROOT / "scripts/git/verify-git-guards.sh"
BANNED_ATTR_LIB = ROOT / "scripts/git/banned_attribution_lib.sh"
CHECK_IDENTITY = ROOT / "scripts/git/check_identity.sh"
CHECK_COMMIT_MESSAGE = ROOT / "scripts/git/check_commit_message.sh"
AUDIT_ATTRIBUTION = ROOT / "scripts/git/audit_attribution.sh"

AUTHORIZED_HUMAN_MARKERS = (
    "diazMelgarejo",
    "diaz.Melgarejo",
)


def _ensure_banned_patterns() -> None:
    subprocess.run(["bash", str(CI_BOOTSTRAP)], check=True, cwd=ROOT)
    assert (ROOT / ".cursor/private/banned-attribution-patterns").is_file()


def _pattern_tokens() -> set[str]:
    _ensure_banned_patterns()
    tokens: set[str] = set()
    for raw in (ROOT / ".cursor/private/banned-attribution-patterns").read_text(
        encoding="utf-8"
    ).splitlines():
        token = raw.split("#", 1)[0].strip().lower()
        if token:
            tokens.add(token)
    return tokens


def _private_owner_email_fixture(tmp_path: Path) -> tuple[Path, str]:
    private_email = "private.owner@gmail.com"
    literals = tmp_path / "verboten.local"
    literals.write_text(
        f"owner_gmail={private_email}\nowner_name=Private.Owner\n",
        encoding="utf-8",
    )
    return literals, private_email


def _call_first_banned_pattern_token(root: Path) -> subprocess.CompletedProcess[str]:
    """Invoke first_banned_pattern_token with an isolated HOME."""
    script = f'source "{BANNED_ATTR_LIB}" && first_banned_pattern_token "{root}"'
    isolated_home = Path(tempfile.mkdtemp(prefix="pt-banned-token-"))
    try:
        env = {
            **os.environ,
            "HOME": str(isolated_home),
            "OPENCLAW_ATTRIBUTION_PATTERNS": str(isolated_home / "missing-patterns"),
        }
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)
    finally:
        shutil.rmtree(isolated_home, ignore_errors=True)


def test_banned_patterns_do_not_forbid_authorized_human_identities():
    """Authorized human names/emails are allowlist material, not banned tokens."""
    tokens = _pattern_tokens()
    forbidden = {
        "diazmelgarejo",
        "diaz.melgarejo",
        "diazmelgarejo@gmail.com",
    }
    assert tokens.isdisjoint(forbidden)


@pytest.mark.parametrize("name", ["diazMelgarejo", "diaz.Melgarejo"])
def test_check_identity_allows_public_authorized_human_authors_even_in_cursor_context(name):
    """Approved human authors must remain valid even when Cursor env vars exist."""
    proc = subprocess.run(
        ["bash", str(CHECK_IDENTITY)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CURSOR_SESSION_ID": "test-session",
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "user.name",
            "GIT_CONFIG_VALUE_0": name,
            "GIT_CONFIG_KEY_1": "user.email",
            "GIT_CONFIG_VALUE_1": "diazMelgarejo@gmail.com",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert "approved" in proc.stdout


def test_check_identity_allows_private_owner_email_from_external_file(tmp_path):
    """The private owner email is allowed only through a local-only literals file."""
    literals, private_email = _private_owner_email_fixture(tmp_path)
    proc = subprocess.run(
        ["bash", str(CHECK_IDENTITY)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CURSOR_SESSION_ID": "test-session",
            "OPENCLAW_VERBOTEN_LITERALS": str(literals),
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "user.name",
            "GIT_CONFIG_VALUE_0": "Private.Owner",
            "GIT_CONFIG_KEY_1": "user.email",
            "GIT_CONFIG_VALUE_1": private_email,
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert "approved" in proc.stdout


def test_audit_attribution_range_mode_reports_only_pushed_range():
    """Pre-push range mode must not report unrelated inherited ref summaries."""
    proc = subprocess.run(
        ["bash", str(AUDIT_ATTRIBUTION), "0"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={
            **os.environ,
            "GIT_AUDIT_RANGE": "HEAD..HEAD",
            "GIT_AUDIT_STRICT": "1",
        },
    )
    assert proc.returncode == 0, proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert lines
    assert all(line.startswith("RANGE\t") for line in lines), proc.stdout


def test_audit_attribution_context_refs_are_explicit_opt_in():
    """Manual diagnostics can still request HEAD/main/origin summaries."""
    proc = subprocess.run(
        ["bash", str(AUDIT_ATTRIBUTION), "0"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={
            **os.environ,
            "GIT_AUDIT_RANGE": "HEAD..HEAD",
            "GIT_AUDIT_STRICT": "1",
            "GIT_AUDIT_INCLUDE_CONTEXT_REFS": "1",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert "RANGE\tHEAD..HEAD\t" in proc.stdout
    assert any(
        line.startswith(("HEAD\t", "main\t", "origin/main\t"))
        for line in proc.stdout.splitlines()
    ), proc.stdout


@pytest.mark.parametrize("name", ["diazMelgarejo", "diaz.Melgarejo"])
def test_check_commit_message_allows_public_authorized_human_coauthors(tmp_path, name):
    """Approved human identities are valid Co-authored-by trailers."""
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(
        f"feat: x\n\nCo-authored-by: {name} <diazMelgarejo@gmail.com>\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["bash", str(CHECK_COMMIT_MESSAGE), str(msg)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_check_commit_message_allows_private_owner_email_from_external_file(tmp_path):
    literals, private_email = _private_owner_email_fixture(tmp_path)
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(
        f"feat: x\n\nCo-authored-by: Private.Owner <{private_email}>\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["bash", str(CHECK_COMMIT_MESSAGE), str(msg)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "OPENCLAW_VERBOTEN_LITERALS": str(literals)},
    )
    assert proc.returncode == 0, proc.stderr


def test_first_banned_pattern_token_returns_first_token(tmp_path):
    private_dir = tmp_path / ".cursor/private"
    private_dir.mkdir(parents=True)
    (private_dir / "banned-attribution-patterns").write_text(
        "# comment line\nut-fixture-first\nut-fixture-second\n", encoding="utf-8"
    )
    proc = _call_first_banned_pattern_token(tmp_path)
    assert proc.returncode == 0
    assert proc.stdout == "ut-fixture-first"


def test_first_banned_pattern_token_skips_empty_lines(tmp_path):
    private_dir = tmp_path / ".cursor/private"
    private_dir.mkdir(parents=True)
    (private_dir / "banned-attribution-patterns").write_text(
        "\n\n\nut-fixture-first\nut-fixture-second\n", encoding="utf-8"
    )
    proc = _call_first_banned_pattern_token(tmp_path)
    assert proc.returncode == 0
    assert proc.stdout == "ut-fixture-first"


def test_first_banned_pattern_token_fails_on_missing_or_empty_patterns(tmp_path):
    assert _call_first_banned_pattern_token(tmp_path).returncode != 0
    private_dir = tmp_path / ".cursor/private"
    private_dir.mkdir(parents=True)
    (private_dir / "banned-attribution-patterns").write_text("", encoding="utf-8")
    assert _call_first_banned_pattern_token(tmp_path).returncode != 0


def test_first_banned_pattern_token_strips_inline_comments(tmp_path):
    private_dir = tmp_path / ".cursor/private"
    private_dir.mkdir(parents=True)
    (private_dir / "banned-attribution-patterns").write_text(
        "# header\nut-fixture-inline  # inline comment\n", encoding="utf-8"
    )
    proc = _call_first_banned_pattern_token(tmp_path)
    assert proc.returncode == 0
    assert proc.stdout == "ut-fixture-inline"


def test_first_banned_pattern_token_with_real_patterns():
    _ensure_banned_patterns()
    proc = _call_first_banned_pattern_token(ROOT)
    assert proc.returncode == 0
    assert proc.stdout.strip()


def test_daily_attribution_guard_requires_opt_in_for_auto_expunge():
    text = (ROOT / "scripts/git/daily-attribution-guard.sh").read_text(encoding="utf-8")
    assert "ATTRIBUTION_EXPUNGE_AUTO" in text
    assert "expunge-all-workspace-repos.sh" in text
    assert 'ATTRIBUTION_EXPUNGE_AUTO:-}" == "1"' in text


def test_cloud_bootstrap_does_not_invoke_daily_attribution_guard():
    text = (ROOT / "scripts/cursor/cloud-bootstrap.sh").read_text(encoding="utf-8")
    assert "daily-attribution-guard.sh" not in text


def _run_verify_guards_in_github_actions(*, home: Path | None = None) -> tuple[subprocess.CompletedProcess[str], str]:
    """Run VERIFY_GUARDS once with the GitHub Actions skip path enabled."""
    _ensure_banned_patterns()
    env = {**os.environ, "GITHUB_ACTIONS": "true"}
    if home is not None:
        env["HOME"] = str(home)
    proc = subprocess.run(
        ["bash", str(VERIFY_GUARDS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=env,
    )
    return proc, proc.stdout + proc.stderr


def test_verify_guards_github_actions_skips_cursor_session_hook_check():
    _proc, combined = _run_verify_guards_in_github_actions()
    assert "skip user-level Cursor session hook checks" in combined


def test_verify_guards_github_actions_does_not_print_cursor_session_hook_fail(tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _proc, combined = _run_verify_guards_in_github_actions(home=fake_home)
    assert "Cursor sessionStart hook missing" not in combined
    assert f"missing {fake_home}/.cursor/hooks.json" not in combined


def test_verify_guards_without_github_actions_checks_session_hook(tmp_path):
    _ensure_banned_patterns()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    proc = subprocess.run(
        ["bash", str(VERIFY_GUARDS)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "HOME": str(fake_home), "GITHUB_ACTIONS": ""},
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0
    assert "Cursor sessionStart hook missing" in combined


def _make_fake_git_repo(tmp_path: Path, hooks_path: str = ".githooks") -> Path:
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "--local", "core.hooksPath", hooks_path],
        check=True,
        capture_output=True,
    )
    return tmp_path


def _run_ensure_hooks(repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(ENSURE_HOOKS)],
        capture_output=True,
        text=True,
        env={**os.environ, "REPO_ROOT": str(repo_root)},
    )


def _snapshot_repo_hooks_state(repo_root: Path) -> dict:
    """Capture local core.hooksPath and hook files before mutating the checkout."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "config", "--local", "--get", "core.hooksPath"],
        capture_output=True,
        text=True,
    )
    hooks_path = proc.stdout.strip() if proc.returncode == 0 else None
    hooks_dir = repo_root / (hooks_path if hooks_path else ".githooks")
    snapshot = {
        "hooks_path": hooks_path,
        "hooks_path_was_set": proc.returncode == 0,
        "hooks_dir_existed": hooks_dir.is_dir(),
        "hooks_dir": hooks_dir,
        "hooks": {},
    }
    for hook in ("pre-commit", "commit-msg", "pre-push"):
        hook_path = hooks_dir / hook
        if hook_path.exists():
            snapshot["hooks"][hook] = {
                "content": hook_path.read_bytes(),
                "mode": hook_path.stat().st_mode,
            }
        else:
            snapshot["hooks"][hook] = None
    return snapshot


def _restore_repo_hooks_state(repo_root: Path, snapshot: dict) -> None:
    """Restore hook files and core.hooksPath after tests that call _ensure_repo_hooks_configured."""
    hooks_dir = snapshot["hooks_dir"]
    for hook in ("pre-commit", "commit-msg", "pre-push"):
        hook_path = hooks_dir / hook
        prev = snapshot["hooks"].get(hook)
        if prev is None:
            if hook_path.exists():
                hook_path.unlink()
        else:
            hooks_dir.mkdir(parents=True, exist_ok=True)
            hook_path.write_bytes(prev["content"])
            hook_path.chmod(prev["mode"])

    if not snapshot["hooks_dir_existed"] and hooks_dir.is_dir():
        try:
            hooks_dir.rmdir()
        except OSError:
            pass

    if snapshot["hooks_path_was_set"]:
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "config",
                "--local",
                "core.hooksPath",
                snapshot["hooks_path"],
            ],
            check=True,
            capture_output=True,
        )
    else:
        subprocess.run(
            ["git", "-C", str(repo_root), "config", "--local", "--unset", "core.hooksPath"],
            capture_output=True,
        )


def _ensure_repo_hooks_configured(repo_root: Path) -> None:
    """CI checkouts may ship .githooks/ without local core.hooksPath configured."""
    hooks_dir = repo_root / ".githooks"
    hooks_dir.mkdir(exist_ok=True)
    for hook in ("pre-commit", "commit-msg", "pre-push"):
        dest = hooks_dir / hook
        if not dest.exists():
            dest.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        dest.chmod(0o755)
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "--local", "core.hooksPath", ".githooks"],
        check=True,
        capture_output=True,
    )


def test_ensure_hooks_installed_fails_when_hookspath_wrong(tmp_path):
    _make_fake_git_repo(tmp_path, hooks_path=".git/hooks")
    proc = _run_ensure_hooks(tmp_path)
    assert proc.returncode != 0
    assert ".githooks" in proc.stderr


def test_ensure_hooks_installed_fails_when_hook_missing(tmp_path):
    _make_fake_git_repo(tmp_path, hooks_path=".githooks")
    hooks_dir = tmp_path / ".githooks"
    hooks_dir.mkdir()
    for hook in ("pre-commit", "commit-msg"):
        h = hooks_dir / hook
        h.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        h.chmod(0o755)

    proc = _run_ensure_hooks(tmp_path)
    assert proc.returncode != 0
    assert "pre-push" in proc.stderr


def test_ensure_hooks_installed_passes_when_all_hooks_present(tmp_path):
    _make_fake_git_repo(tmp_path, hooks_path=".githooks")
    hooks_dir = tmp_path / ".githooks"
    hooks_dir.mkdir()
    for hook in ("pre-commit", "commit-msg", "pre-push"):
        h = hooks_dir / hook
        h.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        h.chmod(0o755)

    proc = _run_ensure_hooks(tmp_path)
    assert proc.returncode == 0
    assert proc.stdout == ""
    assert proc.stderr == ""


def test_ensure_hooks_installed_fails_when_hook_not_executable(tmp_path):
    _make_fake_git_repo(tmp_path, hooks_path=".githooks")
    hooks_dir = tmp_path / ".githooks"
    hooks_dir.mkdir()
    for hook in ("pre-commit", "commit-msg", "pre-push"):
        h = hooks_dir / hook
        h.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        h.chmod(0o644)

    proc = _run_ensure_hooks(tmp_path)
    assert proc.returncode != 0
    assert "non-executable" in proc.stderr


def test_ensure_hooks_installed_remaps_only_nested_repo_root(tmp_path):
    """Nested REPO_ROOT under the script checkout remaps; sibling roots do not."""
    import shutil

    sibling = tmp_path / "sibling"
    _make_fake_git_repo(sibling, hooks_path=".githooks")
    hooks_dir = sibling / ".githooks"
    hooks_dir.mkdir()
    for hook in ("pre-commit", "commit-msg", "pre-push"):
        h = hooks_dir / hook
        h.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        h.chmod(0o644)
    proc = _run_ensure_hooks(sibling)
    assert proc.returncode != 0
    assert "non-executable" in proc.stderr

    nested = ROOT / ".pytest_cache" / "ensure-hooks-nested"
    if nested.exists():
        shutil.rmtree(nested)
    nested.parent.mkdir(parents=True, exist_ok=True)
    hooks_snapshot = _snapshot_repo_hooks_state(ROOT)
    try:
        _ensure_repo_hooks_configured(ROOT)
        _make_fake_git_repo(nested, hooks_path=".githooks")
        proc = _run_ensure_hooks(nested)
        assert proc.returncode == 0, proc.stderr
    finally:
        if nested.exists():
            shutil.rmtree(nested)
        _restore_repo_hooks_state(ROOT, hooks_snapshot)


def test_ensure_banned_patterns_succeeds_when_patterns_present():
    _ensure_banned_patterns()
