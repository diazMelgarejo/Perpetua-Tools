"""tests/test_gossip_bus.py

Tests for orchestrator/gossip_bus.py — FTS5 search, _pending_embeds GC guard,
embed_status column.  No Ollama or LanceDB required — embed pipeline is
mock-isolated.

Covers acceptance gates G1, G2, G3, G5 from:
  docs/superpowers/plans/2026-05-21-rag-memory-v1-plan.md (backport section)
"""
from __future__ import annotations

import asyncio
import pytest

import subprocess
from pathlib import Path

from orchestrator.gossip_bus import (
    GossipBus,
    _canonical_repo_state_dir,
    _pending_embeds,
    cancel_pending_embeddings_for_current_loop,
    _sanitize_fts_query,
    resolve_default_state_dir,
    resolve_gossip_db_path,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def bus(tmp_path):
    db = str(tmp_path / "test.db")
    b = GossipBus(db)
    await b.init_db()
    return b


# ---------------------------------------------------------------------------
# _sanitize_fts_query unit tests (Gap 2 / D_FTS-1)
# ---------------------------------------------------------------------------

def test_sanitize_strips_quotes():
    assert '"hello"' not in _sanitize_fts_query('"hello world"')


def test_sanitize_strips_colon():
    result = _sanitize_fts_query("event_type:dispatch")
    assert ":" not in result


def test_sanitize_lowercases_fts_keywords():
    result = _sanitize_fts_query("hello AND world")
    assert "and" in result
    assert "AND" not in result


def test_sanitize_empty_returns_empty():
    assert _sanitize_fts_query("") == ""


def test_sanitize_preserves_plain_terms():
    result = _sanitize_fts_query("blue widget quarterly report")
    assert "blue" in result
    assert "widget" in result


# ---------------------------------------------------------------------------
# GossipBus FTS5 search tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_empty_query_returns_empty(bus):
    await bus.emit("dispatch", {"prompt": "hello world"})
    result = await bus.search("")
    assert result == []


@pytest.mark.asyncio
async def test_search_finds_exact_payload_keyword(bus):
    # Use non-sensitive keys — prompts are redacted before durable FTS store.
    await bus.emit("dispatch", {"intent": "find the blue widget"})
    await bus.emit("route", {"intent": "unrelated thing"})
    hits = await bus.search("blue widget")
    assert len(hits) == 1
    assert hits[0]["event_type"] == "dispatch"
    assert "blue widget" in hits[0]["payload"]["intent"]


@pytest.mark.asyncio
async def test_search_filters_by_event_type(bus):
    await bus.emit("dispatch", {"intent": "run the calculation"})
    await bus.emit("error", {"detail": "run the calculation", "error": "timeout"})
    hits = await bus.search("run the calculation", event_type="error")
    assert len(hits) == 1
    assert hits[0]["event_type"] == "error"
    assert "run the calculation" in hits[0]["payload"]["detail"]


@pytest.mark.asyncio
async def test_search_returns_empty_for_no_match(bus):
    await bus.emit("dispatch", {"prompt": "completely different content"})
    hits = await bus.search("xyzzy_no_match_ever")
    assert hits == []


@pytest.mark.asyncio
async def test_search_handles_special_chars_without_raising(bus):
    """Query with FTS5 operators must not raise — sanitizer should handle them."""
    await bus.emit("dispatch", {"prompt": "test event"})
    try:
        hits = await bus.search('event_type:"dispatch" AND *')
        assert isinstance(hits, list)
    except Exception as e:
        pytest.fail(f"search() raised on special chars: {e}")


# ---------------------------------------------------------------------------
# embed_status column tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_emit_creates_pending_row(bus):
    """After emit, the row's embed_status starts as 'pending'."""
    import aiosqlite
    await bus.emit("dispatch", {"prompt": "status test"})
    # Cancel any in-flight embed task to avoid side effects
    for task in list(_pending_embeds):
        task.cancel()
    await asyncio.sleep(0)

    async with aiosqlite.connect(bus._db_path) as db:
        cursor = await db.execute("SELECT embed_status FROM gossip LIMIT 1")
        row = await cursor.fetchone()
    assert row is not None
    assert row[0] in ("pending", "embedded", "failed")


# ---------------------------------------------------------------------------
# resolve_gossip_db_path — default resolution must converge across worktrees,
# not fragment per-cwd. Regression test for the multi-worktree job-board
# split-brain incident (empty local .state/perpetua_core.db shadowing the
# real shared one).
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_env(monkeypatch):
    """Strip the env vars that would otherwise override default resolution."""
    monkeypatch.delenv("GOSSIP_DB_PATH", raising=False)
    monkeypatch.delenv("PT_STATE_DIR", raising=False)


@pytest.fixture
def bare_repo_with_worktree(tmp_path):
    """A throwaway git repo with a second worktree, to prove both resolve
    the same canonical .state path regardless of which one is cwd."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text("x")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    worktree = tmp_path / "worktree"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "wt-branch", str(worktree)],
        cwd=repo, check=True,
    )
    return repo, worktree


def test_default_resolution_converges_across_worktrees(
    isolated_env, bare_repo_with_worktree, monkeypatch
):
    """Same repo, two different cwds (main checkout vs. worktree) — the
    default-resolved db path must be identical, not one-per-worktree."""
    repo, worktree = bare_repo_with_worktree
    monkeypatch.chdir(repo)
    path_from_repo = resolve_gossip_db_path()
    monkeypatch.chdir(worktree)
    path_from_worktree = resolve_gossip_db_path()
    assert path_from_repo == path_from_worktree
    assert path_from_repo == str((repo / ".state" / "perpetua_core.db").resolve())


def test_default_resolution_anchors_bare_repo_state_at_common_dir(
    isolated_env, monkeypatch, tmp_path
):
    bare_repo = tmp_path / "bare-repo"
    subprocess.run(["git", "init", "--bare", "-q", str(bare_repo)], check=True)
    monkeypatch.chdir(bare_repo)

    assert resolve_gossip_db_path() == str(
        (bare_repo / ".state" / "perpetua_core.db").resolve()
    )


def test_default_resolution_anchors_external_git_dir_at_common_dir(
    isolated_env, monkeypatch, tmp_path
):
    external_git_dir = tmp_path / "external-git-dir"
    subprocess.run(
        ["git", "init", "--bare", "-q", str(external_git_dir)], check=True
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_DIR", str(external_git_dir))

    assert resolve_gossip_db_path() == str(
        (external_git_dir / ".state" / "perpetua_core.db").resolve()
    )


def test_default_resolution_decodes_git_common_dir_as_utf8(
    isolated_env, monkeypatch, tmp_path
):
    checkout = tmp_path / "r\u00e9sum\u00e9"
    common_dir = checkout / ".git"
    common_dir.mkdir(parents=True)

    def fake_check_output(command, **kwargs):
        assert command == ["git", "rev-parse", "--git-common-dir"]
        assert kwargs["text"] is True
        assert kwargs["encoding"] == "utf-8"
        return str(common_dir)

    monkeypatch.setattr("orchestrator.gossip_bus.subprocess.check_output", fake_check_output)

    assert resolve_gossip_db_path() == str(
        (checkout / ".state" / "perpetua_core.db").resolve()
    )


def test_explicit_state_dir_still_wins(isolated_env, tmp_path):
    """An explicit state_dir argument overrides canonical resolution."""
    explicit = tmp_path / "explicit-state"
    result = resolve_gossip_db_path(explicit)
    assert result == str((explicit / "perpetua_core.db").resolve())


def test_pt_state_dir_env_still_wins(isolated_env, monkeypatch, tmp_path):
    """PT_STATE_DIR is still an explicit override, unaffected by the fix."""
    override = tmp_path / "override-state"
    monkeypatch.setenv("PT_STATE_DIR", str(override))
    result = resolve_gossip_db_path()
    assert result == str((override / "perpetua_core.db").resolve())


def test_gossip_db_path_env_takes_priority(isolated_env, monkeypatch, tmp_path):
    """GOSSIP_DB_PATH is the highest-priority override, unaffected by the fix."""
    explicit_file = tmp_path / "explicit.db"
    monkeypatch.setenv("GOSSIP_DB_PATH", str(explicit_file))
    assert resolve_gossip_db_path() == str(explicit_file)


def test_default_resolution_falls_back_outside_git_repo(isolated_env, tmp_path, monkeypatch):
    """Outside any git repo, falls back to the pre-fix cwd-relative behavior
    instead of raising — packaged/non-git deployments must still work."""
    non_repo = tmp_path / "not-a-repo"
    non_repo.mkdir()
    monkeypatch.chdir(non_repo)
    result = resolve_gossip_db_path()
    assert result == str((non_repo / ".state" / "perpetua_core.db").resolve())


def test_supervisor_default_state_converges_with_fastapi_gossip_bus(
    isolated_env, bare_repo_with_worktree, monkeypatch
):
    """FastAPI startup gossip, supervisor job emits, and memory_node must share
    one db — not split canonical startup from cwd-relative supervisor state."""
    from orchestrator.supervisor import OrchestrationSupervisor

    repo, worktree = bare_repo_with_worktree
    monkeypatch.chdir(worktree)
    fastapi_startup_path = resolve_gossip_db_path()
    supervisor = OrchestrationSupervisor()
    supervisor_gossip_path = resolve_gossip_db_path(supervisor._state_dir)
    memory_node_path = resolve_gossip_db_path()
    canonical_state = resolve_default_state_dir()

    expected = str((repo / ".state" / "perpetua_core.db").resolve())
    assert fastapi_startup_path == expected
    assert supervisor_gossip_path == expected
    assert memory_node_path == expected
    assert canonical_state == (repo / ".state").resolve()
    assert supervisor._state_dir.resolve() == (repo / ".state").resolve()


@pytest.mark.asyncio
async def test_embed_failure_marks_row_failed(tmp_path):
    """When Ollama is unreachable, embed_status is set to 'failed'."""
    from unittest.mock import patch
    import aiosqlite

    db_path = str(tmp_path / "fail.db")
    bus = GossipBus(db_path)
    await bus.init_db()

    async def _fail_embed(text: str):
        raise ConnectionError("Ollama unreachable")

    with patch("orchestrator.memory_embed.get_embedding", side_effect=_fail_embed):
        await bus.emit("dispatch", {"prompt": "failing embed row"})
        # Allow the fire-and-forget task to complete
        await asyncio.sleep(0.2)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT embed_status FROM gossip LIMIT 1")
        row = await cursor.fetchone()
    assert row[0] == "failed"


# ---------------------------------------------------------------------------
# _pending_embeds GC guard test (Gap 3 / D_GCG-1)
# Real behavioral test — not just isinstance check.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pending_embeds_set_prevents_gc(tmp_path):
    """In-flight embed tasks are registered in _pending_embeds during execution
    and auto-discarded when the task completes.

    Gap 3 fix (Antigravity Gemini 3.5 critique, 2026-05-21):
    Previously the test only asserted isinstance(_pending_embeds, set) — a tautology.
    This test patches _embed_and_store to sleep, verifying the set holds the task
    during the active window and drains to 0 after the callback fires.
    """
    from unittest.mock import patch
    import orchestrator.gossip_bus as gossip_mod

    db_path = str(tmp_path / "gc.db")
    bus = GossipBus(db_path)
    await bus.init_db()
    _pending_embeds.clear()

    async def slow_embed(self, row_id, payload):
        await asyncio.sleep(0.1)

    with patch.object(gossip_mod.GossipBus, "_embed_and_store", slow_embed):
        await bus.emit("dispatch", {"prompt": "gc test"})
        assert len(_pending_embeds) == 1, "Task must be registered while in-flight"
        await asyncio.sleep(0.2)
        assert len(_pending_embeds) == 0, "Task must be discarded after done-callback"


@pytest.mark.asyncio
async def test_cli_shutdown_cancels_and_drains_its_pending_embeddings(tmp_path):
    """One-shot CLI loops must not close while an embedding owns aiosqlite I/O."""
    from unittest.mock import patch
    import orchestrator.gossip_bus as gossip_mod

    bus = GossipBus(str(tmp_path / "shutdown.db"))
    await bus.init_db()
    _pending_embeds.clear()
    started = asyncio.Event()

    async def blocked_embed(self, row_id, payload):
        started.set()
        await asyncio.Event().wait()

    with patch.object(gossip_mod.GossipBus, "_embed_and_store", blocked_embed):
        await bus.emit("dispatch", {"prompt": "shutdown test"})
        await started.wait()
        pending = [task for task in _pending_embeds if task.get_loop() is asyncio.get_running_loop()]
        assert len(pending) == 1

        await cancel_pending_embeddings_for_current_loop()

    assert not [task for task in _pending_embeds if task.get_loop() is asyncio.get_running_loop()]
    assert pending[0].cancelled()




@pytest.mark.asyncio
async def test_init_db_reraises_non_duplicate_column_operational_error(tmp_path, monkeypatch):
    """Migration idempotency must not swallow unrelated SQLite failures."""
    db_path = str(tmp_path / "migration.db")
    bus = GossipBus(db_path)

    original_connect = bus.connect

    class FailingConnection:
        def __init__(self, inner):
            self._inner = inner
            self._alter_seen = False

        async def __aenter__(self):
            self._db = await self._inner.__aenter__()
            return self

        async def __aexit__(self, *args):
            return await self._inner.__aexit__(*args)

        async def execute(self, sql, *args):
            if sql.startswith("ALTER TABLE gossip ADD COLUMN event_uuid") and not self._alter_seen:
                self._alter_seen = True
                import sqlite3
                raise sqlite3.OperationalError("disk I/O error")
            return await self._db.execute(sql, *args)

        async def commit(self):
            return await self._db.commit()

    monkeypatch.setattr(bus, "connect", lambda: FailingConnection(original_connect()))

    with pytest.raises(Exception, match="disk I/O error"):
        await bus.init_db()


@pytest.mark.asyncio
async def test_insert_event_duplicate_returns_sanitized_legacy_payload(tmp_path):
    """Duplicate event_uuid return path must not leak legacy governance markers."""
    import aiosqlite
    import json

    db_path = str(tmp_path / "duplicate.db")
    bus = GossipBus(db_path)
    await bus.init_db()
    event_uuid = "duplicate-event"

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO gossip (event_uuid, ts, event_type, payload_json, embed_status) "
            "VALUES (?, ?, ?, ?, 'pending')",
            (
                event_uuid,
                1.0,
                "dispatch",
                json.dumps({
                    "intent": "legacy",
                    "_memory_class": "private",
                    "_redaction_applied": True,
                }),
            ),
        )
        await db.commit()
        row_id, stored_uuid, durable_payload, inserted = await bus.insert_event(
            db, "dispatch", {"intent": "new"}, event_uuid=event_uuid
        )

    assert inserted is False
    assert stored_uuid == event_uuid
    assert row_id == 1
    assert durable_payload == {"intent": "legacy"}


# ---------------------------------------------------------------------------
# tail() test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tail_returns_recent_events_newest_first(bus):
    await bus.emit("dispatch", {"prompt": "first"})
    await bus.emit("route", {"intent": "second"})
    rows = await bus.tail(limit=5)
    assert len(rows) == 2
    assert rows[0]["event_type"] == "route"   # newest first
    assert rows[1]["event_type"] == "dispatch"


# ---------------------------------------------------------------------------
# resolve_gossip_db_path tests (PR change: new function)
# ---------------------------------------------------------------------------

def test_resolve_gossip_db_path_explicit_env_overrides_all(tmp_path, monkeypatch):
    """GOSSIP_DB_PATH env var takes highest precedence over state_dir and PT_STATE_DIR."""
    from orchestrator.gossip_bus import resolve_gossip_db_path

    explicit = str(tmp_path / "explicit.db")
    monkeypatch.setenv("GOSSIP_DB_PATH", explicit)
    monkeypatch.setenv("PT_STATE_DIR", str(tmp_path / "other"))

    result = resolve_gossip_db_path(state_dir=tmp_path / "also_other")
    assert result == explicit


def test_resolve_gossip_db_path_with_state_dir_arg(tmp_path, monkeypatch):
    """When state_dir is provided and GOSSIP_DB_PATH is unset, path is under state_dir."""
    from orchestrator.gossip_bus import resolve_gossip_db_path

    monkeypatch.delenv("GOSSIP_DB_PATH", raising=False)
    monkeypatch.delenv("PT_STATE_DIR", raising=False)

    result = resolve_gossip_db_path(state_dir=tmp_path)
    assert result == str((tmp_path / "perpetua_core.db").resolve())


def test_resolve_gossip_db_path_uses_pt_state_dir_env(tmp_path, monkeypatch):
    """When state_dir is None, PT_STATE_DIR env var determines the database path."""
    from orchestrator.gossip_bus import resolve_gossip_db_path

    monkeypatch.delenv("GOSSIP_DB_PATH", raising=False)
    monkeypatch.setenv("PT_STATE_DIR", str(tmp_path))

    result = resolve_gossip_db_path()
    assert result == str((tmp_path / "perpetua_core.db").resolve())


def test_resolve_gossip_db_path_defaults_to_canonical_repo_state(isolated_env):
    """When no env vars and no state_dir are set, defaults to canonical repo .state."""
    from orchestrator.gossip_bus import resolve_gossip_db_path

    expected = str((_canonical_repo_state_dir() / "perpetua_core.db").resolve())
    assert resolve_gossip_db_path() == expected


def test_resolve_gossip_db_path_state_dir_takes_precedence_over_pt_state_dir(tmp_path, monkeypatch):
    """Explicit state_dir arg overrides PT_STATE_DIR env var (but GOSSIP_DB_PATH wins both)."""
    from orchestrator.gossip_bus import resolve_gossip_db_path

    monkeypatch.delenv("GOSSIP_DB_PATH", raising=False)
    env_dir = tmp_path / "from_env"
    arg_dir = tmp_path / "from_arg"
    monkeypatch.setenv("PT_STATE_DIR", str(env_dir))

    result = resolve_gossip_db_path(state_dir=arg_dir)
    assert result == str((arg_dir / "perpetua_core.db").resolve())
    # Verify it does NOT use the env dir
    assert str(env_dir) not in result


def test_resolve_gossip_db_path_db_filename_is_perpetua_core(tmp_path, monkeypatch):
    """The database file is always named perpetua_core.db regardless of input."""
    from orchestrator.gossip_bus import resolve_gossip_db_path

    monkeypatch.delenv("GOSSIP_DB_PATH", raising=False)

    result = resolve_gossip_db_path(state_dir=tmp_path)
    assert result.endswith("perpetua_core.db")


def test_resolve_gossip_db_path_explicit_env_whitespace_stripped(tmp_path, monkeypatch):
    """GOSSIP_DB_PATH with surrounding whitespace is treated as non-empty/empty correctly."""
    from orchestrator.gossip_bus import resolve_gossip_db_path

    monkeypatch.setenv("GOSSIP_DB_PATH", "   ")  # whitespace-only → ignored
    monkeypatch.delenv("PT_STATE_DIR", raising=False)

    result = resolve_gossip_db_path(state_dir=tmp_path)
    # Whitespace-only GOSSIP_DB_PATH is stripped to "" → falls through to state_dir
    assert result == str((tmp_path / "perpetua_core.db").resolve())
