"""Tests for agent_launcher.resolve_local_or_remote's SSRF handling."""
from __future__ import annotations

import pytest

import perpetua_tools.agent_launcher as agent_launcher


def test_resolve_local_or_remote_uses_fallback_ip_when_remote(monkeypatch):
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_MAC", False)
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_WINDOWS", True)
    result = agent_launcher.resolve_local_or_remote(
        "mac", 11434, fallback_ip="192.168.1.50"
    )
    assert result == "http://192.168.1.50:11434"


def test_resolve_local_or_remote_rejects_link_local_metadata_override(monkeypatch):
    """Regression: the env_var override path returned an operator-supplied
    URL with zero SSRF host-classification when the target role is remote
    (is_local False) -- only the is_local/loopback-heal branch was checked
    for locality, never for a blocked destination range. An
    OLLAMA_WINDOWS_ENDPOINT=http://169.254.169.254:11434 override would be
    returned and later fetched with no validation."""
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_MAC", True)
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_WINDOWS", False)
    monkeypatch.setenv("TEST_REMOTE_ENDPOINT", "http://169.254.169.254:11434")
    result = agent_launcher.resolve_local_or_remote(
        "windows", 11434, env_var="TEST_REMOTE_ENDPOINT", fallback_ip="127.0.0.1"
    )
    assert "169.254.169.254" not in result


def test_resolve_local_or_remote_redacts_rejected_override(monkeypatch, caplog):
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_MAC", True)
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_WINDOWS", False)
    monkeypatch.setenv("TEST_REMOTE_ENDPOINT", "http://user:secret@1.1.1.1:11434")

    result = agent_launcher.resolve_local_or_remote(
        "windows", 11434, env_var="TEST_REMOTE_ENDPOINT", fallback_ip="127.0.0.1"
    )

    assert result == "http://127.0.0.1:11434"
    assert "secret" not in caplog.text


def test_resolve_local_or_remote_rejects_link_local_metadata_fallback(monkeypatch):
    """A rejected override must not make an unsafe fallback reachable."""
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_MAC", True)
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_WINDOWS", False)
    monkeypatch.setenv("TEST_REMOTE_ENDPOINT", "http://169.254.169.254:11434")
    result = agent_launcher.resolve_local_or_remote(
        "windows",
        11434,
        env_var="TEST_REMOTE_ENDPOINT",
        fallback_ip="169.254.169.254",
    )
    assert result == "http://127.0.0.1:11434"


def test_resolve_local_or_remote_still_accepts_lan_override(monkeypatch):
    """Confirm the fix isn't over-broad -- a genuine RFC1918 override must
    still pass through unchanged."""
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_MAC", True)
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_WINDOWS", False)
    monkeypatch.setenv("TEST_REMOTE_ENDPOINT", "http://192.168.1.77:11434")
    result = agent_launcher.resolve_local_or_remote(
        "windows", 11434, env_var="TEST_REMOTE_ENDPOINT", fallback_ip="127.0.0.1"
    )
    assert result == "http://192.168.1.77:11434"
