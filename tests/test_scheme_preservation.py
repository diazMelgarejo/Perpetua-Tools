"""Contract tests: active_tilting transport reconstruction preserves scheme."""

from __future__ import annotations

import pytest

from orchestrator.model_registry import ModelRegistry, _build_tilting_url


def test_build_tilting_url_preserves_https():
    assert _build_tilting_url("https://win-box.example:1234", 11434) == (
        "https://win-box.example:11434"
    )


def test_build_tilting_url_defaults_http_for_bare_hostport():
    assert _build_tilting_url("127.0.1.1:1234", 11434) == (
        "http://127.0.1.1:11434"
    )


def test_build_tilting_url_no_double_scheme():
    result = _build_tilting_url("http://127.0.1.1:1234", 11434)
    assert result == "http://127.0.1.1:11434"
    assert "http://http" not in result


def test_build_tilting_url_returns_none_without_hostname():
    assert _build_tilting_url("", 11434) is None


@pytest.fixture
def registry():
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    return ModelRegistry(config_dir=str(repo_root / "config"))


def test_resolve_host_ollama_preserves_https_scheme(registry, monkeypatch):
    """CodeRabbit #198: do not downgrade https discovery to http for Ollama."""
    monkeypatch.delenv("PT_DISABLE_LIVE_MODEL_PROBES", raising=False)
    monkeypatch.setattr(
        "orchestrator.lan_discovery.detect_active_tilting_ip",
        lambda: "https://127.0.1.1:1234",
    )
    ollama_item = {
        "device": "win-rtx3080",
        "backend": "ollama",
        "host": "${WIN_OLLAMA_ENDPOINT:-http://127.0.1.1}",
        "port": 11434,
        "name": "qwen3-30b-autoresearch-critic",
    }
    assert registry._resolve_host(ollama_item) == "https://127.0.1.1:11434"


def test_resolve_host_lmstudio_returns_tilted_unchanged(registry, monkeypatch):
    monkeypatch.delenv("PT_DISABLE_LIVE_MODEL_PROBES", raising=False)
    monkeypatch.setattr(
        "orchestrator.lan_discovery.detect_active_tilting_ip",
        lambda: "https://127.0.1.1:1234",
    )
    lm_item = {
        "device": "win-rtx3080",
        "backend": "lm-studio",
        "host": "${LM_STUDIO_WIN_ENDPOINT:-http://127.0.1.1}",
        "port": 1234,
        "name": "Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-v2",
    }
    assert registry._resolve_host(lm_item) == "https://127.0.1.1:1234"
