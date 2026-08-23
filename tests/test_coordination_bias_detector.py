"""Tests for CoordinationBiasDetector in orchestrator/coordination/bias_detector.py.

Verifies agreement collapse, echo loop detection, below-threshold cases, and history window management.
"""
from __future__ import annotations

import pytest
from orchestrator.coordination.bias_detector import (
    BiasScore,
    CoordinationBiasDetector,
)


class TestCoordinationBiasDetector:
    """Test suite for CoordinationBiasDetector."""

    def test_minimum_history_returns_zero_score(self) -> None:
        detector = CoordinationBiasDetector()
        detector.add_decision(0.9, "Reasoning step 1")
        detector.add_decision(0.9, "Reasoning step 2")
        detector.add_decision(0.9, "Reasoning step 3")
        score = detector.detect_bias()
        assert score == BiasScore(0.0, {}, False, False)

    def test_agreement_collapse_trigger_at_exact_threshold(self) -> None:
        detector = CoordinationBiasDetector()
        # Identical confidence -> collapse_score = 1.0 > 0.85
        diverse_texts = [
            "Alpha agent analyzed memory footprint and CPU utilization profiles.",
            "Beta worker examined PostgreSQL connection pool timeout configurations.",
            "Gamma orchestrator verified cryptographic hashes of the local dataset.",
            "Delta monitor checked WebSocket heartbeat intervals across worker nodes.",
            "Epsilon auditor reviewed TLS certificate expiration and cipher suites.",
        ]
        for text in diverse_texts:
            detector.add_decision(0.95, text)
        score = detector.detect_bias()
        assert score.agreement_collapse is True
        assert score.bias_types["groupthink"] > 0.85
        assert score.echo_loop_detected is False

    def test_echo_loop_detected_trigger_at_exact_threshold(self) -> None:
        detector = CoordinationBiasDetector()
        # Varied confidences (no agreement collapse), but nearly identical reasoning (>0.92 ratio)
        confidences = [0.2, 0.8, 0.3, 0.9]
        repeated_text = "The agent verified that all invariants match the expected system state exactly."
        for conf in confidences:
            detector.add_decision(conf, repeated_text)
        score = detector.detect_bias()
        assert score.echo_loop_detected is True
        assert score.agreement_collapse is False

    def test_below_threshold_no_detection(self) -> None:
        detector = CoordinationBiasDetector()
        confidences = [0.1, 0.8, 0.2, 0.9, 0.3]
        texts = [
            "Analyzing network packet filters and socket pinning boundaries.",
            "Evaluating test isolation in pytest asyncio event loop fixtures.",
            "Refactoring token-cliff refusal gate in FastAPI orchestrator.",
            "Generating comprehensive verification report for multi-agent mesh.",
            "Checking SQLite GossipBus event ordering and transaction isolation.",
        ]
        for conf, text in zip(confidences, texts):
            detector.add_decision(conf, text)
        score = detector.detect_bias()
        assert score.agreement_collapse is False
        assert score.echo_loop_detected is False
        assert score.total_bias_score < 0.85

    def test_history_window_capped_at_max(self) -> None:
        detector = CoordinationBiasDetector(max_history=20)
        for i in range(30):
            detector.add_decision(0.5, f"Decision {i}")
        assert len(detector.history) == 20
        assert detector.history[-1]["text"] == "Decision 29"
