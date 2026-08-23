"""Coordination bias and echo loop detector for multi-agent workflows.

Ported from AlphaClaw observability draft to detect Agreement Collapse (>0.85),
Echo Loops (>0.92 SequenceMatcher), and Groupthink across parallel agent decisions.
Reference: orama-system docs/v2/54-tri-stack-observability-and-l3-egress-v2.md § 4.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional


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
