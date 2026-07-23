"""Regression coverage for graduated-memory hygiene exemptions.

Operational lessons may legitimately retain RFC1918 addresses as evidence, but
only graduated candidate JSON receives that narrow topology exemption. All
other .agent privacy and secret guards remain active.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parent.parent
HYGIENE_PATH = ROOT / "scripts" / "review" / "repo_hygiene.py"


def load_repo_hygiene():
    spec = importlib.util.spec_from_file_location("repo_hygiene_graduated", HYGIENE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_graduated_candidate_allows_rfc1918_operational_evidence(tmp_path):
    repo_hygiene = load_repo_hygiene()
    candidate = (
        tmp_path
        / ".agent"
        / "memory"
        / "candidates"
        / "graduated"
        / "lesson_network.json"
    )
    candidate.parent.mkdir(parents=True)
    candidate.write_text(
        '{"claim":"LAN peer moved from 192.168.1.10 to 192.168.1.11"}\n',
        encoding="utf-8",
    )

    errors = repo_hygiene.scan_agent_private_surface(
        tmp_path,
        [".agent/memory/candidates/graduated/lesson_network.json"],
    )

    assert errors == []


def test_non_graduated_memory_still_blocks_rfc1918_topology(tmp_path):
    repo_hygiene = load_repo_hygiene()
    note = tmp_path / ".agent" / "memory" / "working" / "network.md"
    note.parent.mkdir(parents=True)
    note.write_text("Connect to 192.168.1.10 for the peer service.\n", encoding="utf-8")

    errors = repo_hygiene.scan_agent_private_surface(
        tmp_path,
        [".agent/memory/working/network.md"],
    )

    assert errors
    assert any("topology" in error.lower() or "private" in error.lower() for error in errors)


def test_graduated_candidate_does_not_bypass_email_guard(tmp_path):
    repo_hygiene = load_repo_hygiene()
    candidate = (
        tmp_path
        / ".agent"
        / "memory"
        / "candidates"
        / "graduated"
        / "lesson_email.json"
    )
    candidate.parent.mkdir(parents=True)
    candidate.write_text(
        '{"claim":"Contact synthetic.owner@private-mail.test about 192.168.1.10"}\n',
        encoding="utf-8",
    )

    errors = repo_hygiene.scan_agent_private_surface(
        tmp_path,
        [".agent/memory/candidates/graduated/lesson_email.json"],
    )

    assert errors
    assert any("email" in error.lower() for error in errors)
