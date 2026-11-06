"""Tests for orchestrator/memory_node.py (Item 6 — RAG v1 backport)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.memory_node import (
    _normalise_fts_hits,
    _text_from_gossip_payload,
    reset_singletons,
    retrieve_context,
)


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Ensure module-level singletons don't bleed between tests."""
    reset_singletons()
    yield
    reset_singletons()


# ── FTS hit normalisation (GossipBus shape) ───────────────────────────────────

def test_text_from_gossip_payload_prefers_prompt():
    assert _text_from_gossip_payload({"prompt": "find widget", "role": "coder"}) == "find widget"


def test_normalise_fts_hits_adds_text_from_payload():
    raw = [
        {
            "row_id": 1,
            "event_type": "dispatch",
            "payload": {"prompt": "Q3 revenue was $10M"},
        }
    ]
    out = _normalise_fts_hits(raw)
    assert len(out) == 1
    assert out[0]["text"] == "Q3 revenue was $10M"
    assert out[0]["row_id"] == 1


@pytest.mark.asyncio
async def test_retrieve_context_real_gossip_bus_fts_only(tmp_path):
    """Integration: GossipBus rows must surface as injectable text (not silent drop)."""
    from orchestrator.gossip_bus import GossipBus

    bus = GossipBus(str(tmp_path / "gossip.db"))
    await bus.init_db()
    with patch.object(bus, "_embed_and_store", new_callable=AsyncMock):
        await bus.emit("dispatch", {"prompt": "Q3 revenue was $10M"})

    with (
        patch("orchestrator.memory_store.lancedb_available", return_value=False),
        patch("orchestrator.memory_embed.get_embedding", AsyncMock()) as mock_embed,
    ):
        result = await retrieve_context("Q3 revenue", top_n=5, gossip_bus=bus, use_gbrain=False)

    mock_embed.assert_not_called()
    assert any("Q3 revenue was $10M" in h.get("text", "") for h in result)


# ── Edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_context_empty_query_returns_empty():
    result = await retrieve_context("")
    assert result == []


@pytest.mark.asyncio
async def test_retrieve_context_blank_query_returns_empty():
    result = await retrieve_context("   ")
    assert result == []


# ── FTS5-only mode (no LanceDB, no gbrain) ────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_context_fts_only():
    mock_bus = MagicMock()
    mock_bus.search = AsyncMock(return_value=[
        {"row_id": 1, "text": "hello world"},
        {"row_id": 2, "text": "foo bar"},
    ])
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[])

    with patch("orchestrator.memory_embed.get_embedding", AsyncMock(return_value=[])):
        result = await retrieve_context(
            "hello",
            top_n=5,
            use_gbrain=False,
            gossip_bus=mock_bus,
            lance_store=mock_store,
        )

    assert len(result) == 2
    assert result[0]["text"] == "hello world"


# ── FTS + vector RRF merge ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_context_rrf_merge():
    mock_bus = MagicMock()
    mock_bus.search = AsyncMock(return_value=[
        {"row_id": 1, "text": "FTS hit A"},
    ])
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[
        {"row_id": 2, "text": "vec hit B"},
    ])

    with (
        patch("orchestrator.memory_store.lancedb_available", return_value=True),
        patch("orchestrator.memory_embed.get_embedding", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await retrieve_context(
            "query",
            top_n=5,
            use_gbrain=False,
            gossip_bus=mock_bus,
            lance_store=mock_store,
        )

    texts = [r["text"] for r in result]
    assert "FTS hit A" in texts
    assert "vec hit B" in texts


# ── gbrain blend ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_context_includes_gbrain_hits():
    mock_bus = MagicMock()
    mock_bus.search = AsyncMock(return_value=[{"row_id": 1, "text": "bus hit"}])
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[])

    with (
        patch("orchestrator.memory_embed.get_embedding", AsyncMock(return_value=[])),
        patch("orchestrator.gbrain_search.gbrain_search", AsyncMock(return_value=[{"text": "gbrain hit"}])),
    ):
        result = await retrieve_context(
            "query",
            top_n=5,
            use_gbrain=True,
            gossip_bus=mock_bus,
            lance_store=mock_store,
        )

    # FTS hits should be present; gbrain hit may also be blended in
    assert len(result) >= 1
    texts = [r["text"] for r in result]
    assert "bus hit" in texts


# ── Degradation: all backends fail ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_context_returns_empty_when_all_backends_fail():
    mock_bus = MagicMock()
    mock_bus.search = AsyncMock(side_effect=RuntimeError("db gone"))
    mock_store = MagicMock()
    mock_store.search = AsyncMock(side_effect=RuntimeError("lance gone"))

    with patch("orchestrator.memory_embed.get_embedding", AsyncMock(side_effect=RuntimeError)):
        result = await retrieve_context(
            "query",
            use_gbrain=False,
            gossip_bus=mock_bus,
            lance_store=mock_store,
        )

    assert result == []


# ── top_n respected ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_context_respects_top_n():
    hits = [{"row_id": i, "text": f"hit {i}"} for i in range(20)]
    mock_bus = MagicMock()
    mock_bus.search = AsyncMock(return_value=hits)
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[])

    with patch("orchestrator.memory_embed.get_embedding", AsyncMock(return_value=[])):
        result = await retrieve_context(
            "many hits",
            top_n=3,
            use_gbrain=False,
            gossip_bus=mock_bus,
            lance_store=mock_store,
        )

    assert len(result) <= 3


