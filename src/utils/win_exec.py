"""Safe partner-CLI resolution, launch argv checks and process-tree termination.

Standalone (stdlib only, no repo-internal imports) so orama-system and
Perpetua-Tools can carry a byte-identical copy; ``scripts/review/
verify_model_endpoint_policy_parity.py`` enforces that.

Public API:
  * ``resolve_executable``  - name or path -> ABSOLUTE executable path, never cwd.
  * ``find_bare_command``   - PATH-only lookup (explicit entries, no cwd).
  * ``safe_argv``           - argv for a resolved path; refuses cmd.exe metacharacters
                              in arguments when the target is a ``.cmd``/``.bat`` shim.
  * ``popen_tree_kwargs``   - Popen kwargs that give a child its own group/session.
  * ``launch_tree``         - Popen that, on Windows, assigns the child to a kill-on-close
                              Job Object before its first instruction runs (POSIX: own
                              session), giving authoritative membership.
  * ``terminate_tree``      - kill a launched process and everything in its job/group and
                              report ``contained`` | ``escaped:<n>`` | ``unknown``;
                              ``unknown`` for a process not started through ``launch_tree``.

Containment is job-scoped: it covers descendants created by ordinary process
creation inside the job, not processes started through out-of-job launchers
(WMI, DCOM, Task Scheduler, services). Call sites append
``CONTAINMENT_SCOPE_NOTE`` to what they report. The job handle is closed when
the Popen is garbage collected; because the job is KILL_ON_JOB_CLOSE that kills
any surviving member, which is the intended bounded lifetime.
"""
from __future__ import annotations

import ntpath
import os
import posixpath
import shutil
import signal
import subprocess
import sys
import time
import weakref
from pathlib import Path
from typing import Optional, Sequence

CONTAINED = "contained"
UNKNOWN = "unknown"
# Appended by call sites to every containment report: the status is job-scoped.
CONTAINMENT_SCOPE_NOTE = "(job-scoped containment; out-of-job launchers not covered)"

# Characters cmd.exe interprets inside a command line, plus line breaks and NUL.
CMD_METACHARACTERS = frozenset('%!^&|<>"\n\r\x00')
_CMD_SUFFIXES = frozenset({".cmd", ".bat"})
# Windows PATHEXT can include interpreter-hosted file types such as .vbs and
# .js.  ``Popen(..., shell=False)`` cannot safely launch those by pathname;
# accept only suffixes CreateProcess can start directly in this API.
_WINDOWS_DIRECT_EXECUTABLE_SUFFIXES = frozenset({".com", ".exe", ".cmd", ".bat"})


def _win() -> bool:
    """True on Windows (evaluated per call so tests can patch ``sys.platform``)."""
    return sys.platform == "win32"


def _pathmod():
    """Return the path module matching the effective platform (ntpath for Windows, posixpath otherwise)."""
    return ntpath if _win() else posixpath


class WinExecError(ValueError):
    """Typed failure for resolution or launch-safety refusals."""


class LaunchError(WinExecError):
    """A process could not be started safely (the half-started child was killed)."""


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


def _isabs(path: str) -> bool:
    """True for an absolute path in the effective flavour.

    Newer ``ntpath.isabs`` rejects a drive-less rooted path, but a POSIX host
    emulating Windows still receives real ``/x/y`` paths, so those stay absolute.
    """
    return _pathmod().isabs(path) or (os.name != "nt" and posixpath.isabs(path))


def _is_bare_command(candidate: str) -> bool:
    """True when ``candidate`` names a command to look up, not a pathname.

    Treat both separator spellings as a path on every host. This keeps a
    Windows-style relative path from becoming a POSIX bare-command lookup when
    tests or configuration are evaluated off Windows.
    """
    if "\\" in candidate:
        return False
    if _win():
        if "/" in candidate:
            return False
        return not bool(_pathmod().splitdrive(candidate)[0])
    return "/" not in candidate


def _search_path() -> str:
    """The PATH string used for lookup, entries unquoted; unset PATH falls back to ``os.defpath``."""
    p = _pathmod()
    default_path = p.defpath if hasattr(p, "defpath") else os.defpath
    raw = os.environ.get("PATH", default_path)
    return p.pathsep.join(entry.strip().strip('"') for entry in raw.split(p.pathsep))


