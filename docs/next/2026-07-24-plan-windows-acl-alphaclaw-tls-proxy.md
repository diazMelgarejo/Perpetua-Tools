# Plan: Windows ACL Enforcement for alphaclaw_tls_proxy.py

**File:** `orchestrator/alphaclaw_tls_proxy.py`
**Scope:** Replace POSIX-only `chmod(0o600)` / `os.open(mode=0o600)` with cross-platform permission enforcement
**Platform:** Windows (primary target) — POSIX behavior preserved unchanged
**Priority:** Major | Security & Privacy
**Effort:** Heavy lift (single utility function + 5 call sites)
**Date:** 2026-07-24
**Status:** Minimal implementation DONE (2026-07-24) -- `_secure_path()` +
`_secure_path_win32()` + `_secure_path_icacls()` added, all 7 call sites
replaced, 8 unit tests added (mocked win32security), 17/17 tests in this
module green. **NOT yet verified on real Windows hardware** -- this was
implemented without a Windows machine available this session. Before
trusting this in production, run the §5.2 manual verification steps on
both the current RTX 3080 Windows machine and the incoming RTX 5080
replacement, and confirm `PROTECTED_DACL_SECURITY_INFORMATION` availability
per the provenance note below. Tracked in the companion scaffolding doc
[`2026-07-24-alphaclaw-tls-proxy-scaffolding.md`](2026-07-24-alphaclaw-tls-proxy-scaffolding.md).

## Provenance and verification note

