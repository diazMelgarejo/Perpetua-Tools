"""Runtime dispatch must claim durably and authorize before provider effects."""
from __future__ import annotations

import asyncio
import multiprocessing
from pathlib import Path

import pytest


def test_restarts_do_not_repeat_unknown_effects(tmp_path: Path) -> None:
    """Dropping durable started claims would repeat a possibly completed effect."""
    from orchestrator.dispatch_guard import DispatchGuard, DispatchRequest, DuplicateDispatch

    request = DispatchRequest(scope="session-a", provider="echo", model="echo", goal="review", prompt="code")
    effects: list[str] = []

    async def effect() -> dict:
        """Simulate an effect followed by a lost acknowledgement."""
        effects.append("ran")
        raise RuntimeError("ack lost")

    with pytest.raises(RuntimeError, match="ack lost"):
        asyncio.run(DispatchGuard(tmp_path).execute(request, effect))
    with pytest.raises(DuplicateDispatch):
        asyncio.run(DispatchGuard(tmp_path).execute(request, effect))
    assert effects == ["ran"]


def test_scopes_models_providers_and_goals_are_distinct(tmp_path: Path) -> None:
    """Omitting identity fields would collapse independent dispatches."""
    from dataclasses import replace
    from orchestrator.dispatch_guard import DispatchGuard, DispatchRequest

    first = DispatchRequest(scope="a", provider="echo", model="one", goal="review", prompt="code")
    requests = [first, replace(first, scope="b"), replace(first, model="two"), replace(first, provider="other"), replace(first, goal="fix")]
    effects: list[str] = []

    async def effect() -> dict:
        """Record a provider effect without external I/O."""
        effects.append("ran")
        return {"ok": True}

    for request in requests:
        asyncio.run(DispatchGuard(tmp_path).execute(request, effect))
    assert len(effects) == 5


def test_configured_approval_fails_closed_without_verifier(tmp_path: Path) -> None:
    """A caller flag must not satisfy a configured operator approval requirement."""
    from orchestrator.dispatch_guard import DispatchGuard, DispatchRequest, DispatchPolicy

    request = DispatchRequest(scope="a", provider="echo", model="one", goal="review", prompt="code")
    effects: list[str] = []

    async def effect() -> dict:
        """Record whether authorization incorrectly reaches the effect."""
        effects.append("ran")
        return {"ok": True}

    policy = lambda request: DispatchPolicy(requires_operator_approval=True)
    with pytest.raises(PermissionError, match="approval"):
        asyncio.run(DispatchGuard(tmp_path, policy=policy).execute(request, effect))
    assert effects == []
    asyncio.run(DispatchGuard(tmp_path, policy=policy, approval_verifier=lambda request: True).execute(request, effect))
    assert effects == ["ran"]


def test_direct_supervisor_dispatch_is_governed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling the public runtime's dispatch path directly must retain dedup."""
    from orchestrator.supervisor import JobSpec, OrchestrationSupervisor
    from orchestrator.dispatch_guard import DuplicateDispatch

    supervisor = OrchestrationSupervisor(state_dir=tmp_path)
    spec = JobSpec(job_id="same", backend_hint="echo", prompt="hello", intent="echo")
    monkeypatch.setattr(supervisor, "_inject_memory_context", _identity)
    first = asyncio.run(supervisor._dispatch(spec))
    assert first
    with pytest.raises(DuplicateDispatch):
        asyncio.run(OrchestrationSupervisor(state_dir=tmp_path)._dispatch(spec))


async def _identity(spec: object) -> object:
    """Disable memory I/O while retaining the actual dispatch pipeline."""
    return spec


