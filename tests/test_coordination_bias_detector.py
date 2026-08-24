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
        assert score == BiasScore(
            total_bias_score=0.0,
            bias_types={},
            agreement_collapse=False,
            echo_loop_detected=False,
            distinct_agent_count=0,
            evidence_window_size=3,
            coordination_risk="insufficient_evidence",
        )

    def test_agreement_collapse_trigger_at_exact_threshold(self) -> None:
        detector = CoordinationBiasDetector()
        # Identical high confidence across 5 distinct agents -> agreement_collapse = True
        diverse_texts = [
            "Alpha agent analyzed memory footprint and CPU utilization profiles.",
            "Beta worker examined PostgreSQL connection pool timeout configurations.",
            "Gamma orchestrator verified cryptographic hashes of the local dataset.",
            "Delta monitor checked WebSocket heartbeat intervals across worker nodes.",
            "Epsilon auditor reviewed TLS certificate expiration and cipher suites.",
        ]
        for i, text in enumerate(diverse_texts):
            detector.add_decision(0.95, text, agent_id=f"agent-{i}")
        score = detector.detect_bias()
        assert score.agreement_collapse is True
        assert score.distinct_agent_count == 5
        assert score.bias_types["groupthink"] > 0.85
        assert score.echo_loop_detected is False
        assert score.coordination_risk == "high"

    def test_agreement_collapse_triggers_at_exact_three_agent_boundary(self) -> None:
        detector = CoordinationBiasDetector()
        # Exactly 3 distinct agents across 4 decisions (minimum activation boundary) -> agreement_collapse = True
        diverse_texts = [
            "Alpha agent analyzed memory footprint and CPU utilization profiles.",
            "Beta worker examined PostgreSQL connection pool timeout configurations.",
            "Gamma orchestrator verified cryptographic hashes of the local dataset.",
            "Alpha agent audited WebSocket heartbeat intervals across worker nodes.",
        ]
        agents = ["agent-0", "agent-1", "agent-2", "agent-0"]
        for agent, text in zip(agents, diverse_texts):
            detector.add_decision(0.95, text, agent_id=agent)
        score = detector.detect_bias()
        assert score.distinct_agent_count == 3
        assert score.agreement_collapse is True
        assert score.bias_types["groupthink"] > 0.85
        assert score.echo_loop_detected is False
        assert score.coordination_risk == "high"

    def test_agreement_collapse_does_not_trigger_with_only_two_distinct_agents(self) -> None:
        detector = CoordinationBiasDetector()
        # Exactly 2 distinct agents (< 3) -> groupthink is 0.0, agreement_collapse = False
        diverse_texts = [
            "Alpha agent analyzed memory footprint and CPU utilization profiles.",
            "Beta worker examined PostgreSQL connection pool timeout configurations.",
            "Alpha agent reviewed database migration indexing strategies.",
            "Beta worker verified cryptographic hash signatures of payloads.",
        ]
        agents = ["agent-alpha", "agent-beta", "agent-alpha", "agent-beta"]
        for agent, text in zip(agents, diverse_texts):
            detector.add_decision(0.95, text, agent_id=agent)
        score = detector.detect_bias()
        assert score.agreement_collapse is False
        assert score.distinct_agent_count == 2
        assert score.bias_types["groupthink"] == 0.0

    def test_single_agent_high_consensus_does_not_trigger_groupthink(self) -> None:
        detector = CoordinationBiasDetector()
        # Identical high confidence from only 1 agent -> groupthink is 0.0, agreement_collapse = False
        diverse_texts = [
            "Alpha agent analyzed memory footprint and CPU utilization profiles.",
            "Beta worker examined PostgreSQL connection pool timeout configurations.",
            "Gamma orchestrator verified cryptographic hashes of the local dataset.",
            "Delta monitor checked WebSocket heartbeat intervals across worker nodes.",
        ]
        for text in diverse_texts:
            detector.add_decision(0.95, text, agent_id="agent-solo")
        score = detector.detect_bias()
        assert score.agreement_collapse is False
        assert score.distinct_agent_count == 1
        assert score.bias_types["groupthink"] == 0.0
        assert score.echo_loop_detected is False

    def test_single_agent_repeated_reasoning_triggers_echo_loop_without_groupthink(self) -> None:
        detector = CoordinationBiasDetector()
        # Repeated identical reasoning from agent-solo -> echo_loop_detected = True, agreement_collapse = False
        repeated_text = "The agent verified that all invariants match the expected system state exactly."
        for _ in range(4):
            detector.add_decision(0.95, repeated_text, agent_id="agent-solo")
        score = detector.detect_bias()
        assert score.distinct_agent_count == 1
        assert score.echo_loop_detected is True
        assert score.agreement_collapse is False
        assert score.bias_types["groupthink"] == 0.0

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
    """Wiring: replay real GossipBus heartbeat/task-outcome events into a
    detector. Uses event_type="heartbeat" with a "kind" payload field, since
    that's what every real emitter in this codebase actually produces
    (heartbeat_monitor.py, coordination/task_queue.py, coordination/claims.py,
    coordination/liveness.py) -- "status_update" was never a real EventType
    (confirmed against gossip_bus.py's own Literal) and no production code
    anywhere emits it; these tests previously asserted that never-real shape.
    """

    @pytest.mark.asyncio
    async def test_fetch_only_returns_heartbeat_outcome_kinds(self, make_bus) -> None:
        bus = await make_bus()
        await bus.emit("heartbeat", {"agent_id": "a", "kind": "task_complete", "message": "do the thing"})
        await bus.emit("heartbeat", {"agent_id": "a", "kind": "agent_pulse"})
        await bus.emit("heartbeat", {"agent_id": "a", "kind": "task_failed", "message": "boom"})
        events = await fetch_bias_detector_events(bus)
        kinds = [e["payload"]["kind"] for e in events]
        assert kinds == ["task_complete", "task_failed"]

    @pytest.mark.asyncio
    async def test_feed_ignores_unrelated_heartbeat_noise(self, make_bus) -> None:
        bus = await make_bus()
        for _ in range(50):
            await bus.emit("heartbeat", {"agent_id": "noisy", "kind": "agent_pulse"})
        await bus.emit("heartbeat", {"agent_id": "a", "kind": "task_complete", "message": "task one done"})
        await bus.emit("heartbeat", {"agent_id": "a", "kind": "agent_note", "message": "task two note"})
        detector = CoordinationBiasDetector()
        await feed_bias_detector_from_gossip(bus, detector)
        assert len(detector.history) == 2

    @pytest.mark.asyncio
    async def test_feed_filters_by_agent_id(self, make_bus) -> None:
        bus = await make_bus()
        await bus.emit("heartbeat", {"agent_id": "agent-a", "kind": "task_complete", "message": "a's task"})
        await bus.emit("heartbeat", {"agent_id": "agent-b", "kind": "task_complete", "message": "b's task"})
        detector = CoordinationBiasDetector()
        await feed_bias_detector_from_gossip(bus, detector, agent_id="agent-a")
        assert len(detector.history) == 1
        assert detector.history[0]["text"] == "a's task"

    @pytest.mark.asyncio
    async def test_agent_filter_applies_before_history_limit(self, make_bus) -> None:
        bus = await make_bus()
        for i in range(4):
            await bus.emit("heartbeat", {"agent_id": "noisy", "kind": "task_complete", "message": f"noise {i}"})
        await bus.emit("heartbeat", {"agent_id": "agent-a", "kind": "task_complete", "message": "agent-a result"})
        detector = CoordinationBiasDetector(max_history=2)

        await feed_bias_detector_from_gossip(bus, detector, agent_id="agent-a")

        assert [decision["text"] for decision in detector.history] == ["agent-a result"]

    @pytest.mark.asyncio
    async def test_feed_does_not_replay_events_on_consecutive_polls(self, make_bus) -> None:
        bus = await make_bus()
        await bus.emit("heartbeat", {"agent_id": "agent-a", "kind": "task_complete", "message": "one result"})
        detector = CoordinationBiasDetector()

        await feed_bias_detector_from_gossip(bus, detector, agent_id="agent-a")
        await feed_bias_detector_from_gossip(bus, detector, agent_id="agent-a")

        assert [decision["text"] for decision in detector.history] == ["one result"]

    @pytest.mark.asyncio
    async def test_feed_derives_nonconstant_confidence_from_event_content(self, make_bus) -> None:
        """A constant confidence would make agreement_collapse trivially always
        true (zero variance). This is the regression guard for that degenerate case."""
        bus = await make_bus()
        await bus.emit("heartbeat", {"agent_id": "a", "kind": "agent_note", "message": "starting work"})
        await bus.emit("heartbeat", {"agent_id": "a", "kind": "agent_note", "message": "all green, pushed"})
        await bus.emit("heartbeat", {"agent_id": "a", "kind": "task_failed", "message": "BLOCKED: conflict"})
        detector = CoordinationBiasDetector()
        await feed_bias_detector_from_gossip(bus, detector)
        confidences = {d["confidence"] for d in detector.history}
        assert len(confidences) > 1

    @pytest.mark.asyncio
    async def test_feed_reads_task_queue_notes_payload_shape(self, make_bus) -> None:
        """Production task_queue.py emits task_complete/failed/abandoned with
        a 'notes' field, not 'message'. Without notes in the extraction
        chain, feed_bias_detector_from_gossip silently drops every real
        queue outcome event."""
        bus = await make_bus()
        await bus.emit(
            "heartbeat",
            {
                "agent_id": "worker-1",
                "kind": "task_complete",
                "task_id": "task-abc",
                "status": "completed",
                "notes": "pytest passed, pushed branch",
            },
        )
        await bus.emit(
            "heartbeat",
            {
                "agent_id": "worker-1",
                "kind": "task_failed",
                "task_id": "task-def",
                "status": "queued",
                "notes": "Retry 1/3: flaky test",
            },
        )
        detector = CoordinationBiasDetector()
        await feed_bias_detector_from_gossip(bus, detector, agent_id="worker-1")
        assert len(detector.history) == 2
        assert detector.history[0]["text"] == "pytest passed, pushed branch"
        assert detector.history[1]["text"] == "Retry 1/3: flaky test"

    @pytest.mark.asyncio
    async def test_feed_returns_bias_score(self, make_bus) -> None:
        """Strengthened: the original version asserted only isinstance(score,
        BiasScore), which passes even with zero events fed in (detect_bias()
        on an empty history still returns a valid BiasScore(0.0, {}, False,
        False)) -- it never actually proved real events were replayed."""
        bus = await make_bus()
        for i in range(5):
            await bus.emit("heartbeat", {"agent_id": "a", "kind": "agent_note", "message": f"step {i} done"})
        detector = CoordinationBiasDetector()
        score = await feed_bias_detector_from_gossip(bus, detector)
        assert isinstance(score, BiasScore)
        assert len(detector.history) == 5