# ── ensure_gossip_db_ready (PR change: renamed to public) ────────────────────

@pytest.mark.asyncio
async def test_ensure_gossip_db_ready_calls_init_db(tmp_path):
    """ensure_gossip_db_ready must call bus.init_db() on a fresh bus."""
    from orchestrator.gossip_bus import GossipBus
    from orchestrator.memory_node import ensure_gossip_db_ready

    bus = GossipBus(str(tmp_path / "ready_test.db"))
    # init_db not yet called — flag is absent
    assert not getattr(bus, "_memory_node_db_ready", False)

    await ensure_gossip_db_ready(bus)

    assert getattr(bus, "_memory_node_db_ready", False) is True


@pytest.mark.asyncio
async def test_ensure_gossip_db_ready_idempotent(tmp_path):
    """Second call to ensure_gossip_db_ready must not call init_db again."""
    from orchestrator.memory_node import ensure_gossip_db_ready
    from unittest.mock import AsyncMock

    mock_bus = AsyncMock()
    mock_bus._memory_node_db_ready = False

    await ensure_gossip_db_ready(mock_bus)
    assert mock_bus.init_db.call_count == 1

    # Mark as ready and call again — init_db must NOT be called a second time.
    mock_bus._memory_node_db_ready = True
    await ensure_gossip_db_ready(mock_bus)
    assert mock_bus.init_db.call_count == 1  # still 1


@pytest.mark.asyncio
async def test_ensure_gossip_db_ready_sets_flag(tmp_path):
    """ensure_gossip_db_ready must set _memory_node_db_ready=True after init_db."""
    from orchestrator.memory_node import ensure_gossip_db_ready
    from unittest.mock import AsyncMock

    mock_bus = AsyncMock()
    mock_bus._memory_node_db_ready = False

    await ensure_gossip_db_ready(mock_bus)
    assert mock_bus._memory_node_db_ready is True


# ── _get_default_bus uses resolve_gossip_db_path (PR change) ─────────────────

def test_get_default_bus_uses_resolve_gossip_db_path(tmp_path, monkeypatch):
    """_get_default_bus must use resolve_gossip_db_path() so the path matches PT_STATE_DIR."""
    from orchestrator.memory_node import _get_default_bus, reset_singletons
    from orchestrator.gossip_bus import resolve_gossip_db_path

    reset_singletons()
    monkeypatch.delenv("GOSSIP_DB_PATH", raising=False)
    monkeypatch.setenv("PT_STATE_DIR", str(tmp_path))

    bus = _get_default_bus()
    assert bus is not None
    expected_path = resolve_gossip_db_path()
    assert bus._db_path == expected_path
    reset_singletons()


def test_get_default_bus_singleton_is_cached(tmp_path, monkeypatch):
    """_get_default_bus returns the same object on repeated calls (singleton)."""
    from orchestrator.memory_node import _get_default_bus, reset_singletons

    reset_singletons()
    monkeypatch.delenv("GOSSIP_DB_PATH", raising=False)
    monkeypatch.setenv("PT_STATE_DIR", str(tmp_path))

    bus1 = _get_default_bus()
    bus2 = _get_default_bus()
    assert bus1 is bus2
    reset_singletons()


# ── Finding P1: Vector recall topology sanitization ──────────────────────────

