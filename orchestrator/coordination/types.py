"""Shared dataclasses and enums for the coordination package.

Keeping these in one module prevents duplicate definitions across core.py,
legacy.py, and cli.py, and avoids enum-identity bugs when modules are reloaded
mid-test-run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass
class ClaimSequence:
    """Represents an ordered claim event with sequence number."""
    agent_id: str
    claim_num: int
    task: str
    timestamp: float
    notes: str = ""
    worktree: str = ""

    def to_payload(self) -> dict:
        """Convert to JSON-serializable payload for GossipBus."""
        return {
            "kind": "claim_sequence",
            "agent_id": self.agent_id,
            "claim_num": self.claim_num,
            "task": self.task,
            "timestamp": self.timestamp,
            "notes": self.notes,
            "worktree": self.worktree,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "ClaimSequence":
        """Reconstruct ClaimSequence from GossipBus payload."""
        return cls(
            agent_id=payload["agent_id"],
            claim_num=payload["claim_num"],
            task=payload["task"],
            timestamp=payload["timestamp"],
            notes=payload.get("notes", ""),
            worktree=payload.get("worktree", ""),
        )


@dataclass
class ReorderBuffer:
    """Manages per-agent reorder buffering for out-of-order claims."""
    agent_id: str
    buffer: dict[int, ClaimSequence] = field(default_factory=dict)
    watermark: int = 0  # Next expected sequence number

    def add_claim(self, claim: ClaimSequence) -> tuple[list[ClaimSequence], int]:
        """
        Add a claim to the buffer; return (emitted_claims, new_watermark).

        When claim N arrives:
        - If N == watermark: emit N, then check buffer for N+1, N+2, etc.
        - If N > watermark: buffer N (gap exists)
        - If N < watermark: silently drop (already emitted)

        Returns:
          - list of claims ready to emit (in order from watermark)
          - new watermark value
        """
        if claim.claim_num < self.watermark:
            # Already emitted, silently drop
            return ([], self.watermark)

        if claim.claim_num == self.watermark:
            # Claim matches watermark: emit immediately and advance
            emitted = [claim]
            new_watermark = self.watermark + 1

            # Check buffer for consecutive claims
            while new_watermark in self.buffer:
                emitted.append(self.buffer.pop(new_watermark))
                new_watermark += 1

            self.watermark = new_watermark
            return (emitted, new_watermark)
        else:
            # claim.claim_num > watermark: buffer the claim (gap exists).
            # Preserve the first buffered claim; later duplicates/conflicts
            # must not overwrite the causal record that arrived first.
            if claim.claim_num not in self.buffer:
                self.buffer[claim.claim_num] = claim
            return ([], self.watermark)

    def drain(self) -> tuple[list[ClaimSequence], int]:
        """
        Force-drain all buffered claims (advance watermark to max seen + 1).
        Used when buffer timeout expires or explicit drain command issued.
        """
        if not self.buffer:
            return ([], self.watermark)

        max_seen = max(self.buffer.keys())
        emitted = []
        for seq_num in sorted(self.buffer.keys()):
            emitted.append(self.buffer.pop(seq_num))

        self.watermark = max_seen + 1
        return (emitted, self.watermark)

    def status(self) -> dict:
        """Return buffer status as dict."""
        return {
            "agent_id": self.agent_id,
            "watermark": self.watermark,
            "buffered_count": len(self.buffer),
            "buffered_seqs": sorted(self.buffer.keys()),
        }


class TaskPriority(Enum):
    """Task priority levels for work distribution."""
    CRITICAL = 1  # Blocks other phases
    HIGH = 2      # Phase blockers
    NORMAL = 3    # Regular work
    LOW = 4       # Nice-to-have

    @classmethod
    def from_string(cls, s: str) -> "TaskPriority":
        """Convert string priority to enum."""
        normalized = s.strip().upper()
        for priority in cls:
            if priority.name == normalized:
                return priority
        raise ValueError(f"Unknown priority: {s}. Must be one of {[p.name for p in cls]}")

    def __str__(self) -> str:
        return self.name


class QueuedTaskState(Enum):
    """Task state progression."""
    QUEUED = "queued"           # Waiting for an agent to claim
    CLAIMED = "claimed"         # Agent has announced intent
    COMPLETED = "completed"     # Task finished successfully
    FAILED = "failed"           # Task failed; retry logic applies


class PhaseStatus(Enum):
    """Phase workflow status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"


class ClaimResult(Enum):
    """Atomic claim outcomes that need distinct caller-facing messages."""
    WON = "won"
    LOST_RACE = "lost_race"
    CONTENTION = "contention"


class ReleaseResult(Enum):
    """Atomic release outcomes that need distinct caller-facing messages."""
    RELEASED = "released"
    LOST_RACE = "lost_race"
    CONTENTION = "contention"


@dataclass
class PhaseState:
    """Represents a workflow phase and its current state."""
    phase_name: str
    status: PhaseStatus
    assigned_to: list[str] = field(default_factory=list)
    total_tests: int = 0
    tests_passing: int = 0
    blockers: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    started_at: float | None = None
    completed_at: float | None = None
    notes: str = ""
    estimated_duration_hours: float = 0.0

    def to_payload(self) -> dict:
        """Convert to JSON-serializable payload for GossipBus."""
        return {
            "kind": "phase_event",
            "phase_name": self.phase_name,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "total_tests": self.total_tests,
            "tests_passing": self.tests_passing,
            "blockers": self.blockers,
            "depends_on": self.depends_on,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "notes": self.notes,
            "estimated_duration_hours": self.estimated_duration_hours,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "PhaseState":
        """Reconstruct PhaseState from GossipBus payload."""
        return cls(
            phase_name=payload["phase_name"],
            status=PhaseStatus(payload["status"]),
            assigned_to=payload.get("assigned_to", []),
            total_tests=payload.get("total_tests", 0),
            tests_passing=payload.get("tests_passing", 0),
            blockers=payload.get("blockers", []),
            depends_on=payload.get("depends_on", []),
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            notes=payload.get("notes", ""),
            estimated_duration_hours=payload.get("estimated_duration_hours", 0.0),
        )