@pytest.mark.parametrize("field", ["job_id", "session_id"])
def test_generated_ids_do_not_change_dispatch_identity(tmp_path: Path, field: str) -> None:
    """Changing either correlation id alone must not authorize a second effect."""
    from orchestrator.dispatch_guard import DuplicateDispatch
    from orchestrator.supervisor import JobSpec, OrchestrationSupervisor

    effects: list[str] = []

    async def effect(spec: JobSpec) -> dict:
        """Record the provider boundary without external I/O."""
        effects.append(spec.prompt)
        return {"ok": True}

    first = JobSpec(job_id="job-a", session_id="session-a", prompt="review")
    second = first.model_copy(update={field: "different"})
    supervisor = OrchestrationSupervisor(tmp_path)
    asyncio.run(supervisor._guarded_worker(first, first, "echo", effect))
    with pytest.raises(DuplicateDispatch):
        asyncio.run(supervisor._guarded_worker(second, second, "echo", effect))
    assert effects == ["review"]


def test_openai_provider_uses_model_planner(tmp_path: Path) -> None:
    """Direct provider names cannot bypass canonical approval requirements."""
    from orchestrator.dispatch_guard import DispatchGuard, DispatchRequest

    async def effect() -> dict:
        """Fail if an unapproved model reaches its provider."""
        pytest.fail("unapproved model reached provider")

    with pytest.raises((PermissionError, ValueError)):
        asyncio.run(DispatchGuard(tmp_path).execute(
            DispatchRequest("a", "openai", "gpt-6.1-sol", "review", "code", effort="medium", fast=False), effect
        ))


@pytest.mark.skipif(__import__("os").name == "nt", reason="POSIX symlink ownership")
def test_trusted_symlink_ancestor_is_accepted(tmp_path: Path) -> None:
    """A root or user owned symlink to a trusted ancestor permits dispatch."""
    from orchestrator.dispatch_guard import DispatchGuard, DispatchRequest

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)

    async def effect() -> dict:
        """Return a successful result without external I/O."""
        return {"ok": True}

    assert asyncio.run(DispatchGuard(link / "state").execute(
        DispatchRequest("a", "echo", "echo", "review", "code"), effect
    )) == {"ok": True}


@pytest.mark.skipif(__import__("os").name == "nt", reason="POSIX symlink ownership")
def test_symlink_chain_through_writable_parent_is_refused(tmp_path: Path) -> None:
    """A trusted outer link must not conceal an attacker-writable target parent."""
    from orchestrator.dispatch_guard import DispatchGuard, DispatchRequest

    target = tmp_path / "target"
    target.mkdir()
    (target / "state").mkdir()
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir()
    unsafe.chmod(0o777)
    (unsafe / "bridge").symlink_to(target, target_is_directory=True)
    outer = tmp_path / "outer"
    outer.symlink_to(unsafe / "bridge", target_is_directory=True)

    async def effect() -> dict:
        """Fail if unsafe storage permits a provider effect."""
        pytest.fail("unsafe symlink chain reached provider")

    with pytest.raises(PermissionError, match="ancestor"):
        asyncio.run(DispatchGuard(outer / "state").execute(
            DispatchRequest("a", "echo", "echo", "review", "code"), effect
        ))
    assert not (target / "state" / "dispatch_claims.sqlite3").exists()


@pytest.mark.parametrize("provider", ["codex", "gemini", "agy"])
@pytest.mark.parametrize("options", [{"model": "unattested-model"}, {"effort": "high"}, {"fast": False}])
def test_unattested_cli_model_override_cannot_authorize_effect(tmp_path: Path, provider: str, options: dict) -> None:
    """Ignored CLI options cannot identify or authorize a provider effect."""
    from orchestrator.supervisor import JobSpec, OrchestrationSupervisor

    effects = []

    async def effect(spec: object) -> dict:
        """Record a provider effect without running an external CLI."""
        effects.append(True)
        return {"ok": True}

    with pytest.raises(ValueError, match="CLI"):
        spec = JobSpec(prompt="task", metadata=options)
        asyncio.run(OrchestrationSupervisor(state_dir=tmp_path)._guarded_worker(spec, spec, provider, effect))
    assert not effects