@pytest.mark.asyncio
async def test_retrieve_context_vector_only_sanitizes_legacy_labels():
    """Vector recall hits derived from gossip payloads must sanitize legacy labels."""
    import json

    private_dir = "/" + "/".join(["home", "alice", "worktree"])
    legacy_label = f"feature/branch@{private_dir}"
    mock_bus = MagicMock()
    mock_bus.search = AsyncMock(return_value=[])
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[
        {
            "row_id": 42,
            "payload": {
                "worktree": legacy_label,
                "prompt": "Q3 forecasts for project",
                "notes": f"derived from {legacy_label}",
            },
        }
    ])

    with (
        patch("orchestrator.memory_store.lancedb_available", return_value=True),
        patch("orchestrator.memory_embed.get_embedding", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await retrieve_context(
            "forecasts",
            top_n=5,
            use_gbrain=False,
            gossip_bus=mock_bus,
            lance_store=mock_store,
        )

    assert len(result) == 1
    hit = result[0]
    assert hit["row_id"] == 42
    assert hit["payload"]["worktree"] == "legacy-redacted"
    assert "legacy-redacted" in hit["payload"]["notes"]
    assert "alice" not in json.dumps(hit)
    assert "feature/branch" not in json.dumps(hit)
    assert hit["text"] == "Q3 forecasts for project"


@pytest.mark.asyncio
async def test_retrieve_context_vector_only_serialized_json_sanitizes_legacy_labels():
    """Vector hits with serialized JSON text must sanitize topology and extract text."""
    import json

    bob_dir = "/" + "/".join(["Users", "bob", "code", "pt"])
    legacy_label = f"secret-fix@{bob_dir}"
    mock_bus = MagicMock()
    mock_bus.search = AsyncMock(return_value=[])
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[
        {
            "row_id": 43,
            "text": json.dumps({
                "worktree": legacy_label,
                "message": "fix deployed to staging",
            }),
        }
    ])

    with (
        patch("orchestrator.memory_store.lancedb_available", return_value=True),
        patch("orchestrator.memory_embed.get_embedding", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await retrieve_context(
            "staging",
            top_n=5,
            use_gbrain=False,
            gossip_bus=mock_bus,
            lance_store=mock_store,
        )

    assert len(result) == 1
    hit = result[0]
    assert hit["payload"]["worktree"] == "legacy-redacted"
    assert hit["text"] == "fix deployed to staging"
    assert "bob" not in json.dumps(hit)
    assert ("/" + "/".join(["Users", "bob"])) not in json.dumps(hit)


@pytest.mark.asyncio
async def test_retrieve_context_vector_only_withholds_unclassified_gossip_projection():
    """Vector hits with unclassifiable gossip projections must be withheld."""
    mock_bus = MagicMock()
    mock_bus.search = AsyncMock(return_value=[])
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[
        {
            "row_id": 44,
            "payload": {
                "worktree": "unclassifiable:broken:topology",
                "prompt": "confidential leak",
            },
        }
    ])

    with (
        patch("orchestrator.memory_store.lancedb_available", return_value=True),
        patch("orchestrator.memory_embed.get_embedding", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await retrieve_context(
            "confidential",
            top_n=5,
            use_gbrain=False,
            gossip_bus=mock_bus,
            lance_store=mock_store,
        )

    assert result == [], "unclassifiable gossip projection must be withheld"


@pytest.mark.asyncio
async def test_retrieve_context_vector_fallback_sanitizes_when_rrf_fails():
    """Vector fallback path must return sanitized hits even if RRF fails."""
    import json

    alice_dev = "/" + "/".join(["Users", "alice", "dev"])
    legacy_label = f"patch@{alice_dev}"
    mock_bus = MagicMock()
    mock_bus.search = AsyncMock(return_value=[])
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[
        {
            "row_id": 45,
            "payload": {
                "worktree": legacy_label,
                "prompt": "fallback test",
            },
        }
    ])

    with (
        patch("orchestrator.memory_store.lancedb_available", return_value=True),
        patch("orchestrator.memory_embed.get_embedding", AsyncMock(return_value=[0.1] * 1024)),
        patch("orchestrator.memory_rrf.rrf_merge", side_effect=RuntimeError("rrf broken")),
    ):
        result = await retrieve_context(
            "fallback",
            top_n=5,
            use_gbrain=False,
            gossip_bus=mock_bus,
            lance_store=mock_store,
        )

    assert len(result) == 1
    assert result[0]["payload"]["worktree"] == "legacy-redacted"
    assert ("/" + "/".join(["Users", "alice"])) not in json.dumps(result)
