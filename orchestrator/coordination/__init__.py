"""Canonical v1 coordination-board implementation.

The public CLI remains available through scripts/agent_coordination.py, but the
implementation is owned here so v2 can migrate one source of truth instead of
multiple drifting script copies.
"""
from __future__ import annotations

from orchestrator.coordination.bias_detector import (
    BiasScore,
    CoordinationBiasDetector,
)
from orchestrator.coordination.claims import (
    claim_task,
    list_agents,
    list_claims,
    log_message,
    register_agent,
    release_task,
)
from orchestrator.coordination.cli import main
from orchestrator.coordination.paths import (
    canonical_db_path,
    current_worktree_label,
)
from orchestrator.coordination.types import (
    ClaimResult,
    ClaimSequence,
    PhaseState,
    PhaseStatus,
    QueuedTaskState,
    ReleaseResult,
    ReorderBuffer,
    TaskPriority,
)

__all__ = [
    "canonical_db_path",
    "claim_task",
    "current_worktree_label",
    "list_agents",
    "list_claims",
    "log_message",
    "main",
    "register_agent",
    "release_task",
    # Coordination bias detection
    "BiasScore",
    "CoordinationBiasDetector",
    # Shared types
    "ClaimResult",
    "ClaimSequence",
    "PhaseState",
    "PhaseStatus",
    "QueuedTaskState",
    "ReleaseResult",
    "ReorderBuffer",
    "TaskPriority",
]
