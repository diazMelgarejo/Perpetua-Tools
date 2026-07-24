"""Out-of-order claim buffering (Phase 1.3.2) over the GossipBus event log.

Extracted from orchestrator/coordination/cli.py as part of the Part 2
consolidation module split (docs/next/2026-07-17-coordination-module-
consolidation-plan.md's canonical orchestrator/coordination/{paths,claims,
reorder_buffer,task_queue,phases}.py target layout).
"""
from __future__ import annotations

import json
import time
from typing import Optional

from orchestrator.gossip_bus import GossipBus
from orchestrator.coordination.paths import current_worktree_label
from orchestrator.coordination.types import ClaimSequence, ReorderBuffer


def _error(message: str) -> bool:
    import sys

    print(f"ERROR: {message}", file=sys.stderr)
    return False


_REORDER_BUFFER_KINDS = ("claim_sequence", "buffer_drained")


async def fetch_reorder_buffer_events(bus: GossipBus) -> list[dict]:
    """Fetch reorder-buffer events via SQL, not a bounded tail().

    Unrelated heartbeat traffic can push claim_sequence / buffer_drained
    events out of a size-bounded tail window, resetting watermarks and
    making buffered sequential claims vanish from buffer status/drain paths.
    """
    kind_placeholders = ",".join("?" for _ in _REORDER_BUFFER_KINDS)
    query = (
        "SELECT id, event_uuid, ts, event_type, payload_json FROM gossip "
        "WHERE event_type = 'heartbeat' "
        f"AND json_extract(payload_json, '$.kind') IN ({kind_placeholders}) "
        "ORDER BY id ASC"
    )
    async with bus.connect() as db:
        cursor = await db.execute(query, list(_REORDER_BUFFER_KINDS))
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


async def get_reorder_buffers(bus: GossipBus) -> dict[str, ReorderBuffer]:
    """Reconstruct all per-agent reorder buffers from GossipBus event log."""
    events = await fetch_reorder_buffer_events(bus)
    buffers: dict[str, ReorderBuffer] = {}

    for ev in events:
        p = ev["payload"]
        kind = p.get("kind")
        agent_id = p.get("agent_id")
        if not agent_id:
            continue
        if agent_id not in buffers:
            buffers[agent_id] = ReorderBuffer(agent_id=agent_id)
        if kind == "claim_sequence":
            claim = ClaimSequence.from_payload(p)
            buffers[agent_id].add_claim(claim)
        elif kind == "buffer_drained":
            new_watermark = p.get("new_watermark")
            if isinstance(new_watermark, int):
                buffers[agent_id].watermark = max(buffers[agent_id].watermark, new_watermark)
                for seq_num in list(buffers[agent_id].buffer):
                    if seq_num < buffers[agent_id].watermark:
                        buffers[agent_id].buffer.pop(seq_num, None)

    return buffers


async def claim_with_seq(
    bus: GossipBus, agent_id: str, seq_num: int, task: str, notes: str
) -> None:
    """Emit a claim with sequence number; reorder buffer processes it."""
    # Get pre-emit buffer state
    buffers_before = await get_reorder_buffers(bus)
    watermark_before = buffers_before.get(agent_id, ReorderBuffer(agent_id)).watermark

    claim = ClaimSequence(
        agent_id=agent_id,
        claim_num=seq_num,
        task=task,
        timestamp=time.time(),
        notes=notes,
        worktree=current_worktree_label(),
    )

    # Emit to bus
    await bus.emit("heartbeat", claim.to_payload())

    # Reconstruct buffer state from ALL events in bus (including the one we just emitted)
    buffers_after = await get_reorder_buffers(bus)
    buffer_after = buffers_after.get(agent_id, ReorderBuffer(agent_id))
    watermark_after = buffer_after.watermark

    # Determine status based on watermark advancement
    if watermark_after > seq_num:
        # Claim was processed (emitted)
        num_emitted = watermark_after - watermark_before
        print(
            f"claimed (seq {seq_num}): {task} by {agent_id} "
            f"(watermark now {watermark_after}, emitted {num_emitted} claim(s))"
        )
    elif seq_num in buffer_after.buffer:
        # Claim is buffered
        status = buffer_after.status()
        print(
            f"buffered (seq {seq_num}): {task} by {agent_id} "
            f"(watermark {watermark_after}, buffered seqs: {status['buffered_seqs']})"
        )
    else:
        # Shouldn't happen, but handle it
        print(
            f"claimed (seq {seq_num}): {task} by {agent_id} "
            f"(watermark now {watermark_after})"
        )


async def buffer_status(bus: GossipBus, agent_filter: Optional[str] = None) -> None:
    """Show reorder buffer status for all or specified agents."""
    buffers = await get_reorder_buffers(bus)
    if not buffers:
        print("no buffer state found")
        return

    print("\n=== Reorder Buffer Status ===")
    for agent_id in sorted(buffers.keys()):
        if agent_filter and agent_id != agent_filter:
            continue
        status = buffers[agent_id].status()
        print(
            f"\n{agent_id}:"
            f"  watermark={status['watermark']}"
            f"  buffered={status['buffered_count']}"
        )
        if status['buffered_seqs']:
            print(f"  buffered_seqs: {status['buffered_seqs']}")


async def buffer_drain(bus: GossipBus, agent_id: str) -> bool | None:
    """Force-drain buffered claims for an agent (emit all held claims)."""
    buffers = await get_reorder_buffers(bus)
    if agent_id not in buffers:
        return _error(f"no buffer state for agent {agent_id}")

    buffer = buffers[agent_id]
    if not buffer.buffer:
        print(f"buffer for {agent_id} is already empty (watermark {buffer.watermark})")
        return

    emitted, new_watermark = buffer.drain()
    print(
        f"drained: {agent_id} ({len(emitted)} claims) "
        f"→ watermark {buffer.watermark} to {new_watermark}"
    )
    for claim in emitted:
        print(f"  - seq {claim.claim_num}: {claim.task}")

    # Emit a drain marker to the bus for audit
    await bus.emit(
        "heartbeat",
        {
            "kind": "buffer_drained",
            "agent_id": agent_id,
            "emitted_count": len(emitted),
            "new_watermark": new_watermark,
        },
    )