def _compete(state_dir: str, start: object, outcomes: object) -> None:
    """Use separate interpreters and SQLite connections against one claim."""
    from orchestrator.dispatch_guard import DispatchGuard, DispatchRequest, DuplicateDispatch

    async def effect() -> dict:
        """Report an effect only after the durable winner claim."""
        outcomes.put("effect")
        return {"ok": True}

    start.wait()
    try:
        asyncio.run(DispatchGuard(state_dir).execute(DispatchRequest("shared", "echo", "echo", "review", "code"), effect))
    except DuplicateDispatch:
        outcomes.put("duplicate")


def test_competing_processes_have_one_effect(tmp_path: Path) -> None:
    """An in-memory lock or SELECT-before-INSERT would admit competing effects."""
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    outcomes = context.Queue()
    processes = [context.Process(target=_compete, args=(str(tmp_path), start, outcomes)) for _ in range(3)]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join(15)
        assert process.exitcode == 0
    assert sorted(outcomes.get(timeout=2) for _ in processes) == ["duplicate", "duplicate", "effect"]


def test_policy_denial_never_reaches_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A policy evaluated only at submission could be bypassed at actual dispatch."""
    from orchestrator.supervisor import JobSpec, OrchestrationSupervisor
    from orchestrator.dispatch_guard import DispatchPolicy
    from orchestrator.worker_registry import WORKER_REGISTRY

    effects: list[str] = []

    async def effect(spec: object) -> dict:
        """Represent the provider boundary without model/network calls."""
        effects.append("ran")
        return {"ok": True}

    monkeypatch.setitem(WORKER_REGISTRY, "echo", effect)
    supervisor = OrchestrationSupervisor(tmp_path, dispatch_policy=lambda request: DispatchPolicy(allowed=False, reason="outside scope"))
    monkeypatch.setattr(supervisor, "_inject_memory_context", _identity)
    with pytest.raises(PermissionError, match="outside scope"):
        asyncio.run(supervisor._dispatch(JobSpec(backend_hint="echo", prompt="hello")))
    assert effects == []


def test_cancelled_effect_remains_claimed(tmp_path: Path) -> None:
    """Cancellation cannot prove that the remote effect did not happen."""
    from orchestrator.dispatch_guard import DispatchGuard, DispatchRequest, DuplicateDispatch

    request = DispatchRequest("shared", "echo", "echo", "review", "code")

    async def effect() -> dict:
        """Simulate cancellation during provider execution."""
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(DispatchGuard(tmp_path).execute(request, effect))
    with pytest.raises(DuplicateDispatch):
        asyncio.run(DispatchGuard(tmp_path).execute(request, effect))


@pytest.mark.skipif(__import__("os").name == "nt", reason="POSIX ownership/mode check; Windows ACL qualification is separate")
def test_writable_state_directory_fails_before_effect(tmp_path: Path) -> None:
    """Private files do not protect a ledger in a directory another user can replace."""
    from orchestrator.dispatch_guard import DispatchGuard, DispatchRequest

    state = tmp_path / "unsafe"
    state.mkdir(mode=0o777)
    state.chmod(0o777)
    effects: list[str] = []

    async def effect() -> dict:
        """Record whether unsafe storage incorrectly permits dispatch."""
        effects.append("ran")
        return {"ok": True}

    with pytest.raises(PermissionError, match="directory"):
        asyncio.run(DispatchGuard(state).execute(DispatchRequest("a", "echo", "echo", "review", "code"), effect))
    assert effects == []


@pytest.mark.skipif(__import__("os").name == "nt", reason="POSIX ancestor policy; native ACLs require qualification")
def test_writable_ancestor_fails_before_effect(tmp_path: Path) -> None:
    """A protected state directory can still be renamed through an unsafe parent."""
    from orchestrator.dispatch_guard import DispatchGuard, DispatchRequest

    parent = tmp_path / "unsafe-parent"
    parent.mkdir()
    parent.chmod(0o777)
    state = parent / "private"
    state.mkdir(mode=0o700)

    async def effect() -> dict:
        """Never execute through an unsafe ancestor."""
        pytest.fail("unsafe ancestor reached provider")

    with pytest.raises(PermissionError, match="ancestor"):
        asyncio.run(DispatchGuard(state).execute(DispatchRequest("a", "echo", "echo", "review", "code"), effect))
