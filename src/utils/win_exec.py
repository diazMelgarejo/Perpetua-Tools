"""Safe partner-CLI resolution, launch argv checks and process-tree termination.

Standalone (stdlib only, no repo-internal imports) so orama-system and
Perpetua-Tools can carry a byte-identical copy; ``scripts/review/
verify_model_endpoint_policy_parity.py`` enforces that.

Public API:
  * ``resolve_executable``  - name or path -> ABSOLUTE executable path, never cwd.
  * ``find_bare_command``   - PATH-only lookup (explicit entries, no cwd).
  * ``safe_argv``           - argv for a resolved path; refuses cmd.exe metacharacters
                              in arguments when the target is a ``.cmd``/``.bat`` shim.
  * ``popen_tree_kwargs``   - Popen kwargs that make a child's tree killable.
  * ``terminate_tree``      - kill a process and its descendants, return an honest
                              containment status (``contained`` | ``escaped:<n>`` | ``unknown``).
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

CONTAINED = "contained"
UNKNOWN = "unknown"

# Characters cmd.exe interprets inside a command line, plus line breaks and NUL.
CMD_METACHARACTERS = frozenset('%!^&|<>"\n\r\x00')
_CMD_SUFFIXES = frozenset({".cmd", ".bat"})


def _win() -> bool:
    """True on Windows (evaluated per call so tests can patch ``sys.platform``)."""
    return sys.platform == "win32"


class WinExecError(ValueError):
    """Typed failure for resolution or launch-safety refusals."""


class CmdArgumentRefused(WinExecError):
    """An argument contains characters that cmd.exe would interpret."""


def escaped_count(status: str) -> int:
    """Return N for an ``escaped:<N>`` containment status, else 0."""
    if status.startswith("escaped:"):
        try:
            return int(status.split(":", 1)[1])
        except ValueError:
            return 0
    return 0


def _is_bare_command(candidate: str) -> bool:
    """True when ``candidate`` names a command to look up, not a pathname."""
    if "/" in candidate or "\\" in candidate:
        return False
    return not (_win() and len(candidate) >= 2 and candidate[1] == ":")


def _search_path() -> str:
    """The PATH string used for lookup, entries unquoted; unset PATH falls back to ``os.defpath``."""
    raw = os.environ.get("PATH", os.defpath)
    return os.pathsep.join(entry.strip().strip('"') for entry in raw.split(os.pathsep))


def _search_path_entries() -> tuple[str, ...]:
    """Return non-empty PATH directories with surrounding quotes removed (never the cwd)."""
    return tuple(e for e in _search_path().split(os.pathsep) if e)


def _windows_pathext() -> tuple[str, ...]:
    """Return PATHEXT suffixes as configured, in order, without empty entries."""
    return tuple(
        e.strip() for e in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if e.strip()
    )


def _windows_executable_extensions() -> tuple[str, ...]:
    """Return casefolded PATHEXT suffixes, used for comparison only."""
    return tuple(e.casefold() for e in _windows_pathext())


def find_bare_command(command: str) -> Optional[str]:
    """Find ``command`` only through explicit non-empty PATH directories.

    ``shutil.which`` can consult the working directory on Windows before a
    supplied PATH; joining each approved directory ourselves keeps a planted
    local binary from shadowing the installed one.
    """
    for directory in _search_path_entries():
        base = Path(directory) / command
        candidates: tuple[Path, ...] = (base,)
        if _win():
            candidates = (base, *(
                base.with_name(f"{base.name}{ext}") for ext in _windows_pathext()
            ))
            if base.suffix.casefold() not in _windows_executable_extensions():
                candidates = (*candidates[1:], base)
        for candidate in candidates:
            if candidate.is_file() and (_win() or os.access(candidate, os.X_OK)):
                return str(candidate)
    return None


def resolve_executable(candidate: str) -> str:
    """Resolve ``candidate`` (bare name or path) to an absolute executable path.

    Bare names are looked up on PATH only, never the current directory. Paths
    are expanded (``~``) and made absolute. On Windows the result must carry a
    PATHEXT extension, so ``.ps1`` and extensionless shims are refused. There is
    no fallback to the bare name; failure raises ``WinExecError``.
    """
    if not isinstance(candidate, str) or not candidate.strip() or "\x00" in candidate:
        raise WinExecError("invalid executable name")
    candidate = os.path.expanduser(candidate)
    found = find_bare_command(candidate) if _is_bare_command(candidate) else shutil.which(candidate)
    if found is None or not Path(found).is_file():
        raise WinExecError("executable is unavailable or not executable")
    if _win() and Path(found).suffix.casefold() not in _windows_executable_extensions():
        raise WinExecError("executable has no permitted Windows extension")
    return os.path.abspath(found)


def _is_cmd_shim(path: str) -> bool:
    """True when ``path`` is a ``.cmd``/``.bat`` file that cmd.exe would interpret."""
    return Path(path).suffix.casefold() in _CMD_SUFFIXES


def safe_argv(executable: str, args: Sequence[str] = ()) -> list[str]:
    """Return ``[executable, *args]`` or refuse arguments cmd.exe would reinterpret.

    ``.exe`` targets keep exact argv round-trip. For ``.cmd``/``.bat`` targets any
    argument (or the path itself) containing ``% ! ^ & | < > "``, a newline or
    NUL raises ``CmdArgumentRefused`` rather than risk injection.
    """
    argv = [str(executable), *(str(a) for a in args)]
    if _is_cmd_shim(argv[0]):
        for item in argv:
            bad = sorted(c for c in set(item) if c in CMD_METACHARACTERS)
            if bad:
                names = " ".join(repr(c) for c in bad)
                raise CmdArgumentRefused(
                    f"refusing to pass cmd metacharacter(s) {names} through a .cmd/.bat shim; "
                    "use an .exe target or pass the data via stdin or a file"
                )
    return argv


def popen_tree_kwargs() -> dict:
    """Popen kwargs giving the child its own process group/session so its tree can be killed."""
    if _win():
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}  # type: ignore[attr-defined]
    return {"start_new_session": True}


# --------------------------------------------------------------------------- tree kill

def _system32(name: str) -> str:
    """Absolute path of a System32 tool, derived from %SystemRoot%."""
    root = os.environ.get("SystemRoot") or os.environ.get("SYSTEMROOT") or r"C:\Windows"
    return os.path.join(root, "System32", name)


def _win_pid_alive(pid: int) -> bool:
    """True when a Windows process with ``pid`` exists and has not exited."""
    import ctypes

    k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    k32.OpenProcess.restype = ctypes.c_void_p
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not k32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code)):
            return True
        return code.value == 259  # STILL_ACTIVE
    finally:
        k32.CloseHandle(ctypes.c_void_p(handle))


def _win_descendants(root_pid: int) -> Optional[set[int]]:
    """Descendant PIDs of ``root_pid`` via psutil, else a CIM query; ``None`` if unobtainable."""
    try:
        import psutil  # type: ignore[import-not-found]

        return {p.pid for p in psutil.Process(root_pid).children(recursive=True)}
    except ImportError:
        pass
    except Exception:  # noqa: BLE001 - psutil NoSuchProcess etc.
        return None
    script = (
        "Get-CimInstance Win32_Process | ForEach-Object "
        "{ '{0} {1}' -f $_.ProcessId, $_.ParentProcessId }"
    )
    try:
        out = subprocess.run(
            [_system32(r"WindowsPowerShell\v1.0\powershell.exe"),
             "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    children: dict[int, list[int]] = {}
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and all(x.isdigit() for x in parts):
            children.setdefault(int(parts[1]), []).append(int(parts[0]))
    if not children:
        return None
    found: set[int] = set()
    stack = [root_pid]
    while stack:
        for child in children.get(stack.pop(), []):
            if child not in found and child != root_pid:
                found.add(child)
                stack.append(child)
    return found


def _job_terminate(pid: int) -> bool:
    """Best effort: put ``pid`` in a kill-on-close Job Object (pywin32) and terminate it."""
    try:
        import win32api  # type: ignore[import-not-found]
        import win32con  # type: ignore[import-not-found]
        import win32job  # type: ignore[import-not-found]

        handle = win32api.OpenProcess(win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, pid)
        job = win32job.CreateJobObject(None, "")
        info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        info["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
        win32job.AssignProcessToJobObject(job, handle)
        win32job.TerminateJobObject(job, 1)
        return True
    except Exception:  # noqa: BLE001 - any failure falls back to taskkill
        return False


def _taskkill(args: list[str]) -> None:
    """Run System32 ``taskkill.exe`` (absolute path) quietly; ignore launch failures."""
    try:
        subprocess.run([_system32("taskkill.exe"), *args], capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _terminate_tree_windows(proc: "subprocess.Popen", grace: float) -> str:
    """Windows tree kill: ``taskkill /F /T`` from the live root, Job Object as fallback; verify by PID.

    The tree is killed while the root is still alive (a dead root hides its
    children), then any descendant seen in the pre-kill snapshot that survives
    is killed individually and re-checked.
    """
    pid = proc.pid
    was_running = proc.poll() is None
    before = _win_descendants(pid) if was_running else None
    if was_running:
        _taskkill(["/F", "/T", "/PID", str(pid)])
        if proc.poll() is None:
            _job_terminate(pid)
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        return f"escaped:{1 + len(before or ())}"
    if before is None:
        return UNKNOWN
    alive = {p for p in before if _win_pid_alive(p)}
    for straggler in alive:
        _taskkill(["/F", "/PID", str(straggler)])
    deadline = time.monotonic() + min(grace, 3.0)
    alive = {p for p in alive if _win_pid_alive(p)}
    while alive and time.monotonic() < deadline:
        time.sleep(0.1)
        alive = {p for p in alive if _win_pid_alive(p)}
    return f"escaped:{len(alive)}" if alive else CONTAINED


def _terminate_tree_posix(proc: "subprocess.Popen", grace: float) -> str:
    """POSIX tree kill via the child's own process group; verified by probing the group."""
    pid = proc.pid
    try:
        own_group = os.getpgid(pid) == pid
    except OSError:
        own_group = False
    if not own_group:
        # Not a group leader (spawned without start_new_session): killing the
        # group would hit the caller. Kill only the child and say so.
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
        return UNKNOWN
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pid, sig)
        except ProcessLookupError:
            break
        except PermissionError:
            return UNKNOWN
        try:
            proc.wait(timeout=grace if sig == signal.SIGTERM else 2)
        except subprocess.TimeoutExpired:
            pass
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                return CONTAINED
            time.sleep(0.05)
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return CONTAINED
    except PermissionError:
        return UNKNOWN
    return "escaped:1"


def terminate_tree(proc: "subprocess.Popen", grace: float = 5.0) -> str:
    """Kill ``proc`` and its descendants and return the containment result.

    Returns ``contained`` only when no descendant observed before the kill
    remains (Windows) or the process group is empty (POSIX); ``escaped:<n>``
    when ``n`` survivors were seen; ``unknown`` when it could not be checked
    (no descendant listing, or the child was not started in its own group/
    session - use ``popen_tree_kwargs``). Never raises for an already-dead child.
    """
    if _win():
        return _terminate_tree_windows(proc, grace)
    return _terminate_tree_posix(proc, grace)