This plan was adapted from an externally-authored draft. Before filing it
here, the draft's own §10 References already flagged that
`win32security.SetFileSecurity` (used in the draft's §4.1 code sample) is
documented by Microsoft as obsolete in favor of `SetNamedSecurityInfo` — the
draft cited the deprecation notice in its references but the code sample
itself still used the deprecated call. That contradiction is fixed below
(§4.1): the sample now calls `SetNamedSecurityInfo`, matching Microsoft's own
current guidance.

**What was independently re-verified for this filing (2026-07-24, EXA +
Firecrawl):**
- `win32security.SetFileSecurity()` deprecation: confirmed against
  [Microsoft's own API docs](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setfilesecuritya)
  — "This function is obsolete. Use the SetNamedSecurityInfo function instead."
- `SetNamedSecurityInfo` signature in pywin32: confirmed against
  [pywin32's own docs](https://mhammond.github.io/pywin32/win32security__SetNamedSecurityInfo_meth.html)
  — `SetNamedSecurityInfo(ObjectName, ObjectType, SecurityInfo, Owner, Group, Dacl, Sacl)`,
  cross-checked against a real usage example in
  [pywin32's own demo script](https://github.com/mhammond/pywin32/blob/master/win32/Demos/security/setnamedsecurityinfo.py).

**What is NOT independently verified and is flagged rather than asserted:**
the draft's §3.2 inheritance-disable requirement (`/inheritance:r` equivalent)
would map to setting `PROTECTED_DACL_SECURITY_INFORMATION` in the
`SecurityInfo` bitmask passed to `SetNamedSecurityInfo`. That flag exists in
the underlying Win32 `SECURITY_INFORMATION` bitmask (`winnt.h`), but pywin32's
own constant listing for `win32security` documents methods, not its exposed
integer constants, and this session had no Windows machine available to
`hasattr()`-check it directly. **Before merging implementation code from this
plan, verify on an actual Windows box:**
```python
import win32security
print(hasattr(win32security, "PROTECTED_DACL_SECURITY_INFORMATION"))
```
If absent, fall back to the numeric literal `0x80000000` (the flag's value in
`winnt.h`) with a comment citing this note, or drop automatic inheritance
disabling and rely on the DENY-before-ALLOW ACE ordering alone (still
correct, just leaves inherited ACEs from the parent in the DACL rather than
replacing them outright — acceptable since `CERT_DIR` is already restricted
first per §7.1).

---

## 1. Problem Statement

`alphaclaw_tls_proxy.py` currently enforces file permissions using POSIX mode bits exclusively:

| Location | Current Code | POSIX Effect | Windows Effect |
|----------|-------------|--------------|----------------|
| `_generate_cert()` line ~108 | `CERT_DIR.mkdir(mode=0o700)` | Owner rwx, nothing else | Mode ignored on Windows |
| `_generate_cert()` line ~109 | `CERT_DIR.chmod(0o700)` | Ensures 0o700 | Toggles read-only attr only |
| `_generate_cert()` line ~133 | `key_path.chmod(0o600)` | Owner rw, nothing else | Toggles read-only attr only |
| `_generate_cert()` line ~134 | `cert_path.chmod(0o600)` | Owner rw, nothing else | Toggles read-only attr only |
| `_generate_cert()` line ~131 | `os.open(key_path, ..., mode=0o600)` | Atomic restrictive create | Mode ignored; file gets inherited ACL |
| `_store_pinned_fingerprint()` | `store.parent.chmod(0o700)` | Ensures 0o700 | Read-only toggle only |
| `_store_pinned_fingerprint()` | `os.open(store, ..., mode=0o600)` | Atomic restrictive create | Mode ignored; file gets inherited ACL |

**On Windows**, `Path.chmod(0o600)` only toggles the read-only attribute — it does NOT restrict read access for other local users. The private key (`alphaclaw.key`), certificate (`alphaclaw.crt`), and fingerprint pin file (`fingerprint.json`) are protected only by the OS default ACL for the user's profile directory. This is a **known gap documented in the module docstring** but not mitigated.

### Windows Default ACL (typical user profile)

```
BUILTIN\Administrators:(I)(F)       ← Full control
NT AUTHORITY\SYSTEM:(I)(F)           ← Full control
NT AUTHORITY\Authenticated Users:(I)(M)  ← Modify (!)
BUILTIN\Users:(I)(RX)                ← Read + Execute (!)
```

Any process running as another user on the same machine (including other standard users, service accounts, or compromised processes) can **read the private key**.

---

## 2. Research Summary

### 2.1 Options Evaluated

| Approach | Dependency | Pros | Cons | Verdict |
|----------|-----------|------|------|---------|
| **pywin32** (`win32security`) | `pip install pywin32` | Clean Python API, no subprocess, full ACL control, well-documented, handles SIDs natively | Additional dependency; not in stdlib | **PRIMARY — recommended** |
| **icacls** (subprocess) | Built into Windows | No Python dependency, always available | Subprocess spawning, parsing output, race conditions, harder to test, error handling is opaque | **FALLBACK only** |
| **ctypes** (`Advapi32.dll`) | stdlib only | No external dependency | Complex — must define all Windows structures manually (SECURITY_DESCRIPTOR, ACL, ACE, SID), error-prone | **Rejected** — too complex for maintenance |
| **python-acl** (3rd party) | `pip install python-acl` | Cleaner than raw win32security | Unmaintained (last release 2015), not widely used | **Rejected** — unmaintained |
| **document gap only** | None | Zero code change | Security gap remains unmitigated; violates principle of least privilege | **Rejected** — security gap must be closed |

### 2.2 Why pywin32 as Primary

- **Already widely used** in Python Windows ecosystems (Django, Ansible, SaltStack all depend on it)
- **Same dependency** as `pypiwin32` which many Windows Python distributions include by default
- **Type-safe Python API** over raw Windows security descriptors — no manual struct packing
- **Handles SID resolution** (`LookupAccountName`) — no need to manually construct SIDs
- **Atomic operations** — a single call sets the whole DACL
- **Microsoft documentation parity** — `win32security` maps 1:1 to Windows SDK functions (this is why the plan uses `SetNamedSecurityInfo`, the SDK's own currently-recommended function, rather than the obsolete `SetFileSecurity`)

### 2.3 Why icacls as Fallback

- **Always available** on Windows (built-in since Windows Vista/Server 2003)
- **Zero Python dependency** — works even if pywin32 isn't installed
- **Sufficient for the task** — can set explicit grant/deny ACEs
- **Trade-off**: subprocess spawning introduces a small race window and complicates error handling

---

## 3. Target Permission Model

### 3.1 POSIX (unchanged)

```
Directories: 0o700  (rwx------)  — owner only
Files:       0o600  (rw-------)  — owner read/write only
```

### 3.2 Windows (new)

```
Explicit ACEs (in precedence order):
  1. DENY  Everyone              — FILE_ALL_ACCESS  (blocks all non-owner/admin access)
  2. ALLOW Current User          — FILE_ALL_ACCESS  (full control for owner)
  3. ALLOW BUILTIN\Administrators — FILE_ALL_ACCESS  (full control for admin recovery)

Inheritance: DISABLED where the pywin32 binding supports it — see the
verification note above; DENY-before-ALLOW ordering holds regardless.
```

**Rationale for Everyone DENY before owner ALLOW:**
Windows ACL evaluation order is: explicit deny → explicit allow → inherited deny → inherited allow. By placing `DENY Everyone` first, then `ALLOW owner`, we get the same semantics as POSIX `0o600`: only the owner (and admins) can access the file. Every other user/group is blocked regardless of any other group membership.

**Rationale for Administrators ALLOW:**
Administrators need access for disaster recovery (e.g., operator locked out, needs to rotate cert manually). This is standard practice for sensitive files on Windows and mirrors the POSIX model where root can always access any file.

---

## 4. Implementation Plan

### 4.1 New Utility Module: `_secure_path()`

A single cross-platform function that replaces all 7 `chmod`/`os.open(mode=)` call sites.

```python
# --- Platform detection and optional imports ---
import platform

_IS_WINDOWS = platform.system() == "Windows"

if _IS_WINDOWS:
    try:
        import win32security
        import win32api
        import ntsecuritycon as con
        _WIN32_AVAILABLE = True
    except ImportError:
        _WIN32_AVAILABLE = False
else:
    _WIN32_AVAILABLE = False


# --- Public API ---

def _secure_path(path: Path, is_directory: bool = False) -> None:
    """Enforce restrictive permissions on a sensitive path.

    POSIX (Linux/macOS): chmod 0o700 for directories, 0o600 for files.
    Windows (primary):   Explicit DACL — owner + admins only, deny everyone else.
    Windows (fallback):  icacls subprocess if pywin32 unavailable.

    This is a no-op on platforms where neither Windows nor POSIX permissions
    apply (theoretical — all supported platforms are covered).
    """
    if _IS_WINDOWS:
        if _WIN32_AVAILABLE:
            _secure_path_win32(path, is_directory)
        else:
            _secure_path_icacls(path, is_directory)
    else:
        # POSIX: use the existing mode-bit approach
        mode = 0o700 if is_directory else 0o600
        path.chmod(mode)


def _secure_path_win32(path: Path, is_directory: bool) -> None:
    """Windows ACL via pywin32: owner + admins full control, deny everyone.

    Uses SetNamedSecurityInfo rather than the deprecated SetFileSecurity --
    Microsoft's own API docs mark SetFileSecurity obsolete and direct
    callers to SetNamedSecurityInfo instead:
    https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setfilesecuritya
    """
    # Resolve SIDs for the three principals we need
    owner_sid, _, _ = win32security.LookupAccountName("", win32api.GetUserName())
    admins_sid, _, _ = win32security.LookupAccountName("", "Administrators")
    everyone_sid, _, _ = win32security.LookupAccountName("", "Everyone")

    # Build a new DACL from scratch (replaces inherited permissions)
    dacl = win32security.ACL()

    # 1. DENY Everyone first (explicit deny takes precedence over allows)
    access_mask = con.FILE_ALL_ACCESS if not is_directory else con.FILE_ALL_ACCESS | con.FILE_DELETE_CHILD
    dacl.AddAccessDeniedAce(win32security.ACL_REVISION, access_mask, everyone_sid)

    # 2. ALLOW owner full control
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, access_mask, owner_sid)

    # 3. ALLOW administrators full control (recovery access)
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, access_mask, admins_sid)

    # SecurityInfo bitmask: set only the DACL, leave owner/group/SACL alone.
    # PROTECTED_DACL_SECURITY_INFORMATION (if exposed by this pywin32 build)
    # additionally strips inherited ACEs instead of merging with them -- see
    # the "Provenance and verification note" above before relying on it.
    security_info = win32security.DACL_SECURITY_INFORMATION
    if hasattr(win32security, "PROTECTED_DACL_SECURITY_INFORMATION"):
        security_info |= win32security.PROTECTED_DACL_SECURITY_INFORMATION

    win32security.SetNamedSecurityInfo(
        str(path),
        win32security.SE_FILE_OBJECT,
        security_info,
        None,  # owner: leave unchanged
        None,  # group: leave unchanged
        dacl,
        None,  # sacl: leave unchanged
    )


def _secure_path_icacls(path: Path, is_directory: bool) -> None:
    """Windows ACL fallback via icacls subprocess.

    Less elegant than pywin32 but works without any external dependency.
    The subprocess race window is acceptable here because the parent
    directory (CERT_DIR) is already restricted, limiting the exposure.
    """
    import subprocess
    import getpass

    user = getpass.getuser()
    target = str(path)

    # Build icacls command:
    #   /inheritance:r  — remove all inherited permissions
    #   /grant:r        — replace (not append) explicit permissions
    #   /deny           — add explicit deny ACE
    cmd = [
        "icacls", target,
        "/inheritance:r",
        "/grant:r", f"{user}:(F)",           # Full control for owner
        "/grant:r", "Administrators:(F)",     # Full control for admins
        "/deny", "Everyone:(F)",              # Deny everyone else
    ]

    if is_directory:
        # (OI)(CI) — Object Inherit + Container Inherit so child files/dirs
        # get the same restrictions automatically
        cmd[4] = f"{user}:(OI)(CI)(F)"
        cmd[6] = "Administrators:(OI)(CI)(F)"
        cmd[8] = "Everyone:(OI)(CI)(F)"

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        _log.warning(
            "icacls failed to restrict permissions on %s: %s",
            target, result.stderr.strip()
        )
```

### 4.2 Call Site Replacements (7 locations)

#### Location 1: `CERT_DIR` setup in `_generate_cert()` (~line 108)

**Before:**
```python
CERT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
CERT_DIR.chmod(0o700)  # covers directories that predate this permissions fix
```

**After:**
```python
CERT_DIR.mkdir(parents=True, exist_ok=True)
_secure_path(CERT_DIR, is_directory=True)  # 0o700 on POSIX, ACL on Windows
```

#### Location 2: Existing key/cert chmod in `_generate_cert()` (~line 133)

**Before:**
```python
key_path.chmod(0o600)
cert_path.chmod(0o600)
```

**After:**
```python
_secure_path(key_path, is_directory=False)
_secure_path(cert_path, is_directory=False)
```

#### Location 3: Atomic key creation in `_generate_cert()` (~line 131)

**Before:**
```python
fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "wb") as f:
    f.write(key_bytes)
```

**After:**
```python
# Create file (no mode on Windows — os.open mode is POSIX-only),
# then immediately apply restrictive ACL.
fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
try:
    with os.fdopen(fd, "wb") as f:
        f.write(key_bytes)
finally:
    _secure_path(key_path, is_directory=False)
```

#### Location 4: `store.parent` (CERT_DIR) in `_store_pinned_fingerprint()`

**Before:**
```python
store.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
store.parent.chmod(0o700)
```

**After:**
```python
store.parent.mkdir(parents=True, exist_ok=True)
_secure_path(store.parent, is_directory=True)
```

#### Location 5: Atomic fingerprint store creation in `_store_pinned_fingerprint()`

**Before:**
```python
fd = os.open(str(store), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "wb") as f:
    f.write(payload)
```

**After:**
```python
fd = os.open(str(store), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
try:
    with os.fdopen(fd, "wb") as f:
        f.write(payload)
finally:
    _secure_path(store, is_directory=False)
```

### 4.3 Summary of Changes

| Call Site | File/Dir | Old | New |
|-----------|----------|-----|-----|
| `_generate_cert()` | `CERT_DIR` | `mkdir(mode=0o700)` + `chmod(0o700)` | `mkdir()` + `_secure_path(CERT_DIR, is_directory=True)` |
| `_generate_cert()` | `key_path` | `os.open(..., mode=0o600)` | `os.open(...)` + `_secure_path(key_path)` |
| `_generate_cert()` | `key_path` | `chmod(0o600)` | `_secure_path(key_path)` |
| `_generate_cert()` | `cert_path` | `chmod(0o600)` | `_secure_path(cert_path)` |
| `_store_pinned_fingerprint()` | `store.parent` | `mkdir(mode=0o700)` + `chmod(0o700)` | `mkdir()` + `_secure_path(store.parent, is_directory=True)` |
| `_store_pinned_fingerprint()` | `store` (fingerprint.json) | `os.open(..., mode=0o600)` | `os.open(...)` + `_secure_path(store)` |

**Total: 1 new function + 2 helpers (~65 lines) + 7 call site edits.**

---

## 5. Testing Strategy

### 5.1 Unit Tests (platform-agnostic)

```python
# tests/test_alphaclaw_tls_proxy_permissions.py

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock win32security for non-Windows test environments
@pytest.fixture
def mock_win32():
    """Provide a mock win32security module for testing Windows ACL logic
    on non-Windows platforms."""
    mock_con = MagicMock()
    mock_con.FILE_ALL_ACCESS = 0x1F01FF
    mock_con.FILE_DELETE_CHILD = 0x0040

    mock_win32 = MagicMock()
    mock_win32.ACL_REVISION = 2
    mock_win32.DACL_SECURITY_INFORMATION = 0x4
    mock_win32.SE_FILE_OBJECT = 1
    mock_win32.LookupAccountName = MagicMock(side_effect=lambda _, name: (
        f"SID-{name}", "DOMAIN", 1  # (sid, domain, type)
    ))
    mock_win32.SetNamedSecurityInfo = MagicMock()

    mock_acl = MagicMock()
    mock_win32.ACL = MagicMock(return_value=mock_acl)

    modules = {
        'win32security': mock_win32,
        'win32api': MagicMock(GetUserName=MagicMock(return_value="testuser")),
        'ntsecuritycon': mock_con,
    }
    with patch.dict('sys.modules', modules):
        yield mock_win32, mock_acl


def test_secure_path_win32_creates_dacl_with_three_aces(mock_win32):
    """Verify the Windows ACL path creates exactly 3 ACEs:
    DENY Everyone, ALLOW owner, ALLOW administrators."""
    from alphaclaw_tls_proxy import _secure_path_win32

    mock_sec, mock_acl = mock_win32
    test_path = Path("C:/test/key.pem")

    _secure_path_win32(test_path, is_directory=False)

    # Should have called AddAccessDeniedAce once (Everyone)
    assert mock_acl.AddAccessDeniedAce.call_count == 1
    # Should have called AddAccessAllowedAce twice (owner + admins)
    assert mock_acl.AddAccessAllowedAce.call_count == 2
    # Should have set the DACL via SetNamedSecurityInfo (not the
    # deprecated SetFileSecurity)
    mock_sec.SetNamedSecurityInfo.assert_called_once()


def test_secure_path_posix_sets_correct_mode(tmp_path):
    """Verify POSIX path sets 0o600 for files, 0o700 for dirs."""
    from alphaclaw_tls_proxy import _secure_path

    test_file = tmp_path / "key.pem"
    test_file.write_text("test key")

    with patch('alphaclaw_tls_proxy._IS_WINDOWS', False):
        _secure_path(test_file, is_directory=False)

    mode = test_file.stat().st_mode & 0o777
    assert mode == 0o600, f"Expected 0o600, got 0o{mode:o}"
```

### 5.2 Integration Tests (Windows-only)

```powershell
# Run on a Windows machine or CI runner with pywin32 installed
# Verify that after _secure_path(), a different local user cannot read the file

# Manual verification steps:
1. Run alphaclaw_tls_proxy to generate cert + key
2. Open PowerShell as a different user
3. Try: Get-Content $env:USERPROFILE\.openclaw\alphaclaw_tls\alphaclaw.key
4. EXPECTED: Access denied
5. Try: Get-Content $env:USERPROFILE\.openclaw\alphaclaw_tls\fingerprint.json
6. EXPECTED: Access denied
7. Verify owner CAN read: run as original user, confirm file content accessible
8. Confirm hasattr(win32security, "PROTECTED_DACL_SECURITY_INFORMATION")
   on the actual target pywin32 build (see provenance note above) and
   record the result in this doc before relying on inheritance-stripping.
```

### 5.3 CI Matrix

| Runner | pywin32 | Test |
|--------|---------|------|
| ubuntu-latest | N/A | `_secure_path` sets 0o600/0o700 |
| macos-latest | N/A | `_secure_path` sets 0o600/0o700 |
| windows-latest | installed | `_secure_path` sets restrictive DACL via SetNamedSecurityInfo (mocked) |
| windows-latest | NOT installed | Falls back to icacls, logs warning |

---

## 6. Dependency Impact

### 6.1 pywin32 (optional, Windows-only)

```
# pyproject.toml / setup.py addition:
[project.optional-dependencies]
windows-security = ["pywin32>=227"]
```

- **Not a hard dependency** — the code works without it (falls back to icacls)
- **Recommended** for production Windows deployments — icacls subprocess is less reliable
- **Already common** in Python Windows environments (many tools pull it in transitively)

### 6.2 icacls (built-in, Windows-only fallback)

- Always available on Windows Vista+ / Server 2003+
- No pip install needed
- subprocess spawning is acceptable for this use case (setup-time, not hot-path)

---

## 7. Security Considerations

### 7.1 TOCTOU on Windows File Creation

**Issue:** `os.open(path, O_CREAT)` on Windows creates the file with inherited ACLs from the parent directory. There is a brief window before `_secure_path()` runs where the file is readable by other users.

**Mitigation:**
- `CERT_DIR` is restricted first (`_secure_path(CERT_DIR, is_directory=True)`) before any file creation
- Files created inside a restricted directory inherit restrictive ACLs automatically
- The explicit `_secure_path(file)` call is a **defense-in-depth** layer, not the primary protection
- The actual window is microseconds (creation → `fdopen` → write → close → `_secure_path`) and requires an attacker process actively scanning the directory

### 7.2 icacls Fallback Race Condition

**Issue:** icacls runs as a subprocess. Between file creation and icacls completion, the file has inherited (permissive) ACLs.

**Mitigation:**
- Same as above — parent directory restriction is the primary protection
- icacls fallback is for environments where pywin32 can't be installed (development, minimal systems)
- Log warning when icacls fallback is used so operators are aware

### 7.3 Administrators Access

**Design decision:** Administrators get full control on all sensitive files.

**Rationale:**
- Standard Windows practice for sensitive user data
- Required for disaster recovery (operator lockout, cert rotation)
- Same as POSIX where root can access any file
- The threat model is **other standard users on the same machine**, not admin compromise (admin compromise = game over regardless)

---

## 8. Migration Plan

| Step | Action | Effort | Risk |
|------|--------|--------|------|
| 1 | Add `_secure_path()`, `_secure_path_win32()`, `_secure_path_icacls()` to `alphaclaw_tls_proxy.py` | 1 hr | **DONE** (2026-07-24) |
| 2 | Replace 7 call sites (chmod → _secure_path, os.open mode → post-creation _secure_path) | 30 min | **DONE** (2026-07-24) |
| 3 | Update module docstring — remove "Platform limitation" paragraph | 5 min | **DONE** (2026-07-24) |
| 4 | Add unit tests with mock_win32 fixture | 45 min | **DONE** (2026-07-24) — 8 tests, `tests/test_alphaclaw_tls_proxy_permissions.py` |
| 5 | On a real Windows box: verify `hasattr(win32security, "PROTECTED_DACL_SECURITY_INFORMATION")` and record the result in this doc | 10 min | **PENDING** — needs the actual RTX 3080 Windows machine (or its incoming RTX 5080 replacement); no Windows hardware available this session |
| 6 | Run CI on PR (ubuntu + macos + windows matrix) | 15 min | **PENDING** — not yet opened as a PR |
| 7 | Manual verification on Windows: verify other-user access denied | 20 min | **PENDING** — needs real Windows hardware (RTX 3080 now, RTX 5080 soon); this is the actual functional proof, not just unit tests against a mock |
| 8 | Update companion doc `docs/next/2026-07-24-alphaclaw-tls-proxy-scaffolding.md`'s "explicitly NOT done yet" list | 5 min | **DONE** (2026-07-24) |

**Total effort: ~3 hours**
**Risk: Low** — all changes are additive (new function + call site replacements). No existing behavior changes on POSIX. On Windows, permissions become more restrictive (strictly safer).

---

## 9. Open Questions

1. **Should pywin32 be a hard dependency on Windows?** Currently it's optional (falls back to icacls). Making it required would eliminate the subprocess fallback but adds a pip-install step for Windows users. Leaning toward including it in the Windows install script (`install.ps1`) so the primary path is available by default, while keeping icacls as a genuine fallback rather than the expected path.
2. **Should the icacls fallback also restrict `BUILTIN\Users` and `Authenticated Users` explicitly?** The current plan uses `DENY Everyone`, which catches all non-owner/admin access. Sufficient for the threat model in §7.3; explicit per-group denies add complexity without closing a real gap here.
3. **Should we also restrict NTFS alternate data streams?** Windows files can have alternate data streams (ADS) that don't inherit the main file's ACL in all cases. The private key content itself isn't written to an ADS by this code, so this is a theoretical hardening item, not a gap this plan needs to close — noted for completeness, not scoped in.

---

## 10. References

- [Microsoft: SetFileSecurity function (deprecated, use SetNamedSecurityInfo)](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setfilesecuritya) — re-verified 2026-07-24
- [pywin32: SetNamedSecurityInfo](https://mhammond.github.io/pywin32/win32security__SetNamedSecurityInfo_meth.html) — re-verified 2026-07-24, signature matches this plan's §4.1
- [pywin32 demo: setnamedsecurityinfo.py](https://github.com/mhammond/pywin32/blob/master/win32/Demos/security/setnamedsecurityinfo.py) — re-verified 2026-07-24, real usage example
- [Tim Golden: Add security to a file (pywin32)](https://timgolden.me.uk/python/win32_how_do_i/add-security-to-a-file.html)
- [Microsoft: icacls documentation](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls)
- [Python issue #42046: POSIX permissions on Windows](https://bugs.python.org/issue42046)
- [Windows permissions cheat-sheet](https://anadoxin.org/blog/windows-permissions-cheat-sheet/)
