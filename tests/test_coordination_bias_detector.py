"""Tests for CoordinationBiasDetector in orchestrator/coordination/bias_detector.py.

Verifies agreement collapse, echo loop detection, below-threshold cases, and history window management.
"""
from __future__ import annotations

import pytest
from orchestrator.coordination.bias_detector import (
    BiasScore,
    CoordinationBiasDetector,
    fetch_bias_detector_events,
    feed_bias_detector_from_gossip,
)
from orchestrator.gossip_bus import GossipBus


@pytest.fixture
def make_bus(tmp_path):
    """Factory for temporary, freshly-initialised GossipBus instances (matches
    tests/test_agent_coordination_reorder_buffer.py's fixture idiom)."""

    async def _factory():
        db_path = str(tmp_path / "coordination_bias_test.db")
        bus = GossipBus(db_path)
        await bus.init_db()
        return bus

    return _factory


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


class TestFeedBiasDetectorFromGossip:
    """Wiring: replay GossipBus dispatch/status_update events into a detector."""

    @pytest.mark.asyncio
    async def test_fetch_only_returns_dispatch_and_status_update_events(self, make_bus) -> None:
        bus = await make_bus()
        await bus.emit("dispatch", {"agent_id": "a", "to": "b", "message": "do the thing"})
        await bus.emit("heartbeat", {"agent_id": "a", "kind": "pulse"})
        await bus.emit("status_update", {"agent_id": "a", "to": "b", "message": "done"})
        events = await fetch_bias_detector_events(bus)
        assert [e["event_type"] for e in events] == ["dispatch", "status_update"]

    @pytest.mark.asyncio
    async def test_feed_ignores_unrelated_heartbeat_noise(self, make_bus) -> None:
        bus = await make_bus()
        for _ in range(50):
            await bus.emit("heartbeat", {"agent_id": "noisy", "kind": "pulse"})
        await bus.emit("dispatch", {"agent_id": "a", "to": "b", "message": "task one"})
        await bus.emit("status_update", {"agent_id": "a", "to": "b", "message": "task one done"})
        detector = CoordinationBiasDetector()
        await feed_bias_detector_from_gossip(bus, detector)
        assert len(detector.history) == 2

    @pytest.mark.asyncio
    async def test_feed_filters_by_agent_id(self, make_bus) -> None:
        bus = await make_bus()
        await bus.emit("dispatch", {"agent_id": "agent-a", "to": "x", "message": "a's task"})
        await bus.emit("dispatch", {"agent_id": "agent-b", "to": "x", "message": "b's task"})
        detector = CoordinationBiasDetector()
        await feed_bias_detector_from_gossip(bus, detector, agent_id="agent-a")
        assert len(detector.history) == 1
        assert detector.history[0]["text"] == "a's task"

    @pytest.mark.asyncio
    async def test_feed_derives_nonconstant_confidence_from_event_content(self, make_bus) -> None:
        """A constant confidence would make agreement_collapse trivially always
        true (zero variance). This is the regression guard for that degenerate case."""
        bus = await make_bus()
        await bus.emit("dispatch", {"agent_id": "a", "to": "b", "message": "starting work"})
        await bus.emit("status_update", {"agent_id": "a", "to": "b", "message": "all green, pushed"})
        await bus.emit("status_update", {"agent_id": "a", "to": "b", "message": "BLOCKED: conflict"})
        detector = CoordinationBiasDetector()
        await feed_bias_detector_from_gossip(bus, detector)
        confidences = {d["confidence"] for d in detector.history}
        assert len(confidences) > 1

    @pytest.mark.asyncio
    async def test_feed_returns_bias_score(self, make_bus) -> None:
        bus = await make_bus()
        for i in range(5):
            await bus.emit("status_update", {"agent_id": "a", "to": "b", "message": f"step {i} done"})
        detector = CoordinationBiasDetector()
        score = await feed_bias_detector_from_gossip(bus, detector)
        assert isinstance(score, BiasScore)
