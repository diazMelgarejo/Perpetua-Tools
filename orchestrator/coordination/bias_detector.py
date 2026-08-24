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
    distinct_agent_count: int = 0
    evidence_window_size: int = 0
    coordination_risk: str = "low"


class CoordinationBiasDetector:
    """Mathematical bias and echo loop detector for multi-agent coordination."""

    def __init__(self, max_history: int = 20) -> None:
        self.history: List[Dict[str, Any]] = []
        self.max_history = max_history
        self._consumed_event_ids: set[int] = set()

    def add_decision(
        self,
        confidence: float,
        reasoning_text: str,
        agent_id: Optional[str] = None,
    ) -> None:
        """Record an agent decision with confidence, reasoning text, and agent identity."""
        self.history.append(
            {
                "confidence": float(confidence),
                "text": str(reasoning_text)[:500],
                "agent_id": agent_id,
            }
        )
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def detect_bias(self) -> BiasScore:
        """Evaluate the rolling window for agreement collapse and echo loops.

        Requires minimum 3 distinct logical agents before issuing an agreement_collapse
        advisory. Single-agent repetitions are flagged as echo loops, never groupthink.
        """
        n = len(self.history)
        if n < 4:
            return BiasScore(
                total_bias_score=0.0,
                bias_types={},
                agreement_collapse=False,
                echo_loop_detected=False,
                distinct_agent_count=len({d["agent_id"] for d in self.history if d.get("agent_id")}),
                evidence_window_size=n,
                coordination_risk="insufficient_evidence",
            )

        confidences = [d["confidence"] for d in self.history]
        texts = [d["text"] for d in self.history]
        distinct_agents = {d["agent_id"] for d in self.history if d.get("agent_id")}
        agent_count = len(distinct_agents)

        mean_conf = sum(confidences) / n
        variance = sum((c - mean_conf) ** 2 for c in confidences) / n
        stddev = variance ** 0.5

        collapse_score = max(0.0, 1.0 - (stddev * 2))
        # Agreement collapse requires high consensus across at least 3 distinct agents
        agreement_collapse = (collapse_score > 0.85) and (agent_count >= 3) and (mean_conf > 0.85)

        echo_loop = any(
            SequenceMatcher(None, texts[i], texts[i - 1]).ratio() > 0.92
            for i in range(1, len(texts))
        )

        avg_conf = sum(confidences) / n
        bias_types = {
            "confirmation_bias": max(0.0, (avg_conf - 0.5) * 2),
            "groupthink": max(0.0, collapse_score) if agent_count >= 3 else 0.0,
            "hallucination_risk": max(0.0, 1.0 - avg_conf),
        }

        total_bias = min(1.0, sum(bias_types.values()) / 2)

        if agreement_collapse or (echo_loop and total_bias > 0.7):
            coordination_risk = "high"
        elif total_bias > 0.4:
            coordination_risk = "medium"
        else:
            coordination_risk = "low"

        return BiasScore(
            total_bias_score=round(total_bias, 3),
            bias_types={k: round(v, 3) for k, v in bias_types.items()},
            agreement_collapse=agreement_collapse,
            echo_loop_detected=echo_loop,
            distinct_agent_count=agent_count,
            evidence_window_size=n,
            coordination_risk=coordination_risk,
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


async def fetch_bias_detector_events(
    bus: GossipBus, max_rows: int = 20, agent_id: Optional[str] = None
) -> list[dict]:
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
    )
    parameters: list[Any] = [*_HEARTBEAT_KINDS]
    if agent_id is not None:
        query += "AND json_extract(payload_json, '$.agent_id') = ? "
        parameters.append(agent_id)
    query += "ORDER BY id DESC LIMIT ?"
    parameters.append(max_rows)
    async with bus.connect() as db:
        cursor = await db.execute(query, parameters)
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
    events = await fetch_bias_detector_events(
        bus, max_rows=detector.max_history, agent_id=agent_id
    )
    for ev in events:
        event_id = int(ev["row_id"])
        if event_id in detector._consumed_event_ids:
            continue
        payload = ev["payload"]
        kind = str(payload.get("kind", ""))
        # task_queue.py emits task_complete/task_failed/task_abandoned with
        # "notes", not "message" -- omitting notes silently drops the primary
        # production heartbeat shapes this feed path exists to observe.
        message = str(
            payload.get("message")
            or payload.get("reason")
            or payload.get("notes")
            or payload.get("task")
            or payload.get("task_id")
            or ""
        )
        if not message and kind not in ("task_failed", "task_abandoned", "agent_killed"):
            continue
        ev_agent_id = str(
            payload.get("agent_id")
            or payload.get("assigned_agent")
            or payload.get("source")
            or ""
        )
        confidence = _estimate_confidence(kind, message)
        detector.add_decision(confidence, message, agent_id=ev_agent_id or None)
        detector._consumed_event_ids.add(event_id)
    return detector.detect_bias()
