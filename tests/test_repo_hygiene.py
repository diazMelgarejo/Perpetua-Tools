"""Tests for scripts/review/repo_hygiene.py — Perpetua-Tools hygiene gate.

Mirrors orama-system/tests/test_repo_hygiene.py with PT-specific adaptations.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
HYGIENE_PATH = ROOT / "scripts" / "review" / "repo_hygiene.py"


def load_repo_hygiene():
    spec = importlib.util.spec_from_file_location("repo_hygiene", HYGIENE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# scan_personal_paths
# ---------------------------------------------------------------------------

def test_personal_path_real_username_is_blocked(tmp_path):
    repo_hygiene = load_repo_hygiene()
    doc = tmp_path / "README.md"
    doc.write_text("Run: /Users/johndoe/projects/pt/start.sh\n", encoding="utf-8")

    errors = repo_hygiene.scan_personal_paths(tmp_path, ["README.md"])

    assert len(errors) == 1
    assert "README.md:1" in errors[0]
    assert "/Users/johndoe/" in errors[0]


def test_personal_path_home_is_blocked(tmp_path):
    repo_hygiene = load_repo_hygiene()
    doc = tmp_path / "docs" / "setup.md"
    doc.parent.mkdir()
    doc.write_text("cd /home/johndoe/code/pt\n", encoding="utf-8")

    errors = repo_hygiene.scan_personal_paths(tmp_path, ["docs/setup.md"])

    assert len(errors) == 1
    assert "/home/johndoe/" in errors[0]


def test_personal_path_windows_path_is_blocked(tmp_path):
    repo_hygiene = load_repo_hygiene()
    doc = tmp_path / "notes.md"
    win = "C:" + "\\Users\\johndoe\\Downloads\\SKILLS.md\\ultrathink"
    doc.write_text(f"Canonical: {win}\n", encoding="utf-8")
    errors = repo_hygiene.scan_personal_paths(tmp_path, ["notes.md"])
    assert len(errors) == 1
    assert "johndoe" in errors[0] or "Users" in errors[0]


def test_personal_path_placeholder_usernames_are_allowed(tmp_path):
    repo_hygiene = load_repo_hygiene()
    doc = tmp_path / "docs" / "install.md"
    doc.parent.mkdir()
    doc.write_text(
        "Example: /Users/you/projects/pt\n"
        "Or: /home/user/code\n"
        "Or: /Users/username/pt\n"
        "Or: /Users/example/dir\n",
        encoding="utf-8",
    )

    errors = repo_hygiene.scan_personal_paths(tmp_path, ["docs/install.md"])

    assert errors == [], f"Placeholder usernames should be allowed: {errors}"


def test_personal_path_script_self_is_exempt(tmp_path):
    """The hygiene script itself is exempt (it names the pattern for documentation)."""
    repo_hygiene = load_repo_hygiene()
    script = tmp_path / "scripts" / "review" / "repo_hygiene.py"
    script.parent.mkdir(parents=True)
    script.write_text("/Users/realuser/something\n", encoding="utf-8")

    errors = repo_hygiene.scan_personal_paths(
        tmp_path, ["scripts/review/repo_hygiene.py"]
    )

    assert errors == []


def test_personal_path_test_file_is_exempt(tmp_path):
    """The test file itself is exempt (it uses fixture personal paths)."""
    repo_hygiene = load_repo_hygiene()
    test_file = tmp_path / "tests" / "test_repo_hygiene.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("/Users/realuser/fixture\n", encoding="utf-8")

    errors = repo_hygiene.scan_personal_paths(
        tmp_path, ["tests/test_repo_hygiene.py"]
    )

    assert errors == []


def test_personal_path_clean_file_passes(tmp_path):
    repo_hygiene = load_repo_hygiene()
    doc = tmp_path / "README.md"
    doc.write_text(
        "Run from: ~/projects/pt\n"
        "Or set REPO_ROOT and use $REPO_ROOT/start.sh\n",
        encoding="utf-8",
    )

    errors = repo_hygiene.scan_personal_paths(tmp_path, ["README.md"])

    assert errors == []


# ---------------------------------------------------------------------------
# scan_bidi_controls
# ---------------------------------------------------------------------------

# Actual BiDi control characters used as test fixtures (permitted in this file
# because "tests/test_repo_hygiene.py" is in BIDI_CONTROL_EXCEPTIONS).
_LRE = "‪"  # Left-to-Right Embedding
_RLO = "‮"  # Right-to-Left Override
_LRI = "⁦"  # Left-to-Right Isolate
_PDI = "⁩"  # Pop Directional Isolate


def test_bidi_lre_is_blocked(tmp_path):
    repo_hygiene = load_repo_hygiene()
    src = tmp_path / "orchestrator" / "agent.py"
    src.parent.mkdir()
    src.write_text(f"# {_LRE}access_level = 'user'\n", encoding="utf-8")

    errors = repo_hygiene.scan_bidi_controls(tmp_path, ["orchestrator/agent.py"])

    assert len(errors) == 1
    assert "U+202A" in errors[0]
    assert "LRE" in errors[0]


def test_bidi_rlo_is_blocked(tmp_path):
    repo_hygiene = load_repo_hygiene()
    src = tmp_path / "config.py"
    src.write_text(f"key = {_RLO}value\n", encoding="utf-8")

    errors = repo_hygiene.scan_bidi_controls(tmp_path, ["config.py"])

    assert len(errors) == 1
    assert "U+202E" in errors[0]
    assert "RLO" in errors[0]


def test_bidi_multiple_chars_report_first_per_file(tmp_path):
    """Only first BiDi char per file is reported (break-after-first logic)."""
    repo_hygiene = load_repo_hygiene()
    src = tmp_path / "evil.py"
    src.write_text(
        f"line1 = {_LRE}ok\n"
        f"line2 = {_RLO}bad\n",
        encoding="utf-8",
    )

    errors = repo_hygiene.scan_bidi_controls(tmp_path, ["evil.py"])

    assert len(errors) == 1  # only first char/line triggers, then breaks


def test_bidi_clean_file_passes(tmp_path):
    repo_hygiene = load_repo_hygiene()
    src = tmp_path / "clean.py"
    src.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    errors = repo_hygiene.scan_bidi_controls(tmp_path, ["clean.py"])

    assert errors == []


def test_bidi_exceptions_are_exempt(tmp_path):
    """The hygiene script and test file are exempt from BiDi scanning."""
    repo_hygiene = load_repo_hygiene()
    script = tmp_path / "scripts" / "review" / "repo_hygiene.py"
    script.parent.mkdir(parents=True)
    script.write_text(f"BIDI_LRE = '{_LRE}'\n", encoding="utf-8")

    test_file = tmp_path / "tests" / "test_repo_hygiene.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(f"_LRE = '{_LRE}'\n", encoding="utf-8")

    errors = repo_hygiene.scan_bidi_controls(
        tmp_path,
        ["scripts/review/repo_hygiene.py", "tests/test_repo_hygiene.py"],
    )

    assert errors == []


# ---------------------------------------------------------------------------
# scan_mojibake
# ---------------------------------------------------------------------------

def test_mojibake_is_blocked(tmp_path):
    repo_hygiene = load_repo_hygiene()
    doc = tmp_path / "docs" / "notes.md"
    doc.parent.mkdir()
    mojibake_emdash = chr(0x00E2) + chr(0x20AC) + chr(0x201D)
    doc.write_text(f"broken {mojibake_emdash} dash\n", encoding="utf-8")

    errors = repo_hygiene.scan_mojibake(tmp_path, ["docs/notes.md"])

    assert len(errors) == 1
    assert "UTF-8 mojibake" in errors[0]
    assert "docs/notes.md:1" in errors[0]


def test_valid_utf8_punctuation_passes_mojibake_scan(tmp_path):
    repo_hygiene = load_repo_hygiene()
    doc = tmp_path / "docs" / "notes.md"
    doc.parent.mkdir()
    doc.write_text("valid UTF-8 punctuation - em dash: \u2014\n", encoding="utf-8")

    errors = repo_hygiene.scan_mojibake(tmp_path, ["docs/notes.md"])

    assert errors == []


def test_four_byte_utf8_mojibake_is_blocked(tmp_path):
    repo_hygiene = load_repo_hygiene()
    doc = tmp_path / "docs" / "notes.md"
    doc.parent.mkdir()
    # UTF-8 emoji bytes mis-decoded as latin-1 (supplementary-plane mojibake).
    mojibake_emoji = chr(0x00F0) + chr(0x0178) + chr(0x02DC) + chr(0x20AC)
    doc.write_text(f"broken {mojibake_emoji}\n", encoding="utf-8")

    errors = repo_hygiene.scan_mojibake(tmp_path, ["docs/notes.md"])

    assert len(errors) == 1
    assert "UTF-8 mojibake" in errors[0]
    assert "docs/notes.md:1" in errors[0]


# ---------------------------------------------------------------------------
# generated artifact tracking
# ---------------------------------------------------------------------------

def test_generated_artifact_patterns_are_blocked():
    repo_hygiene = load_repo_hygiene()
    errors = repo_hygiene.check_generated_artifact_tracking(
        [
            ".DS_Store",
            "orchestrator/__pycache__/contracts.cpython-312.pyc",
            "dist/perpetua_tools-0.9.9.9.whl",
            "README.md",
        ]
    )

    assert "generated artifact is tracked: .DS_Store" in errors
    assert "generated artifact is tracked: orchestrator/__pycache__/contracts.cpython-312.pyc" in errors
    assert "generated artifact is tracked: dist/perpetua_tools-0.9.9.9.whl" in errors
    assert not any("README.md" in e for e in errors)


# ---------------------------------------------------------------------------
# private generated config
# ---------------------------------------------------------------------------

def test_private_generated_configs_are_blocked():
    repo_hygiene = load_repo_hygiene()
    errors = repo_hygiene.check_private_generated_tracking(
        [".env", ".env.local", ".paths", "README.md"]
    )

    assert "private/generated config is tracked: .env" in errors
    assert "private/generated config is tracked: .env.local" in errors
    assert not any("README.md" in e for e in errors)


# ---------------------------------------------------------------------------
# scan_forbidden_identity
# ---------------------------------------------------------------------------

def test_forbidden_identity_token_is_blocked(tmp_path):
    repo_hygiene = load_repo_hygiene()
    doc = tmp_path / "notes.md"
    # Build token at runtime to avoid triggering the hygiene scan on THIS file.
    token = "Lawrence " + "Melgarejo"
    doc.write_text(f"Author: {token}\n", encoding="utf-8")

    errors = repo_hygiene.scan_forbidden_identity(tmp_path, ["notes.md"])

    assert len(errors) == 1
    assert "notes.md" in errors[0]


def test_forbidden_identity_exception_is_exempt(tmp_path):
    repo_hygiene = load_repo_hygiene()
    mailmap = tmp_path / ".mailmap"
    token = "Lawrence " + "Melgarejo"
    mailmap.write_text(f"{token} <old@email.com>\n", encoding="utf-8")

    errors = repo_hygiene.scan_forbidden_identity(tmp_path, [".mailmap"])

    assert errors == []


def test_agent_memory_owner_gmail_identity_is_blocked(tmp_path):
    repo_hygiene = load_repo_hygiene()
    literals = tmp_path / "verboten.local"
    private_email = "private.owner@example.invalid"
    literals.write_text(
        f"owner_gmail={private_email}\nowner_name=Private.Owner\n",
        encoding="utf-8",
    )
    old = os.environ.get("OPENCLAW_VERBOTEN_LITERALS")
    os.environ["OPENCLAW_VERBOTEN_LITERALS"] = str(literals)
    memory = tmp_path / ".agent" / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl"
    memory.parent.mkdir(parents=True)
    memory.write_text(f'{{"author":"{private_email}"}}\n', encoding="utf-8")

    try:
        errors = repo_hygiene.scan_private_verboten_literals(
            tmp_path, [".agent/memory/episodic/AGENT_LEARNINGS.jsonl"]
        )
    finally:
        if old is None:
            os.environ.pop("OPENCLAW_VERBOTEN_LITERALS", None)
        else:
            os.environ["OPENCLAW_VERBOTEN_LITERALS"] = old

    assert len(errors) == 1
    assert "private verboten literal in tracked file" in errors[0]


def test_private_verboten_literals_are_blocked_case_insensitively(tmp_path):
    repo_hygiene = load_repo_hygiene()
    literals = tmp_path / "verboten.local"
    private_email = "private.owner@example.invalid"
    private_name = "Private.Owner"
    forbidden_attr = "Blocked.Attribution@example.invalid"
    literals.write_text(
        f"owner_gmail={private_email}\n"
        f"owner_name={private_name}\n"
        f"forbidden_attribution={forbidden_attr}\n",
        encoding="utf-8",
    )
    old = os.environ.get("OPENCLAW_VERBOTEN_LITERALS")
    os.environ["OPENCLAW_VERBOTEN_LITERALS"] = str(literals)
    contributing = tmp_path / "CONTRIBUTING.md"
    contributing.write_text(f"Use {private_email.upper()}\n", encoding="utf-8")
    template = tmp_path / ".github" / "pull_request_template.md"
    template.parent.mkdir()
    template.write_text(
        f"Do not use {private_name.lower()} or {forbidden_attr.upper()}\n",
        encoding="utf-8",
    )

    try:
        errors = repo_hygiene.scan_private_verboten_literals(
            tmp_path, ["CONTRIBUTING.md", ".github/pull_request_template.md"]
        )
    finally:
        if old is None:
            os.environ.pop("OPENCLAW_VERBOTEN_LITERALS", None)
        else:
            os.environ["OPENCLAW_VERBOTEN_LITERALS"] = old

    assert len(errors) == 2
    assert any("CONTRIBUTING.md" in error for error in errors)
    assert any(".github/pull_request_template.md" in error for error in errors)


def test_owner_gmail_redaction_rule_allows_mechanical_allowlists(tmp_path):
    repo_hygiene = load_repo_hygiene()
    doc = tmp_path / ".github" / "AUTHORIZED_CONTRIBUTORS.md"
    doc.parent.mkdir()
    private_email = "private.owner@example.invalid"
    doc.write_text(f"cyre <{private_email}>\n", encoding="utf-8")

    errors = repo_hygiene.scan_private_verboten_literals(
        tmp_path, [".github/AUTHORIZED_CONTRIBUTORS.md"]
    )

    assert errors == []


# ---------------------------------------------------------------------------
# CLAUDE.md — portable-paths rule (§ 6 Git Hygiene, lockstep w/ orama)
#
# Additive coverage (does not replace scripts/review/repo_hygiene.py checks):
#   a) CLAUDE.md is NOT in PERSONAL_PATH_EXCEPTIONS — navigation doc stays scanned
#   b) The live CLAUDE.md on main passes scan_personal_paths (portable tokens only)
#   c) Synthetic CLAUDE.md fixtures prove /Users/<real>/ and /home/<user>/ leaks
#      are still blocked — enforcement is independent of how § 6 prose is worded
# Canonical rule: ../orama-system/docs/wiki/08-git-hygiene-and-branching.md
# ---------------------------------------------------------------------------

def test_claude_md_is_not_in_personal_path_exceptions():
    """CLAUDE.md must not appear in PERSONAL_PATH_EXCEPTIONS — it stays scanned."""
    repo_hygiene = load_repo_hygiene()
    assert "CLAUDE.md" not in repo_hygiene.PERSONAL_PATH_EXCEPTIONS


def test_claude_md_passes_personal_path_scan():
    """The live CLAUDE.md must contain no real workstation paths."""
    repo_hygiene = load_repo_hygiene()
    claude_md = ROOT / "CLAUDE.md"
    assert claude_md.exists(), "CLAUDE.md not found at repo root"

    errors = repo_hygiene.scan_personal_paths(ROOT, ["CLAUDE.md"])

    assert errors == [], (
        "CLAUDE.md contains a personal/workstation path — "
        "use ~, $REPO_ROOT, or $OPENCLAW_ROOT instead:\n" + "\n".join(errors)
    )


def test_claude_md_with_workstation_path_is_blocked(tmp_path):
    """scan_personal_paths blocks a CLAUDE.md that leaks a real developer path.

    Regression guard: hygiene enforcement on CLAUDE.md is unchanged regardless of
    how § 6 documents the rule (bullet text may evolve; the scanner does not).
    """
    repo_hygiene = load_repo_hygiene()
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(
        "## Setup\n"
        "Run `bash /Users/johndoe/projects/perpetua-tools/scripts/setup.sh`\n",
        encoding="utf-8",
    )

    errors = repo_hygiene.scan_personal_paths(tmp_path, ["CLAUDE.md"])

    assert len(errors) == 1
    assert "CLAUDE.md:2" in errors[0]
    assert "/Users/johndoe/" in errors[0]


def test_claude_md_with_home_path_is_blocked(tmp_path):
    """/home/<user>/ paths in CLAUDE.md are blocked (Linux workstation leak)."""
    repo_hygiene = load_repo_hygiene()
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(
        "cd /home/devuser/code/perpetua-tools && npm install\n",
        encoding="utf-8",
    )

    errors = repo_hygiene.scan_personal_paths(tmp_path, ["CLAUDE.md"])

    assert len(errors) == 1
    assert "/home/devuser/" in errors[0]


def test_claude_md_with_portable_paths_passes(tmp_path):
    """CLAUDE.md using portable path tokens must pass the scan cleanly."""
    repo_hygiene = load_repo_hygiene()
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(
        "## Setup\n"
        "Run from `$OPENCLAW_ROOT` or `$REPO_ROOT`.\n"
        "Shorthand: `~/projects/perpetua-tools`.\n"
        "Example path: /Users/you/projects is fine (placeholder username).\n",
        encoding="utf-8",
    )

    errors = repo_hygiene.scan_personal_paths(tmp_path, ["CLAUDE.md"])

    assert errors == [], f"Portable-path CLAUDE.md should pass: {errors}"


# ---------------------------------------------------------------------------
# full script smoke test
# ---------------------------------------------------------------------------

def test_repo_hygiene_script_runs_clean():
    result = subprocess.run(
        [sys.executable, "scripts/review/repo_hygiene.py", "."],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_personal_path_windows_placeholder_not_flagged(tmp_path):
    """Windows C:\\Users\\username placeholder must NOT be flagged — bug was group(2)=None."""
    f = tmp_path / "README.md"
    f.write_text("Copy files to C:\\Users\\username\\AppData\\Local\\hermes\n")
    mod = load_repo_hygiene()
    errors = mod.scan_personal_paths(tmp_path, ["README.md"])
    assert errors == [], f"placeholder path incorrectly flagged: {errors}"


def test_personal_path_windows_real_username_flagged(tmp_path):
    """Windows C:\\Users\\realname (non-placeholder) MUST be flagged."""
    f = tmp_path / "README.md"
    f.write_text("See C:\\Users\\alice\\Downloads\\repo\n")
    mod = load_repo_hygiene()
    errors = mod.scan_personal_paths(tmp_path, ["README.md"])
    assert any("alice" in e for e in errors), f"real username not flagged: {errors}"
