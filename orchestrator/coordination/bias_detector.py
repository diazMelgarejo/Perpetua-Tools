"""Coordination bias and echo loop detector for multi-agent workflows.

Ported from AlphaClaw observability draft to detect Agreement Collapse (>0.85),
Echo Loops (>0.92 SequenceMatcher), and Groupthink across parallel agent decisions.
Reference: orama-system docs/v2/54-tri-stack-observability-and-l3-egress-v2.md § 4.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from orchestrator.gossip_bus import GossipBus


@dataclass(frozen=True)
class BiasScore:
    total_bias_score: float
    bias_types: Dict[str, float]
    agreement_collapse: bool
    echo_loop_detected: bool


class CoordinationBiasDetector:
    """Mathematical bias and echo loop detector for multi-agent coordination."""

    def __init__(self, max_history: int = 20) -> None:
        self.history: List[Dict[str, Any]] = []
        self.max_history = max_history

    def add_decision(
        self,
        confidence: float,
        reasoning_text: str,
        agent_outputs: Optional[List[str]] = None,
    ) -> None:
        """Record an agent decision with confidence and reasoning text."""
        self.history.append(
            {"confidence": float(confidence), "text": str(reasoning_text)[:500]}
        )
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def detect_bias(self) -> BiasScore:
        """Evaluate the rolling window for agreement collapse and echo loops."""
        if len(self.history) < 4:
            return BiasScore(0.0, {}, False, False)

        confidences = [d["confidence"] for d in self.history]
        texts = [d["text"] for d in self.history]

        n = len(confidences)
        variance_sum = sum(
            abs(confidences[i] - confidences[i - 1]) for i in range(1, n)
        )
        collapse_score = 1.0 - (variance_sum / (n - 1))
        agreement_collapse = collapse_score > 0.85

        echo_loop = any(
            SequenceMatcher(None, texts[i], texts[i - 1]).ratio() > 0.92
            for i in range(1, len(texts))
        )

        avg_conf = sum(confidences) / n
        bias_types = {
            "confirmation_bias": max(0.0, (avg_conf - 0.5) * 2),
            "groupthink": max(0.0, collapse_score),
            "hallucination_risk": max(0.0, 1.0 - avg_conf),
        }

        total_bias = min(1.0, sum(bias_types.values()) / 2)

        return BiasScore(
            total_bias_score=round(total_bias, 3),
            bias_types={k: round(v, 3) for k, v in bias_types.items()},
            agreement_collapse=agreement_collapse,
            echo_loop_detected=echo_loop,
        )


_GOSSIP_EVENT_TYPES = ("dispatch", "status_update")
_POSITIVE_SIGNAL_WORDS = ("done", "complete", "completed", "green", "passed", "pushed", "verified", "merged")
_NEGATIVE_SIGNAL_WORDS = ("blocked", "fail", "failed", "error", "collision", "conflict")


def _estimate_confidence(event_type: str, message: str) -> float:
    """Derive a confidence proxy from a GossipBus event, since dispatch/status_update
    payloads carry no self-reported confidence score (unlike PeerObservation.compute_confidence()
    in orchestrator/membership.py). A constant value here would make agreement_collapse's
    variance-based check trivially always true (zero variance across every decision) --
    that degenerate case is exactly what this heuristic exists to avoid.

    dispatch: new work assigned, no outcome yet -- neutral-low.
    status_update: keyword-scanned for a completion or a blocker/failure signal.
    """
    lowered = message.lower()
    if event_type == "status_update":
        if any(word in lowered for word in _NEGATIVE_SIGNAL_WORDS):
            return 0.2
        if any(word in lowered for word in _POSITIVE_SIGNAL_WORDS):
            return 0.95
        return 0.6
    if event_type == "dispatch":
        return 0.5
    return 0.6


async def fetch_bias_detector_events(bus: GossipBus) -> list[dict]:
    """Fetch dispatch/status_update events via targeted SQL, not a bounded tail().

    Mirrors reorder_buffer.py's fetch_reorder_buffer_events(): unrelated heartbeat
    traffic can push relevant events out of a size-bounded tail() window.
    """
    type_placeholders = ",".join("?" for _ in _GOSSIP_EVENT_TYPES)
    query = (
        "SELECT id, event_uuid, ts, event_type, payload_json FROM gossip "
        f"WHERE event_type IN ({type_placeholders}) "
        "ORDER BY id ASC"
    )
    async with bus.connect() as db:
        cursor = await db.execute(query, list(_GOSSIP_EVENT_TYPES))
        rows = await cursor.fetchall()
    return [
        {
            "row_id": row[0],
            "uuid": row[1],
            "ts": row[2],
            "event_type": row[3],
            "payload": json.loads(row[4]),
        }
        for row in rows
    ]


async def feed_bias_detector_from_gossip(
    bus: GossipBus,
    detector: CoordinationBiasDetector,
    *,
    agent_id: Optional[str] = None,
) -> BiasScore:
    """Replay GossipBus dispatch/status_update events into ``detector`` and
    return the resulting BiasScore.

    ``agent_id``, when given, restricts replay to events whose payload
    ``agent_id`` field matches -- per-agent groupthink/echo-loop detection
    rather than a single mixed history across every agent on the board.
    """
    events = await fetch_bias_detector_events(bus)
    for ev in events:
        payload = ev["payload"]
        if agent_id is not None and payload.get("agent_id") != agent_id:
            continue
        message = str(payload.get("message", ""))
        if not message:
            continue
        confidence = _estimate_confidence(ev["event_type"], message)
        detector.add_decision(confidence, message)
    return detector.detect_bias()
