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
import time
from typing import Any, Sequence

from utils.win_exec import (
    CONTAINED,
    UNKNOWN,
    WinExecError,
    popen_tree_kwargs,
    resolve_executable,
    safe_argv,
    terminate_tree,
)

__all__ = [
    "CONTAINED",
    "UNKNOWN",
    "WinExecError",
    "prepare_cli_command",
    "cli_spawn_kwargs",
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


def cli_spawn_kwargs() -> dict[str, Any]:
    """Extra spawn kwargs so a CLI child's tree can be killed (Windows only).

    Returns ``{}`` on POSIX to leave process-group behaviour untouched.
    """
    return popen_tree_kwargs() if _is_windows() else {}


class _AsyncProcAdapter:
    """Present an ``asyncio`` subprocess through the Popen-like surface ``terminate_tree`` needs."""

    def __init__(self, proc: Any) -> None:
        """Wrap ``proc`` (an ``asyncio.subprocess.Process`` or compatible)."""
        self._proc = proc
        self.pid = proc.pid

    def poll(self) -> int | None:
        """Return the child's exit code, or ``None`` while it runs."""
        return self._proc.returncode

    def wait(self, timeout: float | None = None) -> int:
        """Block (in a worker thread) until exit; raise ``subprocess.TimeoutExpired`` on timeout."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while self._proc.returncode is None:
            if deadline is not None and time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired("cli-child", timeout)
            time.sleep(0.05)
        return self._proc.returncode

    def kill(self) -> None:
        """Force-kill the direct child."""
        self._proc.kill()


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
    """Terminate a CLI child (its whole tree on Windows) and return a containment status.

    Returns ``contained`` / ``escaped:<n>`` / ``unknown`` (see
    ``utils.win_exec.terminate_tree``). On POSIX only the direct child is
    signalled with ``terminate()`` as before and the result is ``contained``
    once it has exited, else ``unknown``. On Windows the blocking tree kill runs
    in a worker thread; any failure there degrades to ``unknown`` (never raises)
    after a best-effort direct ``terminate()``.
    """
    if not _is_windows():
        if proc.returncode is None:
            with contextlib.suppress(Exception):
                proc.terminate()
            await _wait_exit(proc, grace)
        return CONTAINED if proc.returncode is not None else UNKNOWN
    try:
        return await asyncio.to_thread(terminate_tree, _AsyncProcAdapter(proc), grace)
    except Exception:  # noqa: BLE001 - honest degradation, never a false "contained"
        with contextlib.suppress(Exception):
            proc.terminate()
        return UNKNOWN
