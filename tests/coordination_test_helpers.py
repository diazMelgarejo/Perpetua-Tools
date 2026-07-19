"""Shared test helpers for the coordination + gossip test suite.

Not a conftest.py -- deliberately a plain, unambiguously-named module so it
can be imported the normal way (`from tests.coordination_test_helpers import
X` or `from coordination_test_helpers import X` with tests/ on sys.path),
never via a bare `from conftest import X`. The tests/ tree has more than one
conftest.py (tests/conftest.py and tests/scripts/conftest.py, the latter for
shell-script tests that intentionally override the parent's autouse
fixtures) -- pytest itself only ever loads conftest.py files for fixture
discovery, it does not guarantee which one a bare `import conftest`
resolves to when multiple exist on sys.path. That ambiguity is exactly what
broke CI: it happened to resolve tests/scripts/conftest.py instead of
tests/conftest.py, and the former has no emit_noise_batch, so five
coordination test modules failed to collect at all.
"""
from __future__ import annotations


async def emit_noise_batch(bus, count, *, kind="agent_pulse", modulo=10):
    """Insert `count` synthetic heartbeat events in ONE transaction.

    Several tests verify that a real function (phase/task/reorder-buffer
    folding) still finds the right event once unrelated heartbeat volume
    exceeds an old size-bounded tail() window -- historically written as
    `for i in range(1500): await bus.emit(...)`, which is 1500 individual
    SQLite transactions (each with its own fsync-backed commit) and takes
    30-50s per test. The noise events' individual content doesn't matter
    here, only that they exist in bulk -- so this reuses the same
    GossipBus.insert_event() the real emit() calls (identical schema,
    redaction, payload handling), just inside one connection/commit instead
    of `count` of them. Does not schedule embeddings for the noise rows
    (irrelevant to what these tests assert, and would itself spawn `count`
    background tasks).
    """
    async with bus.connect() as db:
        for i in range(count):
            await bus.insert_event(
                db, "heartbeat", {"kind": kind, "agent_id": f"noise-{i % modulo}", "seq": i}
            )
        await db.commit()
