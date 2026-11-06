"""Portable producer identity and topology hygiene (closure row C4).

Covers: a random opaque producer identifier that is stable across restarts,
collision handling during creation, restrictive permissions on the local
identifier file, and synthetic legacy worktree labels flowing from gossip
through memory derivation and portable export without leaking branch names or
private paths. Unclassified legacy rows must be blocked from export.

All data below is synthetic. The private-looking paths are fixtures, not
workstation paths.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from orchestrator.coordination import producer_identity
from orchestrator.coordination.producer_identity import (
    UNAVAILABLE_PRODUCER_ID,
    ProducerIdError,
    is_opaque_producer_id,
    load_or_create_producer_id,
)
from orchestrator.coordination import topology_hygiene
from orchestrator.coordination.topology_hygiene import (
    LEGACY_REDACTED,
    classify_payload,
    export_portable_events,
    inventory_episodic,
    inventory_topology,
    portable_payload,
)
from orchestrator.gossip_bus import GossipBus

REPO_ROOT = Path(__file__).resolve().parent.parent

# Synthetic legacy fixtures (assembled so tracked text never holds a literal
# workstation path).
_SECRET_BRANCH = "feature/acme-merger-secret"
_PRIVATE_DIR = "/" + "/".join(["home", "alice", "worktrees", "acme-merger"])
_LEGACY_LABEL = f"{_SECRET_BRANCH}@{_PRIVATE_DIR}"
_UNCLASSIFIED_LABEL = "alice-laptop:" + "/".join(["", "Users", "alice", "repo"])
_FORBIDDEN = ("acme-merger", "alice", "/home/", "/Users/")


def _git(cwd: Path, *args: str) -> str:
    """Run git in ``cwd`` with a fixed identity and return stdout."""
    return subprocess.check_output(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=str(cwd), text=True, stderr=subprocess.DEVNULL,
    ).strip()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a throwaway repository on a revealing branch name."""
    repo = tmp_path / "acme-merger-repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _SECRET_BRANCH)
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
    return repo


def _label_in_subprocess(cwd: Path) -> str:
    """Return current_worktree_label() from a fresh interpreter (a restart)."""
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    env.pop("PT_STATE_DIR", None)
    env.pop("PT_PRODUCER_ID_FILE", None)  # exercise the real git-dir location
    return subprocess.check_output(
        [sys.executable, "-c",
         "from orchestrator.coordination.paths import current_worktree_label as f;"
         "print(f())"],
        cwd=str(cwd), env=env, text=True,
    ).strip()


# ── Random opaque identifier ────────────────────────────────────────────────


def test_label_is_opaque_and_stable_across_restarts(git_repo: Path) -> None:
    """Two fresh processes see the same random id with no topology in it."""
    first = _label_in_subprocess(git_repo)
    second = _label_in_subprocess(git_repo)
    assert first == second
    assert is_opaque_producer_id(first)
    for forbidden in ("acme-merger", str(git_repo), _SECRET_BRANCH):
        assert forbidden not in first


def test_identifier_file_is_private_to_the_owner(git_repo: Path) -> None:
    """The local id file lives in the untracked git dir with mode 0600."""
    label = _label_in_subprocess(git_repo)
    id_file = git_repo / ".git" / producer_identity.ID_FILE_NAME
    assert id_file.read_text(encoding="utf-8").strip() == label
    if os.name == "posix":
        assert stat.S_IMODE(id_file.stat().st_mode) == 0o600
    assert _git(git_repo, "status", "--porcelain") == ""


def test_linked_worktrees_get_distinct_identifiers(git_repo: Path, tmp_path: Path) -> None:
    """Each worktree has its own id; neither is derived from its path."""
    other = tmp_path / "second-acme-worktree"
    _git(git_repo, "worktree", "add", "-q", "-b", "other-secret", str(other))
    main_id = _label_in_subprocess(git_repo)
    other_id = _label_in_subprocess(other)
    assert is_opaque_producer_id(main_id) and is_opaque_producer_id(other_id)
    assert main_id != other_id


