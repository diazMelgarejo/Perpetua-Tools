"""Windows-safe launch and kill helpers for partner-CLI worker children.

Thin adapter over ``utils.win_exec`` (byte-mirrored from orama-system). On
POSIX every helper is a pass-through, so existing behaviour is unchanged; on
Windows it resolves executables to absolute paths (never the cwd), refuses
cmd.exe metacharacters bound for ``.cmd`` shims, and kills whole process trees
while reporting an honest containment status.
"""
from __future__ import annotations

import asyncio
import contextlib
import subprocess
import sys
from typing import Any, Sequence

from utils.win_exec import (
    CONTAINED,
    CONTAINMENT_SCOPE_NOTE,
    UNKNOWN,
    LaunchError,
    WinExecError,
    launch_tree,
    resolve_executable,
    safe_argv,
    terminate_tree,
)

__all__ = [
    "CONTAINED",
    "CONTAINMENT_SCOPE_NOTE",
    "UNKNOWN",
    "LaunchError",
    "WinExecError",
    "containment_note",
    "prepare_cli_command",
    "spawn_cli",
    "terminate_cli_tree",
]


def _is_windows() -> bool:
    """True on Windows (evaluated per call so tests can patch it)."""
    return sys.platform == "win32"


def prepare_cli_command(cmd: Sequence[str]) -> list[str]:
    """Return the argv to launch: absolute executable plus safely checked args.

    On Windows ``cmd[0]`` is resolved via ``resolve_executable`` (PATH only,
    absolute result, PATHEXT required) and the argv passes ``safe_argv``, which
    raises ``CmdArgumentRefused`` for cmd.exe metacharacters aimed at a
    ``.cmd``/``.bat`` shim. Failures raise ``WinExecError`` (a ``ValueError``);
    there is no fallback to the bare name. On POSIX the command is returned as
    a list, unchanged.
    """
    if not cmd:
        raise WinExecError("empty command")
    if not _is_windows():
        return list(cmd)
    return safe_argv(resolve_executable(cmd[0]), cmd[1:])


class _PopenProxy:
    """Asyncio-style facade over a ``launch_tree`` Popen (Windows Job Object child).

    Exposes ``pid``/``returncode``/``communicate``/``wait``/``terminate``/``kill``
    so the supervisor and worker code treat it like an asyncio subprocess, while
    ``popen`` keeps the real handle that ``terminate_tree`` needs.
    """

    def __init__(self, popen: subprocess.Popen) -> None:
        """Wrap ``popen`` (started by ``launch_tree``)."""
        self.popen = popen
        self.pid = popen.pid

    @property
    def returncode(self) -> int | None:
        """Exit code, or ``None`` while the child runs (polls the Popen)."""
        return self.popen.poll()

    async def communicate(self) -> tuple[bytes, bytes]:
        """Collect stdout/stderr and wait for exit without blocking the event loop."""
        return await asyncio.to_thread(self.popen.communicate)

    async def wait(self) -> int:
        """Wait for exit without blocking the event loop."""
        return await asyncio.to_thread(self.popen.wait)

    def terminate(self) -> None:
        """Terminate the direct child only (tree kill is ``terminate_cli_tree``)."""
        self.popen.terminate()

    def kill(self) -> None:
        """Force-kill the direct child only."""
        self.popen.kill()


async def spawn_cli(cmd: Sequence[str], **kwargs: Any) -> Any:
    """Start ``cmd`` with stdout/stderr pipes and stdin ignored; return a process handle.

    POSIX: ``asyncio.create_subprocess_exec`` exactly as before. Windows:
    ``launch_tree`` (suspended start inside a kill-on-close Job Object, so every
    descendant is a job member) run in a thread and wrapped in ``_PopenProxy``.
    A ``LaunchError`` (suspended start could not complete) becomes a
    ``RuntimeError`` like other launch failures.
    """
    if not _is_windows():
        return await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            **kwargs,
        )
    try:
        popen = await asyncio.to_thread(
            launch_tree, list(cmd),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
            **kwargs,
        )
    except LaunchError as exc:
        raise RuntimeError(f"launch failed: {exc}") from exc
    return _PopenProxy(popen)


def containment_note(status: str) -> str:
    """Return a human suffix for a containment ``status`` (empty for POSIX ``contained``).

    ``contained`` is stated only when the status is exactly ``contained``; on
    Windows the job-scope caveat is always appended, and any other status is
    spelled out.
    """
    parts = []
    if status != CONTAINED:
        parts.append(f"process-tree containment: {status}")
    if _is_windows():
        parts.append(CONTAINMENT_SCOPE_NOTE)
    return f" ({'; '.join(parts)})" if parts else ""


async def _wait_exit(proc: Any, timeout: float) -> None:
    """Wait up to ``timeout`` seconds for ``proc`` to exit (monotonic deadline)."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while proc.returncode is None:
        remaining = deadline - loop.time()
        if remaining <= 0:
            return
        try:
            await asyncio.wait_for(proc.wait(), timeout=remaining)
        except asyncio.TimeoutError:
            return


async def terminate_cli_tree(proc: Any, grace: float = 5.0) -> str:
    """Terminate a CLI child (its whole job on Windows) and return a containment status.

    Returns exactly ``contained`` / ``escaped:<n>`` / ``unknown`` (job-scoped on
    Windows, see ``CONTAINMENT_SCOPE_NOTE``). On Windows ``terminate_tree`` runs
    in a worker thread and is called even if the root already exited, so
    orphaned descendants still die; a handle not started by ``spawn_cli`` or a
    failure yields ``unknown`` after a best-effort ``terminate()``. On POSIX only
    the direct child is signalled when still running (unchanged) and the result
    is ``contained`` once it has exited, else ``unknown``.
    """
    if not _is_windows():
        if proc.returncode is None:
            with contextlib.suppress(Exception):
                proc.terminate()
            await _wait_exit(proc, grace)
        return CONTAINED if proc.returncode is not None else UNKNOWN
    popen = getattr(proc, "popen", None)
    try:
        if popen is None:
            raise WinExecError("child was not started through launch_tree")
        return await asyncio.to_thread(terminate_tree, popen, grace)
    except Exception:  # noqa: BLE001 - honest degradation, never a false "contained"
        with contextlib.suppress(Exception):
            proc.terminate()
        return UNKNOWN