def _is_unc(entry: str) -> bool:
    """True for a UNC/network path (two leading separators plus host), not a local device-prefix path."""
    if not _win():
        return False
    norm = entry.replace("/", "\\")
    if not norm.startswith("\\\\"):
        return False
    if norm.startswith("\\\\?\\") or norm.startswith("\\\\.\\"):
        return norm[4:7].upper() == "UNC"
    return True


def _search_path_entries(allow_unc: bool = False) -> tuple[str, ...]:
    """Return the absolute PATH directories usable for lookup.

    Empty, relative (dot, dot-dot, bare names) and, unless ``allow_unc``, UNC
    entries are dropped so lookup can never land in the working directory or on
    a network share. On Windows a drive-less rooted entry is dropped too.
    """
    p = _pathmod()
    kept = []
    for entry in _search_path().split(p.pathsep):
        if not entry or not _isabs(entry):
            continue
        if _win():
            if _is_unc(entry):
                if not allow_unc:
                    continue
            elif not p.splitdrive(entry)[0] and not (os.name != "nt" and posixpath.isabs(entry)):
                continue
        kept.append(entry)
    return tuple(kept)


def _windows_pathext() -> tuple[str, ...]:
    """Return PATHEXT suffixes as configured, in order, without empty entries."""
    return tuple(
        e.strip() for e in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if e.strip()
    )


def _windows_executable_extensions() -> tuple[str, ...]:
    """Return configured direct-launch suffixes, casefolded for comparison only."""
    p = _pathmod()
    return tuple(
        p.normcase(e)
        for e in _windows_pathext()
        if p.normcase(e) in _WINDOWS_DIRECT_EXECUTABLE_SUFFIXES
    )


def find_bare_command(command: str, allow_unc: bool = False) -> Optional[str]:
    """Find ``command`` only through absolute PATH directories (UNC only if ``allow_unc``).

    ``shutil.which`` can consult the working directory on Windows before a
    supplied PATH; joining each approved directory ourselves keeps a planted
    local binary from shadowing the installed one.
    """
    p = _pathmod()
    pathext = _windows_executable_extensions() if _win() else ()
    win_exts = pathext
    for directory in _search_path_entries(allow_unc):
        base = Path(directory) / command
        candidates: tuple[Path, ...] = (base,)
        if _win():
            candidates = (base, *(
                base.with_name(f"{base.name}{ext}") for ext in pathext
            ))
            _, cur_ext = p.splitext(command)
            if p.normcase(cur_ext) not in win_exts:
                candidates = (*candidates[1:], base)
        for candidate in candidates:
            if candidate.is_file() and (_win() or os.access(candidate, os.X_OK)):
                return str(candidate)
    return None


def resolve_executable(candidate: str, allow_unc: bool = False) -> str:
    """Resolve ``candidate`` (bare name or path) to an absolute executable path.

    Bare names are looked up on PATH only, never the current directory. Paths
    are expanded (``~``) and must then be absolute (a relative path would reach
    the working directory and raises ``WinExecError``). UNC PATH entries are
    ignored unless ``allow_unc``. On Windows the result must carry a
    direct-launch extension (``.com``, ``.exe``, ``.cmd`` or ``.bat``), so
    interpreter-hosted entries such as ``.ps1``, ``.vbs`` and ``.js`` are
    refused. There is no fallback to the bare name; failure raises
    ``WinExecError``.
    """
    if not isinstance(candidate, str) or not candidate.strip() or "\x00" in candidate:
        raise WinExecError("invalid executable name")
    candidate = os.path.expanduser(candidate)
    p = _pathmod()
    if _is_bare_command(candidate):
        found = find_bare_command(candidate, allow_unc)
    elif not _isabs(candidate):
        raise WinExecError("executable path must be absolute")
    elif _win() and _is_unc(candidate) and not allow_unc:
        raise WinExecError("UNC executable paths are refused")
    elif _win() and not p.splitdrive(candidate)[0] and not (os.name != "nt" and posixpath.isabs(candidate)):
        raise WinExecError("executable path must be absolute")
    else:
        found = shutil.which(candidate)
    if found is None or not Path(found).is_file():
        raise WinExecError("executable is unavailable or not executable")
    if _win():
        _, ext = p.splitext(found)
        if p.normcase(ext) not in _windows_executable_extensions():
            raise WinExecError("executable has no permitted Windows extension")
    # ``found`` is a real host-filesystem path: normalise it with the host module so
    # a Windows-emulating run on POSIX never rewrites /tmp/x into \tmp\x.
    return os.path.abspath(found)


