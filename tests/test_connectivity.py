from __future__ import annotations

from unittest.mock import patch

from orchestrator import connectivity


def test_endpoint_online_false_when_endpoint_up_but_model_not_served():
    with patch(
        "orchestrator.connectivity._served_model_ids",
        return_value=(True, frozenset()),
    ):
        assert connectivity.endpoint_online(
            "http://127.0.0.1:1234",
            "lm-studio",
            "Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-v2",
            ttl=0,
        ) is False


def test_endpoint_online_true_when_model_is_served():
    served = frozenset({"qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2"})
    with patch(
        "orchestrator.connectivity._served_model_ids",
        return_value=(True, served),
    ):
        assert connectivity.endpoint_online(
            "http://127.0.0.1:1234",
            "lm-studio",
            "Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-v2",
            ttl=0,
        ) is True


def test_endpoint_online_uses_ollama_tags_for_mac_ollama_backend():
    with patch(
        "orchestrator.connectivity.httpx.get",
    ) as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "models": [{"name": "qwen3.5:9b"}],
        }
        assert connectivity.endpoint_online(
            "http://127.0.0.1:11434",
            "mac-ollama",
            "qwen3.5:9b",
            ttl=0,
        ) is True
        mock_get.assert_called_once()
        assert mock_get.call_args.args[0].endswith("/api/tags")


def test_endpoint_online_generic_reachability_without_model_id():
    with patch(
        "orchestrator.connectivity._served_model_ids",
        return_value=(True, frozenset()),
    ):
        assert connectivity.endpoint_online(
            "http://127.0.0.1:1234",
            "lm-studio",
            "",
            ttl=0,
        ) is True
