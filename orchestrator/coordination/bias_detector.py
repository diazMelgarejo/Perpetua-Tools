"""Coordination bias and echo loop detector for multi-agent workflows.

Ported from AlphaClaw observability draft to detect Agreement Collapse (>0.85),
Echo Loops (>0.92 SequenceMatcher), and Groupthink across parallel agent decisions.
Reference: orama-system docs/v2/54-tri-stack-observability-and-l3-egress-v2.md § 4.
"""
from __future__ import annotations

import json
import re
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
        mean_conf = sum(confidences) / n
        variance = sum((c - mean_conf) ** 2 for c in confidences) / n
        stddev = variance ** 0.5
        # Low dispersion around the mean means the group is converging on the
        # same value -- collapse_score is high when stddev is near 0, low
        # when confidences are spread out (including a bimodal split, which
        # has HIGH stddev despite looking locally "smooth" step to step).
        collapse_score = max(0.0, 1.0 - (stddev * 2))
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


_HEARTBEAT_KINDS = (
    "task_complete",
    "task_failed",
    "task_abandoned",
    "agent_killed",
    "agent_note",
)
_POSITIVE_SIGNAL_WORDS = ("done", "complete", "completed", "green", "passed", "pushed", "verified", "merged")
_NEGATIVE_SIGNAL_WORDS = ("blocked", "fail", "failed", "error", "collision", "conflict")


def _estimate_confidence(kind: str, message: str) -> float:
    """Derive a confidence proxy from a GossipBus heartbeat event, since these
    payloads carry no self-reported confidence score (unlike
    PeerObservation.compute_confidence() in orchestrator/membership.py). A
    constant value here would make agreement_collapse's variance-based check
    trivially always true (zero variance across every decision) -- that
    degenerate case is exactly what this heuristic exists to avoid.

    task_complete/agent_note: keyword-scanned for a completion or a
    blocker/failure signal. task_failed/task_abandoned/agent_killed: an
    explicit negative outcome already, regardless of message content.
    """
    if kind in ("task_failed", "task_abandoned", "agent_killed"):
        return 0.2
    lowered = message.lower()
    words_lowered = set(re.findall(r"[a-z]+", lowered))
    if words_lowered & set(_NEGATIVE_SIGNAL_WORDS):
        return 0.2
    if words_lowered & set(_POSITIVE_SIGNAL_WORDS):
        return 0.95
    return 0.6


async def fetch_bias_detector_events(bus: GossipBus, max_rows: int = 20) -> list[dict]:
    """Fetch status-bearing heartbeat events via targeted SQL, not a bounded
    tail(). Real emitters (heartbeat_monitor.py, coordination/task_queue.py,
    coordination/claims.py, coordination/liveness.py) all use event_type
    "heartbeat" with a "kind" payload field distinguishing agent_release,
    task_complete, task_failed, etc. -- there is no "status_update"
    event_type anywhere in production (confirmed against EventType's own
    Literal in gossip_bus.py, which doesn't define one either).

    Mirrors reorder_buffer.py's fetch_reorder_buffer_events(): unrelated
    heartbeat traffic (agent_pulse, agent_claim, buffer_drained, etc.) can
    push relevant events out of a size-bounded tail() window, so this filters
    at the SQL layer by kind, not just event_type, and applies LIMIT there
    too rather than reading the whole table and discarding most of it in
    Python.
    """
    kind_placeholders = ",".join("?" for _ in _HEARTBEAT_KINDS)
    query = (
        "SELECT id, event_uuid, ts, event_type, payload_json FROM gossip "
        "WHERE event_type = 'heartbeat' "
        f"AND json_extract(payload_json, '$.kind') IN ({kind_placeholders}) "
        "ORDER BY id DESC LIMIT ?"
    )
    async with bus.connect() as db:
        cursor = await db.execute(query, [*_HEARTBEAT_KINDS, max_rows])
        rows = await cursor.fetchall()
    rows.reverse()  # restore ascending id order after DESC+LIMIT
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
    """Replay GossipBus heartbeat/task-outcome events into ``detector`` and
    return the resulting BiasScore.

    ``agent_id``, when given, restricts replay to events whose payload
    ``agent_id`` field matches -- per-agent groupthink/echo-loop detection
    rather than a single mixed history across every agent on the board.
    """
    events = await fetch_bias_detector_events(bus, max_rows=detector.max_history)
    for ev in events:
        payload = ev["payload"]
        if agent_id is not None and payload.get("agent_id") != agent_id:
            continue
        kind = str(payload.get("kind", ""))
        message = str(payload.get("message") or payload.get("reason") or payload.get("task") or "")
        if not message:
            continue
        confidence = _estimate_confidence(kind, message)
        detector.add_decision(confidence, message)
    return detector.detect_bias()