def _is_cmd_shim(path: str) -> bool:
    """True when ``path`` is a ``.cmd``/``.bat`` file that cmd.exe would interpret.

    Host independent on purpose: a shim is refused with the same Windows name rules
    (case-insensitive, NTFS stream suffix, trailing dots and spaces) on every platform.
    """
    name = ntpath.split(path.replace("/", "\\"))[1]
    name = name.split(":", 1)[0].rstrip(" .")
    return ntpath.normcase(ntpath.splitext(name)[1]) in _CMD_SUFFIXES


def safe_argv(executable: str, args: Sequence[str] = ()) -> list[str]:
    """Return ``[executable, *args]`` or refuse arguments cmd.exe would reinterpret.

    ``.exe`` targets keep exact argv round-trip. For ``.cmd``/``.bat`` targets any
    argument (or the path itself) containing ``% ! ^ & | < > "`` or any
    control character (NUL through 0x1f) raises ``CmdArgumentRefused`` rather than risk injection.
    """
    argv = [str(executable), *(str(a) for a in args)]
    if _is_cmd_shim(argv[0]):
        for item in argv:
            bad = sorted(c for c in set(item) if c in CMD_METACHARACTERS or ord(c) < 0x20)
            if bad:
                names = " ".join(repr(c) for c in bad)
                raise CmdArgumentRefused(
                    f"refusing to pass cmd metacharacter(s) {names} through a .cmd/.bat shim; "
                    "use an .exe target or pass the data via stdin or a file"
                )
    return argv




def popen_tree_kwargs() -> dict:
    """Popen kwargs giving the child its own process group/session (no job; see ``launch_tree``)."""
    if _win():
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}  # type: ignore[attr-defined]
    return {"start_new_session": True}


# --------------------------------------------------------------------------- Windows job objects

_JOB_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JOB_EXTENDED_LIMIT_CLASS = 9
_JOB_BASIC_PROCESS_ID_LIST_CLASS = 3
_CREATE_SUSPENDED = 0x00000004


def _k32():
    """kernel32 with explicit 64-bit-safe prototypes for the job-object calls."""
    import ctypes
    from ctypes import wintypes

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k.SetInformationJobObject.restype = wintypes.BOOL
    k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k.AssignProcessToJobObject.restype = wintypes.BOOL
    k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k.TerminateJobObject.restype = wintypes.BOOL
    k.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    k.QueryInformationJobObject.restype = wintypes.BOOL
    k.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
    ]
    k.CloseHandle.restype = wintypes.BOOL
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    return k


