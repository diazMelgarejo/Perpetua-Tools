"""Tests for path_hygiene.sanitize_private_identity_leaks and its chaining
into sanitize_tracked_path_leaks (the memory-write boundary all
.agent/memory writers, including learn.py, go through).

Prevention counterpart to the incident this closes: a real email leaked
into lessons.jsonl (superseded lesson_23e51efcde2f -> lesson_c3b24dc506a6)
because learn.py scrubbed path leaks at staging time but never identity
literals, so the leak reached tracked memory and was only caught later by
the pre-commit hygiene gate on a subsequent commit. These tests assert the
leak can no longer reach the staged text at all.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

import pytest


def _load_path_hygiene():
    module_path = Path(__file__).parent.parent / ".agent" / "memory" / "path_hygiene.py"
    spec = importlib.util.spec_from_file_location("path_hygiene_under_test", module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["path_hygiene_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def configured_literals(monkeypatch):
    """Write a synthetic local verboten-literals file and point the env var
    at it, restoring the prior env state afterward. Uses only synthetic,
    example.invalid-style values -- never a real identity, per this
    project's own testing standard for private-literal coverage.
    """
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".local", delete=False, encoding="utf-8")
    tmp.write(
        "owner_gmail=synthetic.owner@example.invalid\n"
        "owner_name=Synthetic.Owner\n"
        "forbidden_attribution=synthetic-forbidden-handle\n"
    )
    tmp.close()
    monkeypatch.setenv("OPENCLAW_VERBOTEN_LITERALS", tmp.name)
    yield tmp.name
    os.unlink(tmp.name)


def test_no_config_is_a_safe_no_op(monkeypatch):
    monkeypatch.delenv("OPENCLAW_VERBOTEN_LITERALS", raising=False)
    ph = _load_path_hygiene()
    text = "A normal lesson claim with no private data at all."
    assert ph.sanitize_tracked_path_leaks(text) == text


def test_owner_gmail_is_redacted(configured_literals):
    ph = _load_path_hygiene()
    text = "Contact synthetic.owner@example.invalid for details."
    result = ph.sanitize_tracked_path_leaks(text)
    assert "synthetic.owner@example.invalid" not in result
    assert "<owner Gmail identity>" in result


def test_owner_name_is_redacted(configured_literals):
    ph = _load_path_hygiene()
    text = "Approved by Synthetic.Owner in review."
    result = ph.sanitize_tracked_path_leaks(text)
    assert "Synthetic.Owner" not in result


def test_forbidden_attribution_is_redacted(configured_literals):
    ph = _load_path_hygiene()
    text = "Do not attribute to synthetic-forbidden-handle."
    result = ph.sanitize_tracked_path_leaks(text)
    assert "synthetic-forbidden-handle" not in result


def test_case_insensitive_match(configured_literals):
    ph = _load_path_hygiene()
    text = "Contact SYNTHETIC.OWNER@EXAMPLE.INVALID please."
    result = ph.sanitize_tracked_path_leaks(text)
    assert "synthetic.owner@example.invalid" not in result.lower()


def test_redaction_composes_with_existing_path_scrub(configured_literals):
    """The two scrubs must not interfere with each other -- an identity
    literal and a workstation path in the same string are both redacted."""
    ph = _load_path_hygiene()
    text = "synthetic.owner@example.invalid saved a file at /Users/alice/notes.md"
    result = ph.sanitize_tracked_path_leaks(text)
    assert "synthetic.owner@example.invalid" not in result
    assert "/Users/alice" not in result
    assert "$HOME" in result


def test_no_op_when_text_does_not_contain_any_configured_literal(configured_literals):
    ph = _load_path_hygiene()
    text = "This claim mentions nothing private at all."
    assert ph.sanitize_tracked_path_leaks(text) == text