def test_concurrent_creator_adopts_the_winning_identifier(tmp_path: Path) -> None:
    """If another process creates the file first, the loser reuses its id."""
    id_path = tmp_path / "pt-producer-id"
    winner = "ptp-" + "a" * 32

    def racing_token() -> str:
        """Install another creator's complete identity before this draw returns."""
        id_path.write_text(winner + "\n", encoding="utf-8")
        return "b" * 32

    assert load_or_create_producer_id(id_path, token_hex=racing_token) == winner
    assert load_or_create_producer_id(id_path) == winner


def test_concurrent_readers_never_observe_empty_or_truncated_file(tmp_path: Path) -> None:
    """Finding P3: Concurrent readers never see a 0-byte or truncated id file."""
    id_path = tmp_path / "concurrent" / "pt-producer-id"
    reader_observations: list[str] = []
    errors: list[Exception] = []
    stop = False

    def reader() -> None:
        """Observe published content while concurrent creators compete."""
        while not stop:
            if id_path.exists():
                try:
                    txt = id_path.read_text(encoding="utf-8")
                    reader_observations.append(txt)
                except Exception as exc:
                    errors.append(exc)
            time.sleep(0.0001)

    def creator() -> str:
        """Create or adopt the stable producer identity."""
        return load_or_create_producer_id(id_path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        reader_futs = [ex.submit(reader) for _ in range(8)]
        creator_futs = [ex.submit(creator) for _ in range(8)]
        results = [f.result() for f in creator_futs]
        stop = True
        for f in reader_futs:
            f.result()

    assert not errors, f"readers encountered unexpected errors: {errors}"
    assert len(set(results)) == 1, f"creators converged on multiple winners: {results}"
    winning_id = results[0]
    assert is_opaque_producer_id(winning_id)

    # Verify that every single read observed by any reader thread was valid and non-empty
    assert len(reader_observations) > 0, "expected at least one reader observation while file existed"
    for obs in reader_observations:
        stripped = obs.strip()
        assert stripped == winning_id, f"reader observed unexpected or empty content: {obs!r}"
        assert is_opaque_producer_id(stripped)

    # Verify no dangling temporary files remain
    tmp_files = list(id_path.parent.glob(".*.tmp"))
    assert tmp_files == [], f"dangling temporary files left behind: {tmp_files}"


def test_sibling_collision_is_regenerated(tmp_path: Path) -> None:
    """A candidate already used by a sibling worktree is rejected and redrawn."""
    id_path = tmp_path / "pt-producer-id"
    taken = "c" * 32
    draws = iter([taken, "d" * 32])
    result = load_or_create_producer_id(
        id_path,
        token_hex=lambda: next(draws),
        sibling_ids=frozenset({"ptp-" + taken}),
    )
    assert result == "ptp-" + "d" * 32


def test_exhausted_collisions_fail_closed(tmp_path: Path) -> None:
    """Endless collisions raise instead of reusing another producer's id."""
    id_path = tmp_path / "pt-producer-id"
    with pytest.raises(ProducerIdError):
        load_or_create_producer_id(
            id_path,
            token_hex=lambda: "e" * 32,
            sibling_ids=frozenset({"ptp-" + "e" * 32}),
        )
    assert not id_path.exists()


def test_malformed_identifier_file_is_refused_not_rotated(tmp_path: Path) -> None:
    """A corrupt id file is reported and preserved, never silently replaced."""
    id_path = tmp_path / "pt-producer-id"
    id_path.write_text(_LEGACY_LABEL, encoding="utf-8")
    with pytest.raises(ProducerIdError):
        load_or_create_producer_id(id_path)
    assert id_path.read_text(encoding="utf-8") == _LEGACY_LABEL


def test_explicit_identifier_file_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PT_PRODUCER_ID_FILE names the identifier file explicitly."""
    target = tmp_path / "custom" / "id"
    monkeypatch.setenv("PT_PRODUCER_ID_FILE", str(target))
    assert producer_identity.producer_id_path() == target
    label = producer_identity.current_producer_id()
    assert is_opaque_producer_id(label)
    assert target.read_text(encoding="utf-8").strip() == label


def test_label_falls_back_to_placeholder_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Emit paths must never crash on identity errors."""
    def boom(*_args: object, **_kwargs: object) -> str:
        """Inject an identity failure at the emission boundary."""
        raise ProducerIdError("synthetic")

    monkeypatch.setattr(producer_identity, "load_or_create_producer_id", boom)
    from orchestrator.coordination.paths import current_worktree_label

    assert current_worktree_label() == UNAVAILABLE_PRODUCER_ID


# ── Legacy classification, memory derivation and export ─────────────────────


def test_classification_vocabulary() -> None:
    """Rows are opaque, legacy_label, no_topology or unclassified."""
    assert classify_payload({"worktree": "ptp-" + "0" * 32}) == "opaque"
    assert classify_payload({"worktree": _LEGACY_LABEL}) == "legacy_label"
    assert classify_payload({"worktree": "?@" + _PRIVATE_DIR}) == "legacy_label"
    assert classify_payload({"kind": "agent_pulse"}) == "no_topology"
    assert classify_payload({"worktree": None}) == "no_topology"
    assert classify_payload({"worktree": _UNCLASSIFIED_LABEL}) == "unclassified"
    assert classify_payload({"worktree": {"path": _PRIVATE_DIR}}) == "unclassified"


def test_portable_payload_sanitizes_legacy_labels_everywhere() -> None:
    """The label, its branch and its path are removed from every string."""
    payload = {
        "kind": "agent_claim",
        "agent_id": "agent-1",
        "task": "T1",
        "worktree": _LEGACY_LABEL,
        "notes": f"moved from {_LEGACY_LABEL}; see {_PRIVATE_DIR}/notes on {_SECRET_BRANCH}",
    }
    result = portable_payload(payload)
    assert result is not None
    assert result["worktree"] == LEGACY_REDACTED
    assert result["agent_id"] == "agent-1"
    dumped = json.dumps(result)
    for forbidden in _FORBIDDEN:
        assert forbidden not in dumped
    assert payload["worktree"] == _LEGACY_LABEL  # input not mutated


def test_portable_payload_blocks_unclassified_and_residual_private_paths() -> None:
    """Fail closed: unknown topology shapes and leftover paths are blocked."""
    assert portable_payload({"worktree": _UNCLASSIFIED_LABEL}) is None
    assert portable_payload({"kind": "agent_note", "message": f"at {_PRIVATE_DIR}"}) is None
    opaque = {"kind": "agent_pulse", "worktree": "ptp-" + "1" * 32}
    assert portable_payload(opaque) == opaque


def test_portable_payload_scrubs_nested_dictionary_keys() -> None:
    """Finding P2: Dictionary keys containing legacy fragments are scrubbed."""
    payload = {
        "worktree": _LEGACY_LABEL,
        f"status_{_PRIVATE_DIR}": "active",
        "nested": {
            f"branch_{_SECRET_BRANCH}": "merged",
            "safe_key": "safe_val",
        },
    }
    result = portable_payload(payload)
    assert result is not None
    assert result["worktree"] == LEGACY_REDACTED
    assert f"status_{LEGACY_REDACTED}" in result
    assert f"branch_{LEGACY_REDACTED}" in result["nested"]
    assert result["nested"]["safe_key"] == "safe_val"

    dumped = json.dumps(result)
    for forbidden in _FORBIDDEN:
        assert forbidden not in dumped


def test_portable_payload_blocks_private_dictionary_keys() -> None:
    """Finding P2: Dictionary keys containing un-scrubbed private paths fail closed."""
    # Key containing POSIX private path
    assert portable_payload({f"{_PRIVATE_DIR}/status": "ok"}) is None
    # Key containing Windows private path
    assert portable_payload({"C:\\" + "\\".join(["Users", "alice", "config"]): 1}) is None
    # Nested key containing private path
    assert portable_payload({"nested": {f"{_PRIVATE_DIR}/file": True}}) is None


def test_portable_payload_blocks_home_relative_private_paths_and_keys() -> None:
    """Finding P2: Private user home fragments fail closed in values and keys."""
    # User-relative home path in value
    assert portable_payload({"kind": "agent_note", "path": "~" + "alice/repo"}) is None
    # User-relative home path in key
    assert portable_payload({"kind": "agent_note", "~" + "alice/repo": "present"}) is None
    # User-relative home path inside nested dict
    assert portable_payload({"data": {"~" + "bob/secret": 123}}) is None
    # Home path with slash Users under tilde
    assert portable_payload({"kind": "agent_note", "path": "~/" + "/".join(["Users", "alice", "repo"])}) is None


def test_portable_payload_allows_approved_generic_anchors() -> None:
    """Finding P2: Approved generic anchors (e.g. generic tilde) are preserved."""
    safe_payload = {
        "kind": "agent_note",
        "path": "~/.gstack/projects/foo",
        "file": "~/repo/README.md",
        "~/repo/config.json": "present",
        "nested": {
            "~/shared/anchor": 42,
        },
    }
    result = portable_payload(safe_payload)
    assert result == safe_payload


async def _seed_legacy_bus(tmp_path: Path) -> GossipBus:
    """Store synthetic legacy, unclassified and opaque coordination rows."""
    bus = GossipBus(str(tmp_path / "legacy.db"))
    await bus.init_db()
    await bus.emit("heartbeat", {
        "kind": "agent_claim", "agent_id": "agent-1", "task": "rollout",
        "worktree": _LEGACY_LABEL, "notes": f"rollout claimed in {_LEGACY_LABEL}",
    })
    await bus.emit("heartbeat", {
        "kind": "agent_register", "agent_id": "agent-2", "agent_type": "t",
        "model": "m", "worktree": _UNCLASSIFIED_LABEL, "notes": "rollout helper",
    })
    await bus.emit("heartbeat", {
        "kind": "agent_pulse", "agent_id": "agent-3",
        "worktree": "ptp-" + "2" * 32, "notes": "rollout pulse",
    })
    return bus


async def test_legacy_labels_do_not_leak_through_memory_derivation(tmp_path: Path) -> None:
    """Recall text derived from gossip carries no branch names or paths."""
    from orchestrator.memory_node import retrieve_context

    bus = await _seed_legacy_bus(tmp_path)
    hits = await retrieve_context(
        "rollout", top_n=10, use_gbrain=False, gossip_bus=bus, lance_store=object()
    )
    texts = [hit["text"] for hit in hits]
    assert texts, "the opaque and sanitized legacy rows should still be recalled"
    joined = "\n".join(texts) + json.dumps([h.get("payload") for h in hits])
    for forbidden in _FORBIDDEN:
        assert forbidden not in joined
    assert "agent-2" not in joined  # unclassified row withheld


async def test_export_sanitizes_legacy_and_blocks_unclassified(tmp_path: Path) -> None:
    """The portable export never contains private topology."""
    bus = await _seed_legacy_bus(tmp_path)
    result = export_portable_events(bus.db_path)
    dumped = json.dumps(result.rows)
    for forbidden in _FORBIDDEN:
        assert forbidden not in dumped
    assert result.blocked == 1
    assert result.counts == {"legacy_label": 1, "unclassified": 1, "opaque": 1}
    kinds = sorted(row["payload"]["kind"] for row in result.rows)
    assert kinds == ["agent_claim", "agent_pulse"]


async def test_inventory_reports_counts_without_values(tmp_path: Path) -> None:
    """Inventory output is counts only and never echoes stored values."""
    bus = await _seed_legacy_bus(tmp_path)
    counts = inventory_topology(bus.db_path)
    assert counts["legacy_label"] == 1 and counts["unclassified"] == 1
    rendered = json.dumps(counts)
    for forbidden in _FORBIDDEN:
        assert forbidden not in rendered


def test_inventory_cli_prints_counts_only(tmp_path: Path) -> None:
    """The command-line inventory prints JSON counts and no private values."""
    episodic = tmp_path / "episodic.jsonl"
    episodic.write_text(
        json.dumps({"detail": f"worked in {_LEGACY_LABEL}"}) + "\n"
        + json.dumps({"detail": "clean"}) + "\n",
        encoding="utf-8",
    )
    assert inventory_episodic(episodic) == {"rows": 2, "private_path_rows": 1, "unparseable_rows": 0}
    out = subprocess.check_output(
        [sys.executable, "-m", "orchestrator.coordination.topology_hygiene",
         "inventory-episodic", str(episodic)],
        cwd=str(REPO_ROOT), text=True,
    )
    for forbidden in _FORBIDDEN:
        assert forbidden not in out
    assert json.loads(out)["private_path_rows"] == 1


def test_inventory_reads_the_store_without_writing(tmp_path: Path) -> None:
    """Inventory opens the database read-only, so it cannot migrate it."""
    missing = tmp_path / "absent.db"
    with pytest.raises(topology_hygiene.TopologyInventoryError):
        inventory_topology(str(missing))
    assert not missing.exists()