def _create_kill_on_close_job() -> Optional[int]:
    """Create an unnamed Job Object with KILL_ON_JOB_CLOSE; return its handle or ``None``."""
    import ctypes
    from ctypes import wintypes

    class _Basic(ctypes.Structure):
        """ctypes layout of JOBOBJECT_BASIC_LIMIT_INFORMATION."""
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _Io(ctypes.Structure):
        """ctypes layout of IO_COUNTERS."""
        _fields_ = [(n, ctypes.c_uint64) for n in (
            "ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]

    class _Extended(ctypes.Structure):
        """ctypes layout of JOBOBJECT_EXTENDED_LIMIT_INFORMATION."""
        _fields_ = [
            ("Basic", _Basic), ("Io", _Io), ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    k = _k32()
    job = k.CreateJobObjectW(None, None)
    if not job:
        return None
    info = _Extended()
    info.Basic.LimitFlags = _JOB_LIMIT_KILL_ON_JOB_CLOSE
    if not k.SetInformationJobObject(job, _JOB_EXTENDED_LIMIT_CLASS, ctypes.byref(info), ctypes.sizeof(info)):
        k.CloseHandle(job)
        return None
    return int(job)


def _job_process_count(job: int) -> Optional[int]:
    """Number of processes still assigned to ``job`` (authoritative), or ``None`` on query failure."""
    import ctypes
    from ctypes import wintypes

    class _IdList(ctypes.Structure):
        """ctypes layout of JOBOBJECT_BASIC_PROCESS_ID_LIST with room for 16 ids."""
        _fields_ = [
            ("Assigned", wintypes.DWORD), ("InList", wintypes.DWORD),
            ("Ids", ctypes.c_size_t * 16),
        ]

    buf = _IdList()
    # ERROR_MORE_DATA (more than 16 members) still fills ``Assigned`` with the true count.
    ok = _k32().QueryInformationJobObject(
        job, _JOB_BASIC_PROCESS_ID_LIST_CLASS, ctypes.byref(buf), ctypes.sizeof(buf), None)
    if not ok and ctypes.get_last_error() != 234:
        return None
    return int(buf.Assigned)


def _job_terminate_and_count(job: int, grace: float) -> Optional[int]:
    """TerminateJobObject, wait up to ``grace`` s for the member list to empty; return survivors or ``None``."""
    _k32().TerminateJobObject(job, 1)
    deadline = time.monotonic() + max(grace, 0.5)
    while True:
        count = _job_process_count(job)
        if count is None or count == 0 or time.monotonic() >= deadline:
            return count
        time.sleep(0.05)


def _close_job_handle(job: int) -> None:
    """Close a job handle. KILL_ON_JOB_CLOSE means this also kills any surviving member (intended)."""
    try:
        _k32().CloseHandle(job)
    except Exception:  # noqa: BLE001 - finalizers must never raise
        pass


def _nt_resume_process(handle) -> int:
    """Call ntdll NtResumeProcess on a process handle; return the NTSTATUS (0 is success)."""
    import ctypes
    from ctypes import wintypes

    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    ntdll.NtResumeProcess.restype = ctypes.c_long
    return int(ntdll.NtResumeProcess(handle))


def _launch_suspended_in_job(argv: Sequence[str], **kwargs) -> "subprocess.Popen":
    """Windows: start ``argv`` suspended, assign it to a new kill-on-close job, then resume it.

    The child therefore runs its first instruction already inside the job, so
    every descendant started from it (including re-parented ones) is a job
    member. If only the job is unavailable (create or assign fails) the child
    is still resumed and runs without membership, so ``terminate_tree`` reports
    ``unknown``. Any other failure after the suspended start (an exception or a
    non-zero NTSTATUS from the resume) kills the child and raises
    ``LaunchError``: a suspended child is never left behind. The job handle is
    closed by a finalizer when the Popen is collected (see ``launch_tree``).
    """
    from ctypes import wintypes

    flags = int(kwargs.pop("creationflags", 0)) | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    proc = subprocess.Popen(list(argv), creationflags=flags | _CREATE_SUSPENDED, **kwargs)
    job: Optional[int] = None
    try:
        k = _k32()
        handle = wintypes.HANDLE(int(proc._handle))  # type: ignore[attr-defined]
        job = _create_kill_on_close_job()
        if job is not None and not k.AssignProcessToJobObject(job, handle):
            _close_job_handle(job)
            job = None
        status = _nt_resume_process(handle)
        if status != 0:
            raise LaunchError("NtResumeProcess failed with NTSTATUS 0x%08X" % (status & 0xFFFFFFFF))
    except BaseException as exc:
        if job is not None:
            _close_job_handle(job)
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            pass
        if isinstance(exc, LaunchError):
            raise
        raise LaunchError("could not start process inside a job: %s" % (exc,)) from exc
    proc._win_exec_job = job  # type: ignore[attr-defined]
    if job is not None:
        proc._win_exec_close = weakref.finalize(proc, _close_job_handle, job)  # type: ignore[attr-defined]
    return proc


def launch_tree(argv: Sequence[str], **kwargs) -> "subprocess.Popen":
    """``subprocess.Popen`` whose whole tree ``terminate_tree`` can contain authoritatively.

    Windows: suspended start, Job Object (KILL_ON_JOB_CLOSE) assignment, then
    NtResumeProcess, so no descendant can predate the job. POSIX: new session
    (the child leads its own process group). Other Popen kwargs pass through.
    """
    if _win():
        return _launch_suspended_in_job(argv, **kwargs)
    kwargs.setdefault("start_new_session", True)
    proc = subprocess.Popen(list(argv), **kwargs)
    if kwargs.get("start_new_session"):
        proc._win_exec_group = proc.pid  # type: ignore[attr-defined]
    return proc


# --------------------------------------------------------------------------- tree kill

def _system32(name: str) -> str:
    """Absolute path of a System32 tool, derived from %SystemRoot%."""
    root = os.environ.get("SystemRoot") or os.environ.get("SYSTEMROOT") or r"C:\Windows"
    return os.path.join(root, "System32", name)


def _taskkill(args: list[str]) -> None:
    """Run System32 ``taskkill.exe`` (absolute path) quietly; ignore launch failures."""
    try:
        subprocess.run([_system32("taskkill.exe"), *args], capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _terminate_tree_windows(proc: "subprocess.Popen", grace: float) -> str:
    """Windows tree kill with authoritative job membership, honest ``unknown`` without it.

    Launched via ``launch_tree``: TerminateJobObject, then report from the job's
    own process list (empty -> contained). A root that already exited is still
    contained by its job. Otherwise (no job): kill the root, still held open
    through its Popen handle so its PID cannot be reused, and report ``unknown``;
    no snapshot of parent links is ever trusted and no after-the-fact PID kill is issued.
    """
    job = getattr(proc, "_win_exec_job", None)
    if isinstance(job, int) and job:
        count = _job_terminate_and_count(job, grace)
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
        closer = getattr(proc, "_win_exec_close", None)
        if closer is not None:
            closer()  # idempotent finalizer: closes the handle exactly once
        else:
            _close_job_handle(job)
        proc._win_exec_job = None  # type: ignore[attr-defined]
        proc._win_exec_result = (  # type: ignore[attr-defined]
            UNKNOWN if count is None else CONTAINED if count == 0 else f"escaped:{count}")
        return proc._win_exec_result  # type: ignore[attr-defined]
    cached = getattr(proc, "_win_exec_result", None)
    if isinstance(cached, str) and cached:
        return cached
    if proc.poll() is None:
        _taskkill(["/F", "/T", "/PID", str(proc.pid)])  # root alive: handle held, PID is ours
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            return "escaped:1"
    return UNKNOWN


def _terminate_tree_posix(proc: "subprocess.Popen", grace: float) -> str:
    """POSIX tree kill via the child's own process group; verified by probing the group."""
    cached = getattr(proc, "_win_exec_result", None)
    if isinstance(cached, str) and cached:
        return cached
    pid = proc.pid
    sigkill = getattr(signal, "SIGKILL", 9)
    sigterm = getattr(signal, "SIGTERM", 15)
    if getattr(proc, "_win_exec_group", None) != pid:
        # Not started through launch_tree: membership is not authoritative.
        # A recycled PID could name an unrelated process group, so clean up
        # only the direct child and report unknown.
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            return "escaped:1"
        return UNKNOWN
    for sig in (sigterm, sigkill):
        try:
            os.killpg(pid, sig)
        except ProcessLookupError:
            break
        except PermissionError:
            return UNKNOWN
        try:
            proc.wait(timeout=grace if sig == sigterm else 2)
        except subprocess.TimeoutExpired:
            pass
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                proc._win_exec_result = CONTAINED  # type: ignore[attr-defined]
                return CONTAINED
            time.sleep(0.05)
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        proc._win_exec_result = CONTAINED  # type: ignore[attr-defined]
        return CONTAINED
    except PermissionError:
        return UNKNOWN
    proc._win_exec_result = "escaped:1"  # type: ignore[attr-defined]
    return "escaped:1"


def terminate_tree(proc: "subprocess.Popen", grace: float = 5.0) -> str:
    """Kill ``proc`` and everything in its job/group and return the containment result.

    Containment is job-scoped (CONTAINMENT_SCOPE_NOTE): ``contained`` means the
    job has no members left. It is NOT a guarantee against launchers outside the
    job - a process created through WMI (Win32_Process Create), DCOM, the Task
    Scheduler or a service is parented outside the job and survives while the
    status still reads ``contained``. Report the note with the status.

    ``contained`` only when the job (Windows) or process group (POSIX) is empty
    afterwards; ``escaped:<n>`` with ``n`` survivors; ``unknown`` when
    membership is not authoritative (Windows or POSIX: not started via
    ``launch_tree``) or the check failed. Never raises for an already-dead child.
    """
    if _win():
        return _terminate_tree_windows(proc, grace)
    return _terminate_tree_posix(proc, grace)
