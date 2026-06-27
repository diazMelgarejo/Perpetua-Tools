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
