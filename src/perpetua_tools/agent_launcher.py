#!/usr/bin/env python3
"""
agent_launcher.py
-----------------
Hardware-aware agent launcher for the Perpetua-Tools orchestration stack.

Detects whether the remote Windows worker (Dell RTX 3080) is reachable and
routes the coder/heavy-reasoning role accordingly. Falls back gracefully to
Mac-only mode if the Windows node is offline.

Usage:
    python agent_launcher.py              # auto-detect with defaults
    python agent_launcher.py --configure  # interactive IP / hardware setup

References:
    hardware/SKILL.md     - hardware profiles and role matrix
    hardware/Modelfile.*  - Ollama model definitions
    config/routing.yml    - routing rules that consume the endpoints returned here
"""
from __future__ import annotations  # PEP 563: postpone annotation eval (Python 3.9 compat)

import os
import logging
import sys
import json
import asyncio
import argparse
import ipaddress
import socket
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

from utils.hardware_policy import HardwareAffinityError, check_affinity
from orchestrator.backend_resolver import resolve_backend_for_spec
from orchestrator.startup_intelligence import (
    StartupScenario,
    classify_scenario,
    build_routing_hints,
    FleetMode,
    classify_fleet_mode,
)
from perpetua.discovery.backend import Backend, BackendHealth, BackendKind
from perpetua.discovery.registry import BackendRegistry

_platform_override = os.getenv("ORAMA_PLATFORM", "").strip().lower()
RUNNING_ON_WINDOWS = _platform_override in {"win", "windows", "win32"} or (
    not _platform_override and sys.platform.startswith("win")
)
RUNNING_ON_MAC = _platform_override in {"mac", "macos", "darwin"} or (
    not _platform_override and sys.platform == "darwin"
)

try:
    import httpx
except ImportError:
    print("[agent_launcher] ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

# Load .env files so vars are available whether called from start.sh or directly.
# .env.local overrides .env (machine-local settings take precedence).
try:
    from dotenv import load_dotenv as _load_dotenv
    _repo_root = Path(__file__).resolve().parents[2]
    _load_dotenv(_repo_root / ".env",       override=False)
    _load_dotenv(_repo_root / ".env.local", override=True)
except ImportError:
    pass  # python-dotenv not installed — rely on shell env vars


# ---------------------------------------------------------------------------
# Default hardware endpoints (from hardware/SKILL.md profiles)
# Override via environment variables or --configure flag
#
# Priority for each endpoint (highest → lowest):
#   1. Machine-local .env.local  (e.g. MAC_LMS_HOST, WINDOWS_IP)
#   2. Shared .env               (LM_STUDIO_MAC_ENDPOINT, LM_STUDIO_WIN_ENDPOINTS)
#   3. Shell environment vars    (exported by start.sh from network_autoconfig)
#   4. Hard-coded LAN defaults   (.110 = Mac LM Studio, .108 = Windows)
# ---------------------------------------------------------------------------

def _is_loopback_host(host: str) -> bool:
    if host in ("localhost", "::1"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _safe_port(parsed, default: int) -> int:
    """Read ParseResult.port, falling back to *default* on malformed/out-of-range ports.

    ``ParseResult.port`` raises ``ValueError`` lazily on access (not at
    ``urlparse()`` time) for non-numeric or out-of-range ports — guard every
    access so a bad env var never escapes as a bare ValueError.
    """
    try:
        return parsed.port or default
    except ValueError:
        return default


def _loopback_host_from_endpoint(endpoint: str, *, default_port: int) -> tuple[str, int]:
    """Resolve host/port from a URL; never use LOCAL_MAC_HOST (avoids secret-scan collisions)."""
    endpoint = endpoint.strip()
    if "://" in endpoint:
        parsed = urlparse(endpoint)
        host = (parsed.hostname or "localhost").strip()
        port = _safe_port(parsed, default_port)
    else:
        host, _, port_part = endpoint.partition(":")
        host = host.strip() or "localhost"
        port = int(port_part) if port_part else default_port
    if _is_loopback_host(host):
        host = "localhost"
    return host, port


_default_mac_host = os.getenv("MAC_IP") or os.getenv("MAC_LMS_HOST") or ""
_default_ollama_mac_endpoint = (
    "http://localhost:11434"
    if RUNNING_ON_MAC
    else f"http://{_default_mac_host}:11434"
)
_ollama_mac_endpoint = os.getenv("OLLAMA_MAC_ENDPOINT", _default_ollama_mac_endpoint)
# PT runs ON the Mac, so its own ("mac") ollama is always loopback. A stale LAN
# IP from a previous subnet (e.g. 127.0.3.1) is never correct here — it only
# breaks Mac-orchestrator selection (mac_ollama_ok=False -> manager falls off
# ollama-localhost). Normalize any non-loopback mac endpoint to localhost, the
# canonical value. Mirrors the Win endpoint's "live/canonical source beats stale
# config" self-heal in lan_discovery.detect_active_tilting_ip.
_p_mac = urlparse(_ollama_mac_endpoint if "://" in _ollama_mac_endpoint else f"http://{_ollama_mac_endpoint}")
if RUNNING_ON_MAC and _p_mac.hostname and not _is_loopback_host(_p_mac.hostname):
    _healed_mac = f"http://localhost:{_safe_port(_p_mac, 11434)}"
    logging.getLogger(__name__).warning(
        "OLLAMA_MAC_ENDPOINT=%s is non-loopback; PT runs on the Mac so its ollama "
        "is localhost — normalizing to %s", _ollama_mac_endpoint, _healed_mac
    )
    _ollama_mac_endpoint = _healed_mac
LOCAL_MAC_HOST, LOCAL_MAC_PORT = _loopback_host_from_endpoint(_ollama_mac_endpoint, default_port=11434)
LOCAL_MAC_URL = _ollama_mac_endpoint if "://" in _ollama_mac_endpoint else f"http://{LOCAL_MAC_HOST}:{LOCAL_MAC_PORT}"
MAC_MANAGER_MODEL = os.getenv("MAC_MANAGER_MODEL", "glm-5.1:cloud")

# Mac LM Studio — locality-aware default (mirrors Ollama block above).
_default_mac_lms_endpoint = (
    "http://localhost:1234"
    if RUNNING_ON_MAC
    else f"http://{_default_mac_host}:1234"
)
_mac_lms_endpoint = os.getenv("LM_STUDIO_MAC_ENDPOINT", _default_mac_lms_endpoint)
_p_mac_lms = urlparse(
    _mac_lms_endpoint if "://" in _mac_lms_endpoint else f"http://{_mac_lms_endpoint}"
)
if RUNNING_ON_MAC and _p_mac_lms.hostname not in ("localhost", "127.0.0.1", "::1", None):
    _healed_mac_lms = f"http://localhost:{_safe_port(_p_mac_lms, 1234)}"
    logging.getLogger(__name__).warning(
        "LM_STUDIO_MAC_ENDPOINT=%s is non-loopback; PT runs on the Mac so Mac LM Studio "
        "is localhost — normalizing to %s",
        _mac_lms_endpoint,
        _healed_mac_lms,
    )
    _mac_lms_endpoint = _healed_mac_lms
    _p_mac_lms = urlparse(_healed_mac_lms)
_mac_lms_host = os.getenv(
    "MAC_LMS_HOST",
    _p_mac_lms.hostname or ("localhost" if RUNNING_ON_MAC else _default_mac_host),
)
if RUNNING_ON_MAC and not _is_loopback_host(_mac_lms_host):
    logging.getLogger(__name__).warning(
        "MAC_LMS_HOST=%s is non-loopback; PT runs on the Mac so Mac LM Studio "
        "is localhost — normalizing to localhost",
        _mac_lms_host,
    )
    _mac_lms_host = "localhost"
MAC_LMS_HOST = _mac_lms_host
MAC_LMS_PORT = int(os.getenv("MAC_LMS_PORT", str(_safe_port(_p_mac_lms, 1234))))
MAC_LMS_URL = f"http://{MAC_LMS_HOST}:{MAC_LMS_PORT}"
MAC_LMS_MODEL = (os.getenv("MAC_LMS_MODEL")
                 or os.getenv("LMS_MAC_MODEL")
                 or "Qwen3.5-9B-MLX-4bit")
MAC_REQUIRED_OLLAMA_MODELS = tuple(
    m.strip()
    for m in os.getenv("MAC_REQUIRED_OLLAMA_MODELS", "qwen3.5:9b-nvfp4,bge-m3").split(",")
    if m.strip()
)


def _served_model_present(served: list[str], required: str) -> bool:
    required_l = required.lower()
    for model in served:
        model_l = str(model).lower()
        if model_l == required_l or model_l.startswith(required_l + ":"):
            return True
    return False


def _ensure_mac_ollama_models_present(served: list[str], base_url: str = LOCAL_MAC_URL) -> None:
    """Fail closed unless the Mac host has localhost:11434 with required models."""
    if not RUNNING_ON_MAC:
        return
    parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    host = parsed.hostname or ""
    port = _safe_port(parsed, 11434)
    if not _is_loopback_host(host) or port != 11434:
        raise RuntimeError(
            f"Mac Ollama must be localhost:11434 before manager selection; got {base_url}"
        )
    missing = [
        model
        for model in MAC_REQUIRED_OLLAMA_MODELS
        if not _served_model_present(served, model)
    ]
    if missing:
        _launcher_logger.critical(
            "Mac Ollama is missing required manager/support model(s): %s",
            ", ".join(missing),
        )
        raise RuntimeError(
            "Mac Ollama missing required model(s): " + ", ".join(missing)
        )


def _pick_mac_manager(served: list, preferred: str) -> str:
    """Choose the Mac orchestrator/manager model with the correct priority.

    Priority order:
      1. the configured Mac orchestrator model (`preferred`) when it is actually
         served — keeps Mac ollama-localhost as the highest-priority orchestrator
         whenever it's online (rather than grabbing the first raw tag, which may
         be an embedding model like bge-m3);
      2. the first served Mac-affine model;
      3. the configured default (affinity-checked).
    Never returns a NEVER_MAC model (a Win-only coder that leaked into a mac
    bucket via LAN discovery) — that would fail the hardware-affinity gate.
    """
    if preferred:
        for m in served:
            if _served_model_present([m], preferred):
                try:
                    check_affinity(m, "mac")
                    return m
                except HardwareAffinityError:
                    logging.getLogger(__name__).warning(
                        "skipping preferred NEVER_MAC model %r for the Mac manager role",
                        m,
                    )
    for m in served:
        try:
            check_affinity(m, "mac")
            return m
        except HardwareAffinityError:
            logging.getLogger(__name__).warning(
                "skipping NEVER_MAC model %r for the Mac manager role", m
            )
            continue
    if preferred:
        check_affinity(preferred, "mac")
        return preferred
    raise HardwareAffinityError("No Mac-affine manager model available")

# Windows — WINDOWS_IP exported by start.sh; if absent parse LM_STUDIO_WIN_ENDPOINTS
# (first entry), then fall back to hard-coded LAN default.
_win_lms_eps = os.getenv("LM_STUDIO_WIN_ENDPOINTS", "").strip()
_win_lms_first = _win_lms_eps.split(",")[0].strip() if _win_lms_eps else ""
if not os.getenv("WINDOWS_IP") and _win_lms_first:
    _pw = urlparse(_win_lms_first)
    # No fabricated cross-machine default: an unset WINDOWS_IP with no
    # discovered LM Studio hostname must fail closed (empty host breaks any
    # constructed URL immediately and obviously) rather than silently
    # resolving to 192.0.2.4 — a TEST-NET-1 documentation address that looks
    # plausible but never routes anywhere, turning a config gap into a
    # confusing hang/timeout instead of a clear connection error.
    _win_ip_default = _pw.hostname or ("localhost" if RUNNING_ON_WINDOWS else "")
else:
    _win_ip_default = "localhost" if RUNNING_ON_WINDOWS else ""

_windows_ip = os.getenv("WINDOWS_IP", _win_ip_default)
if RUNNING_ON_WINDOWS and not _is_loopback_host(_windows_ip):
    logging.getLogger(__name__).warning(
        "WINDOWS_IP=%s is non-loopback; PT runs on Windows so local services "
        "are localhost — normalizing to localhost",
        _windows_ip,
    )
    _windows_ip = "localhost"
WINDOWS_IP        = _windows_ip
WINDOWS_PORT      = int(os.getenv("WINDOWS_PORT", "11434"))
REMOTE_WINDOWS_URL   = f"http://{WINDOWS_IP}:{WINDOWS_PORT}"
WINDOWS_CODER_MODEL  = os.getenv(
    "WINDOWS_CODER_MODEL",
    "qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2",  # exact LM Studio model id
)


def resolve_local_or_remote(
    target_role: str,
    port: int,
    *,
    env_var: str = "",
    fallback_ip: str = "",
) -> str:
    """Return the correct endpoint for *target_role* based on where this process runs.

    Locality rule (user decision 2026-06-24):
      • If this process runs ON the target machine → always use localhost.
      • If this process runs on a DIFFERENT machine → use the parametrized LAN IP.

    This eliminates the twin failure modes:
      (a) stale LAN IP configured when code runs locally (slow / broken routing)
      (b) hardcoded IP in source that drifts as DHCP changes

    Args:
        target_role: ``"mac"`` or ``"windows"`` (case-insensitive)
        port:        service port (e.g. 1234 for LM Studio, 11434 for Ollama)
        env_var:     optional full-URL env var that overrides everything
                     (e.g. ``"LM_STUDIO_WIN_ENDPOINTS"``)
        fallback_ip: LAN IP fallback when running on the other machine.
                     Should be sourced from env (e.g. WIN_IP / MAC_IP), never
                     a bare literal in caller code.

    Returns:
        ``"http://localhost:{port}"`` when on the target machine,
        ``"http://{fallback_ip}:{port}"`` when on the other machine.
    """
    role = target_role.lower().strip()
    is_local = (
        (role in {"mac", "macos", "darwin"} and RUNNING_ON_MAC)
        or (role in {"win", "windows", "win32"} and RUNNING_ON_WINDOWS)
    )
    if env_var:
        override = os.getenv(env_var, "").strip().split(",")[0].strip()
        if override:
            if is_local:
                parsed = urlparse(override if "://" in override else f"http://{override}")
                if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
                    _launcher_logger.warning(
                        "resolve_local_or_remote: %s=%s is non-loopback but we run ON "
                        "the %s machine — normalizing to localhost", env_var, override, role
                    )
                    return f"http://localhost:{_safe_port(parsed, port)}"
            return override if "://" in override else f"http://{override}"
    if is_local:
        return f"http://localhost:{port}"
    ip = fallback_ip or "127.0.0.1"
    return f"http://{ip}:{port}"

# ---------------------------------------------------------------------------
# Startup assertion — validate hardware policy on module load
# ---------------------------------------------------------------------------

_launcher_logger = logging.getLogger(__name__)


def _validate_hardware_policy(resolved_model: str) -> None:
    """Raise HardwareAffinityError if resolved_model is not valid for Windows execution."""
    try:
        from utils.hardware_policy import load_policy
        policy = load_policy()
        valid_for_windows = {
            m.lower()
            for m in (policy.get("windows_only", []) or []) + (policy.get("shared", []) or [])
        }
        if valid_for_windows and resolved_model.lower() not in valid_for_windows:
            _launcher_logger.critical(
                "Hardware Policy Violation: Resolved model '%s' is not validated "
                "for Windows execution. Halting orchestration.",
                resolved_model,
            )
            raise HardwareAffinityError(f"Invalid model affinity: {resolved_model}")
    except HardwareAffinityError:
        raise
    except Exception as _e:
        _launcher_logger.warning("Hardware policy startup validation skipped: %s", _e)


_validate_hardware_policy(WINDOWS_CODER_MODEL)

WINDOWS_LMS_PORT      = int(os.getenv("WINDOWS_LMS_PORT", "1234"))
REMOTE_WINDOWS_LMS_URL = f"http://{WINDOWS_IP}:{WINDOWS_LMS_PORT}"
LMS_API_TOKEN         = os.getenv("LM_STUDIO_API_TOKEN", "")
WINDOWS_LMS_MODEL     = (os.getenv("WINDOWS_LMS_MODEL")
                         or os.getenv("LMS_WIN_MODEL")
                         or "qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2")

# Timeout in seconds — short to avoid blocking the launcher when Windows is asleep
DETECT_TIMEOUT = int(os.getenv("AGENT_DETECT_TIMEOUT", "3"))

# State file for routing state (separate from AgentTracker's agents.json)
STATE_FILE = Path(".state/routing.json")

# Startup history — records probe results per run so future runs adapt
HISTORY_FILE  = Path(".state/startup_history.jsonl")
HISTORY_MAX   = 10  # keep last N runs


# ---------------------------------------------------------------------------
# Startup history helpers — experience as a tool
# ---------------------------------------------------------------------------

def _load_history() -> list[dict]:
    """Read the last HISTORY_MAX entries from startup_history.jsonl.

    Returns an empty list if the file is missing or unreadable.
    """
    if not HISTORY_FILE.exists():
        return []
    try:
        lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
        entries = []
        for line in lines:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries[-HISTORY_MAX:]
    except OSError:
        return []


def _record_startup(scenario: StartupScenario, latencies: dict[str, int | None]) -> None:
    """Append one startup record to startup_history.jsonl.

    Args:
        scenario: The classified scenario for this run.
        latencies: Dict with optional keys win_lms_latency_ms, mac_ol_latency_ms.

    Trims the file to HISTORY_MAX lines after writing.
    Non-fatal on any I/O error.
    """
    record: dict = {
        "ts": int(time.time()),
        "scenario": scenario.value,
        "win_ip": WINDOWS_IP,
        **{k: v for k, v in latencies.items() if v is not None},
    }
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        # Trim to last HISTORY_MAX lines
        lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
        if len(lines) > HISTORY_MAX:
            HISTORY_FILE.write_text("".join(lines[-HISTORY_MAX:]), encoding="utf-8")
    except OSError as exc:
        print(f"[agent_launcher] ⚠  could not write startup history: {exc}")


# ---------------------------------------------------------------------------
# Device identity — detect when two URLs point to the same physical machine
# ---------------------------------------------------------------------------

def _get_local_ips() -> frozenset[str]:
    """Return all IPv4 addresses that belong to this machine.

    Uses three strategies (all non-blocking):
    1. Resolve the machine's hostname.
    2. UDP routing trick — open a socket toward a routable IP; the OS fills in
       the outbound LAN IP without actually sending any packets.
    3. Always include the loopback aliases.
    """
    local: set[str] = {"localhost"}
    try:
        local.add(socket.gethostbyname(socket.gethostname()))
    except OSError:
        pass
    for probe in ("8.8.8.8", "1.1.1.1"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.2)
                s.connect((probe, 80))
                local.add(s.getsockname()[0])
                break
        except OSError:
            pass
    return frozenset(local)


def _host_of(url: str) -> str:
    """Extract hostname from a URL, normalising loopback aliases to 127.0.0.1."""
    h = urlparse(url).hostname or url
    return "localhost" if _is_loopback_host(h) else h


def _is_local_endpoint(url: str, local_ips: frozenset[str]) -> bool:
    """Return True if *url* points to this machine."""
    return _host_of(url) in local_ips


# ---------------------------------------------------------------------------
# Helper: check if a remote Ollama instance is reachable
# ---------------------------------------------------------------------------

async def check_remote_worker(
    base_url: str,
    timeout: int = DETECT_TIMEOUT,
    _retries: int = 1,
) -> tuple[bool, int | None]:
    """Return (reachable, latency_ms) for the Ollama instance at base_url.

    Retries once (2 s gap) when the first attempt fails with a connection
    error — catches backends that are mid-boot. Returns (False, None) if all
    attempts fail.
    """
    for attempt in range(_retries + 1):
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(f"{base_url}/api/tags")
                if resp.status_code == 200:
                    latency = int((time.monotonic() - t0) * 1000)
                    return True, latency
        except Exception:
            pass
        if attempt < _retries:
            print(f"[agent_launcher]   ↻  retrying {base_url} (attempt {attempt + 2}/{_retries + 1})…")
            await asyncio.sleep(2)
    return False, None


async def check_lmstudio_worker(
    base_url: str,
    timeout: int = DETECT_TIMEOUT,
    _retries: int = 1,
) -> tuple[bool, int | None]:
    """Return (reachable, latency_ms) for the LM Studio instance at base_url.

    Passes LM_STUDIO_API_TOKEN as Bearer if set, so secured deployments are
    not misreported as unreachable. Retries once (2 s gap) to catch backends
    still booting.
    """
    url = f"{base_url.rstrip('/')}/v1/models"
    headers = {"Authorization": f"Bearer {LMS_API_TOKEN}"} if LMS_API_TOKEN else {}
    for attempt in range(_retries + 1):
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code < 400:
                    latency = int((time.monotonic() - t0) * 1000)
                    return True, latency
        except Exception:
            pass
        if attempt < _retries:
            print(f"[agent_launcher]   ↻  retrying {base_url} (attempt {attempt + 2}/{_retries + 1})…")
            await asyncio.sleep(2)
    return False, None


# ---------------------------------------------------------------------------
# Helpers: logging, model discovery, missing-backend prompt, routing builder
# ---------------------------------------------------------------------------

def _log_backend(label: str, ok: bool, url: str) -> None:
    status = "✓" if ok else "✗"
    print(f"[agent_launcher]   {status}  {label:<18} {url}")


async def _fetch_models(
    mac_ok: bool,
    mac_url: str,
    mac_lms_ok: bool,
    lms_url: str,
    win_ok: bool = False,
    win_url: str = "",
    win_lms_ok: bool = False,
    win_lms_url: str = "",
) -> dict[str, list[str]]:
    # (signature unchanged — internal callers still pass bool flags)
    """Query live local backends for their actual loaded model names.

    Runs while LAN probes are still in flight — adds no extra latency.
    Falls back to an empty list on any error; callers use env-var constants.
    """
    async def _ollama_tags(url: str) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=DETECT_TIMEOUT) as c:
                r = await c.get(f"{url}/api/tags")
                return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    async def _lms_models(url: str) -> list[str]:
        hdrs = {"Authorization": f"Bearer {LMS_API_TOKEN}"} if LMS_API_TOKEN else {}
        try:
            async with httpx.AsyncClient(timeout=DETECT_TIMEOUT) as c:
                r = await c.get(f"{url.rstrip('/')}/v1/models", headers=hdrs)
                return [m["id"] for m in r.json().get("data", [])]
        except Exception:
            return []

    coros: dict[str, object] = {}
    if mac_ok:
        coros["mac-ollama"] = _ollama_tags(mac_url)
    if mac_lms_ok:
        coros["mac-lmstudio"] = _lms_models(lms_url)
    if RUNNING_ON_WINDOWS and win_ok and win_url:
        coros["win-ollama"] = _ollama_tags(win_url)
    if RUNNING_ON_WINDOWS and win_lms_ok and win_lms_url:
        coros["win-lmstudio"] = _lms_models(win_lms_url)
    if not coros:
        return {}
    gathered = await asyncio.gather(*coros.values(), return_exceptions=True)
    return {
        key: val if isinstance(val, list) else []
        for key, val in zip(coros.keys(), gathered)
    }


def _prompt_missing(items: list[str]) -> None:
    """Print a diagnostic table and ask the user whether to continue offline.

    Non-interactive (stdin not a tty): warns and returns to continue.
    Interactive: calls sys.exit(1) if the user declines.
    """
    print("\n" + "─" * 64)
    print("  SETUP INCOMPLETE — could not reach:")
    for item in items:
        print(f"    ✗  {item}")
    print("─" * 64)
    if not sys.stdin.isatty():
        print("  [non-interactive] continuing offline — fix backends and restart")
        return
    ans = input("  Continue offline anyway? [y/N]: ").strip().lower()
    if ans != "y":
        sys.exit(1)


async def _await_manager_override_async(exc: Exception, timeout: float = 10.0) -> bool:
    """Prompt operator to degrade-or-raise on manager affinity violation.

    Returns True  → operator chose degraded mode (swallow exception).
    Returns False → operator declined / timed out → caller should re-raise.

    Non-interactive (no TTY): auto-deny — fail closed on hardware policy violations.
    """
    if not sys.stdin.isatty():
        print(
            f"\n[agent_launcher] ⚠  Manager affinity violation: {exc}\n"
            f"  [non-interactive] auto-denying — fail closed on hardware policy violation.\n",
            flush=True,
        )
        return False
    print(
        f"\n[agent_launcher] ⚠  Manager affinity violation: {exc}\n"
        f"  Press ENTER within {timeout:.0f}s to run in degraded mode, "
        f"or wait for timeout to abort.\n",
        flush=True,
    )
    try:
        await asyncio.wait_for(asyncio.to_thread(sys.stdin.readline), timeout=timeout)
        print("[agent_launcher] → Operator chose degraded mode.", flush=True)
        return True
    except asyncio.TimeoutError:
        print("[agent_launcher] ✗  Timeout — re-raising HardwareAffinityError.", flush=True)
        return False


def _build_routing_state(
    mac_ok: bool,
    mac_lms_ok: bool,
    win_ok: bool,
    lms_ok: bool,
    local_models: dict[str, list[str]],
    mac_lms_is_local: bool,
    local_ips: frozenset[str],
    manager_affinity_alert: str | None = None,
    scenario: StartupScenario | None = None,
    manager_model: str | None = None,
) -> dict:
    """Construct the routing state dict.

    Agent assignment happens here — only after hardware is confirmed and
    actual model names have been queried from live backends.

    Cloud fallback: when all local backends are offline and PERPLEXITY_API_KEY
    is set, the coder is routed to the Perplexity API instead of leaving a
    'mac-degraded' dead-end pointing at an unreachable URL.
    """
    def _first(key: str, fallback: str) -> str:
        models = local_models.get(key, [])
        return models[0] if models else fallback

    # Manager: Mac Ollama localhost is the highest-priority orchestrator whenever
    # online+accessible; then Mac LM Studio. Affinity-safe (never a NEVER_MAC model).
    if mac_ok:
        manager_endpoint = LOCAL_MAC_URL
        manager_backend  = "mac-ollama"
    else:
        manager_endpoint = MAC_LMS_URL
        manager_backend  = "mac-lmstudio"
    if manager_model is None:
        manager_model = (
            _pick_mac_manager(local_models.get("mac-ollama", []), MAC_MANAGER_MODEL)
            if mac_ok
            else _pick_mac_manager(local_models.get("mac-lmstudio", []), MAC_LMS_MODEL)
        )

    mac_any = mac_ok or mac_lms_ok

    registry = BackendRegistry()
    if lms_ok:
        registry._backends["lmstudio-win"] = Backend(
            "lmstudio-win", REMOTE_WINDOWS_LMS_URL, BackendKind.LMSTUDIO,
            (WINDOWS_LMS_MODEL,), BackendHealth.ONLINE, None,
        )
    if win_ok:
        registry._backends["ollama-win"] = Backend(
            "ollama-win", REMOTE_WINDOWS_URL, BackendKind.OLLAMA,
            (WINDOWS_CODER_MODEL,), BackendHealth.ONLINE, None,
        )
    if not lms_ok and not win_ok:
        manager_kind = BackendKind.OLLAMA if manager_backend == "mac-ollama" else BackendKind.LMSTUDIO
        registry._backends["mac-degraded"] = Backend(
            "mac-degraded", manager_endpoint, manager_kind,
            (manager_model,), BackendHealth.ONLINE, None,
        )

    spec = {
        "task_type": "coding",
        "target_tier": "shared",
        "model_hint": None,
        "base_url_override": None,
    }
    backend = resolve_backend_for_spec(registry, spec)
    coder_endpoint = backend.base_url
    if backend.name == "lmstudio-win":
        coder_model = WINDOWS_LMS_MODEL
        coder_backend = "windows-lmstudio"
    elif backend.name == "ollama-win":
        coder_model = WINDOWS_CODER_MODEL
        coder_backend = "windows-ollama"
    else:
        coder_model = manager_model
        coder_backend = "mac-degraded"
    coder_platform = "win" if coder_backend.startswith("windows-") else "mac"

    # ── Cloud fallback ───────────────────────────────────────────────────────
    # When all local backends are offline (coder_backend == "mac-degraded") and
    # a cloud API key is configured, route to the cloud instead of a dead URL.
    _perplexity_key = os.getenv("PERPLEXITY_API_KEY", "")
    _anthropic_key  = os.getenv("ANTHROPIC_API_KEY", "")
    if coder_backend == "mac-degraded" and (_perplexity_key or _anthropic_key):
        if _perplexity_key and not _perplexity_key.startswith("your_"):
            coder_endpoint = "https://api.perplexity.ai"
            coder_model    = os.getenv("CLOUD_CODER_MODEL", "sonar-reasoning-pro")
            coder_backend  = "perplexity"
            coder_platform = "cloud"
            print("[agent_launcher] ☁  all local backends offline — routing coder to Perplexity API")
        elif _anthropic_key:
            coder_endpoint = "https://api.anthropic.com"
            coder_model    = os.getenv("CLOUD_CODER_MODEL", "claude-4-5-thinking")
            coder_backend  = "anthropic"
            coder_platform = "cloud"
            print("[agent_launcher] ☁  all local backends offline — routing coder to Anthropic API")

    if coder_platform not in ("cloud",):
        try:
            check_affinity(coder_model, coder_platform)
        except HardwareAffinityError as exc:
            print(f"[agent_launcher] ✗  {exc}")
            print("[agent_launcher]   affinity violation escalates to controller; refusing silent fallback")
            raise

    _scenario = scenario or classify_scenario(mac_ok, mac_lms_ok, win_ok, lms_ok,
                                               cloud_ok=coder_backend in ("perplexity", "anthropic"))

    return {
        "manager_endpoint":      manager_endpoint,
        "manager_model":         manager_model,
        "manager_backend":       manager_backend,
        "coder_endpoint":        coder_endpoint,
        "coder_model":           coder_model,
        "coder_backend":         coder_backend,
        "mac_ollama_ok":         mac_ok,
        "mac_lmstudio_ok":       mac_lms_ok,
        "windows_ollama_ok":     win_ok,
        "windows_lm_studio_ok":  lms_ok,
        "distributed":           win_ok or lms_ok,
        "mac_only":              not win_ok and not lms_ok,
        "mac_reachable":         mac_any,
        "windows_ip":            WINDOWS_IP,
        "lmstudio_endpoint":     REMOTE_WINDOWS_LMS_URL if lms_ok else None,
        "lmstudio_model":        WINDOWS_LMS_MODEL if lms_ok else None,
        "lmstudio_detected":     lms_ok,
        "mac_lmstudio_endpoint": MAC_LMS_URL if mac_lms_ok else None,
        "mac_lmstudio_model":    MAC_LMS_MODEL if mac_lms_ok else None,
        "mac_lmstudio_is_local": mac_lms_is_local,
        "local_ips":             sorted(local_ips),
        "discovered_models":     local_models,
        "manager_affinity_alert": manager_affinity_alert,
        "scenario_name":          _scenario.value,
    }


# ---------------------------------------------------------------------------
# Core: detect hardware and build routing state
# ---------------------------------------------------------------------------

async def initialize_environment() -> dict:
    """Detect available hardware and return agent routing state.

    All four backend probes fire concurrently at t=0 using adaptive timeouts
    derived from startup history. Local (Mac) results are awaited first and
    gate agent-role commitment. LAN results are collected as soon as they
    arrive — no sequential blocking.

    Each probe returns (ok: bool, latency_ms: int | None) so we can record
    probe durations in startup_history.jsonl for future adaptive tuning.

    Returns a dict suitable for writing to .state/routing.json.
    """
    # ── Load history hints for adaptive timeouts ──────────────────────────
    history = _load_history()
    hints = build_routing_hints(history)
    win_timeout = hints["suggested_timeout_win_lms"]
    if win_timeout != DETECT_TIMEOUT:
        print(f"[agent_launcher] ℹ  adaptive timeout: Win LMS → {win_timeout}s "
              f"(P50={hints['win_lms_p50_ms']}ms from last {len(history)} runs)")
    if hints["win_ip_hint"] and hints["win_ip_hint"] != WINDOWS_IP:
        print(f"[agent_launcher] ℹ  history hint: Win IP was {hints['win_ip_hint']} "
              f"last run (current config: {WINDOWS_IP})")

    # ── All probes start at t=0 ───────────────────────────────────────────
    t_mac_ol  = asyncio.create_task(
        check_remote_worker(LOCAL_MAC_URL, timeout=DETECT_TIMEOUT),   name="mac-ollama")
    t_mac_lms = asyncio.create_task(
        check_lmstudio_worker(MAC_LMS_URL, timeout=DETECT_TIMEOUT),   name="mac-lmstudio")
    t_win_ol  = asyncio.create_task(
        check_remote_worker(REMOTE_WINDOWS_URL, timeout=DETECT_TIMEOUT), name="win-ollama")
    t_win_lms = asyncio.create_task(
        check_lmstudio_worker(REMOTE_WINDOWS_LMS_URL, timeout=win_timeout), name="win-lmstudio")

    # ── Step 1: await local results — they gate agent-role commitment ─────
    print("[agent_launcher] Probing backends…")
    (mac_ok, _mac_ol_lat), (mac_lms_ok, _mac_lms_lat) = await asyncio.gather(t_mac_ol, t_mac_lms)
    _log_backend("Mac Ollama",    mac_ok,    LOCAL_MAC_URL)
    _log_backend("Mac LM Studio", mac_lms_ok, MAC_LMS_URL)

    # ── Step 2: identify actual models on live local backends ─────────────
    # Runs while LAN tasks are still in flight — no extra wall-clock cost.
    local_models = await _fetch_models(mac_ok, LOCAL_MAC_URL, mac_lms_ok, MAC_LMS_URL)
    for backend, models in local_models.items():
        if models:
            preview = ", ".join(models[:3]) + (" …" if len(models) > 3 else "")
            print(f"[agent_launcher]   ↳ {backend}: {preview}")

    # ── Step 3: collect LAN results (Win LM Studio usually already done) ──
    (win_ok, _win_ol_lat), (lms_ok, _win_lms_lat) = await asyncio.gather(t_win_ol, t_win_lms)
    _log_backend("Win Ollama",    win_ok, REMOTE_WINDOWS_URL)
    _log_backend("Win LM Studio", lms_ok, REMOTE_WINDOWS_LMS_URL)
    if RUNNING_ON_WINDOWS:
        local_models.update(await _fetch_models(
            False, "", False, "",
            win_ok=win_ok,
            win_url=REMOTE_WINDOWS_URL,
            win_lms_ok=lms_ok,
            win_lms_url=REMOTE_WINDOWS_LMS_URL,
        ))

    # ── Step 4: device-identity guard ────────────────────────────────────
    # If a "remote" URL resolves to a local IP, the user mis-configured
    # WINDOWS_IP — do NOT spawn a second researcher on the same device.
    local_ips = _get_local_ips()

    if not RUNNING_ON_WINDOWS:
        if win_ok and _is_local_endpoint(REMOTE_WINDOWS_URL, local_ips):
            print(f"[agent_launcher] ⚠  Windows Ollama {REMOTE_WINDOWS_URL} is THIS device"
                  f" — ignoring (one role per device; local IPs: {sorted(local_ips)})")
            win_ok = False

        if lms_ok and _is_local_endpoint(REMOTE_WINDOWS_LMS_URL, local_ips):
            print(f"[agent_launcher] ⚠  Windows LM Studio {REMOTE_WINDOWS_LMS_URL} is THIS device"
                  f" — ignoring (one role per device)")
            lms_ok = False

    # If Mac Ollama AND Mac LM Studio are both on this device, Ollama takes
    # priority (avoid two simultaneous inference loads on the same GPU/CPU).
    mac_lms_is_local = _is_local_endpoint(MAC_LMS_URL, local_ips)
    if mac_lms_is_local and mac_ok and mac_lms_ok:
        print(f"[agent_launcher] ℹ  Mac LM Studio ({MAC_LMS_URL}) is on this device"
              f" — Ollama takes precedence (one role per device)")
        mac_lms_ok = False

    # ── Step 5: prompt if no local backend found ──────────────────────────
    mac_any = mac_ok or mac_lms_ok
    if not mac_any:
        _prompt_missing([
            f"Mac Ollama      → {LOCAL_MAC_URL}  (run: ollama serve)",
            f"Mac LM Studio   → {MAC_LMS_URL}  (start LM Studio server)",
        ])

    # ── Step 6: assign agents — hardware confirmed, models identified ─────
    # Pre-compute manager model (mirrors _build_routing_state logic) so we can
    # run the async override prompt before committing to routing state.
    manager_affinity_alert: str | None = None
    _mac_ol = local_models.get("mac-ollama", [])
    _mac_lms = local_models.get("mac-lmstudio", [])
    if mac_ok:
        _ensure_mac_ollama_models_present(_mac_ol, LOCAL_MAC_URL)
    # Mac ollama-localhost is the highest-priority orchestrator when online;
    # affinity-safe pick (never a NEVER_MAC Win coder that leaked into the bucket).
    _mgr_model: str | None = None
    try:
        _mgr_model = (
            _pick_mac_manager(_mac_ol, MAC_MANAGER_MODEL)
            if mac_ok
            else _pick_mac_manager(_mac_lms, MAC_LMS_MODEL)
        )
        check_affinity(_mgr_model, "mac")
    except HardwareAffinityError as exc:
        override = await _await_manager_override_async(exc, timeout=10.0)
        if override:
            if _mgr_model is None:
                _mgr_model = MAC_MANAGER_MODEL if mac_ok else MAC_LMS_MODEL
            mac_ok = False
            mac_lms_ok = False
            mac_any = False
            manager_affinity_alert = str(exc)
        else:
            raise

    # ── Step 7: classify scenario and record startup experience ──────────
    _cloud_ok = bool(os.getenv("PERPLEXITY_API_KEY", "").strip() or
                     os.getenv("ANTHROPIC_API_KEY", "").strip())
    scenario = classify_scenario(mac_ok, mac_lms_ok, win_ok, lms_ok, cloud_ok=_cloud_ok)
    print(f"[agent_launcher] ✓  scenario: {scenario.value}")
    _record_startup(scenario, {
        "mac_ol_latency_ms":  _mac_ol_lat,
        "mac_lms_latency_ms": _mac_lms_lat,
        "win_ol_latency_ms":  _win_ol_lat,
        "win_lms_latency_ms": _win_lms_lat,
    })

    # ── Step 8: classify fleet mode (Phase 2 — peer topology detection) ─────
    # Placeholder: peers_reachable defaults to 0 (SOLO) until Phase 3 peer
    # discovery is implemented. Will be populated by LAN discovery module.
    _peers_reachable = 0  # TODO: replace with actual peer discovery count
    _cross_reachable = False  # TODO: replace with actual mesh probe results
    fleet_mode = classify_fleet_mode(_peers_reachable, _cross_reachable)
    print(f"[agent_launcher] ✓  fleet mode: {fleet_mode.value}")

    return _build_routing_state(
        mac_ok, mac_lms_ok, win_ok, lms_ok, local_models, mac_lms_is_local, local_ips,
        manager_affinity_alert=manager_affinity_alert,
        scenario=scenario,
        manager_model=_mgr_model,
    )


# ---------------------------------------------------------------------------
# Auto-write detected IPs back to .env so future runs are pre-configured
# ---------------------------------------------------------------------------

def _patch_env_file(env_path: Path, mac_lms_url: str, win_lms_url: str) -> bool:
    """Patch LM_STUDIO_MAC_ENDPOINT, LM_STUDIO_WIN_ENDPOINTS, and WINDOWS_IP
    in a .env-style file. Returns True if any line was updated."""
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return False

    updated = False
    new_lines = []
    for line in lines:
        stripped = line.rstrip("\n").rstrip()
        if stripped.startswith("LM_STUDIO_MAC_ENDPOINT="):
            want = f"LM_STUDIO_MAC_ENDPOINT={mac_lms_url}\n"
            if line != want:
                line = want
                updated = True
        elif stripped.startswith("LM_STUDIO_WIN_ENDPOINTS="):
            rest = stripped[len("LM_STUDIO_WIN_ENDPOINTS="):]
            parts = [p.strip() for p in rest.split(",")]
            if parts[0] != win_lms_url:
                parts[0] = win_lms_url
                want = "LM_STUDIO_WIN_ENDPOINTS=" + ",".join(parts) + "\n"
                line = want
                updated = True
        elif stripped.startswith("WINDOWS_IP="):
            want = f"WINDOWS_IP={WINDOWS_IP}\n"
            if line != want:
                line = want
                updated = True
        new_lines.append(line)

    if updated:
        try:
            env_path.write_text("".join(new_lines), encoding="utf-8")
        except OSError as exc:
            print(f"[agent_launcher] ⚠  could not write {env_path.name}: {exc}")
            return False
    return updated


def _persist_detected_ips(state: dict) -> None:
    """Write confirmed live endpoints back into .env AND .env.local.

    Patching both files prevents the stale-.env.local-override bug:
    .env.local is loaded with override=True, so a stale WINDOWS_IP there
    would silently win on the next run even after .env is corrected.

    Only updates lines that already exist in each file (safe, non-destructive).
    """
    _here = Path(__file__).resolve().parents[2]
    mac_lms_url = state.get("mac_lmstudio_endpoint") or MAC_LMS_URL
    win_lms_url = state.get("lmstudio_endpoint") or REMOTE_WINDOWS_LMS_URL

    patched_any = False
    for env_name in (".env", ".env.local"):
        env_path = _here / env_name
        if not env_path.exists():
            continue
        changed = _patch_env_file(env_path, mac_lms_url, win_lms_url)
        if changed:
            print(f"[agent_launcher] ✎  {env_name} updated with live endpoints"
                  f" (Mac LMS: {mac_lms_url}  Win LMS: {win_lms_url})")
            patched_any = True

    if not patched_any:
        print(f"[agent_launcher] ✔  .env/.env.local already have correct endpoints — no update needed")


# ---------------------------------------------------------------------------
# State persistence (idempotency: .state/routing.json)
# ---------------------------------------------------------------------------

def save_routing_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    try:
        from orchestrator.periscope_adapter import maybe_emit_routing_observation

        maybe_emit_routing_observation(STATE_FILE.parent, state)
    except Exception:
        pass  # observation must never break routing persistence


def load_routing_state() -> dict | None:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return None


# ---------------------------------------------------------------------------
# CLI interactive configuration
# ---------------------------------------------------------------------------

def interactive_configure() -> None:
    """Prompt user for hardware details and write to .env overrides."""
    print("\n=== Agent Launcher — Hardware Configuration ===")
    print("Press Enter to accept defaults shown in [brackets].\n")

    mac_host = input(f"  Mac Ollama host   [{LOCAL_MAC_HOST}]: ").strip() or LOCAL_MAC_HOST
    mac_port = input(f"  Mac Ollama port   [{LOCAL_MAC_PORT}]: ").strip() or str(LOCAL_MAC_PORT)
    win_ip   = input(f"  Windows IP        [{WINDOWS_IP}]: ").strip() or WINDOWS_IP
    win_port = input(f"  Windows port      [{WINDOWS_PORT}]: ").strip() or str(WINDOWS_PORT)

    env_path = Path(".env.local")
    lines = [
        f"LOCAL_MAC_HOST={mac_host}",
        f"LOCAL_MAC_PORT={mac_port}",
        f"WINDOWS_IP={win_ip}",
        f"WINDOWS_PORT={win_port}",
    ]
    env_path.write_text("\n".join(lines) + "\n")
    print(f"\n  Saved to {env_path}. Re-run without --configure to apply.\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(args: argparse.Namespace) -> None:
    if args.configure:
        interactive_configure()
        return

    # --status: print saved state without re-probing
    if args.status:
        saved = load_routing_state()
        if saved is None:
            print("[agent_launcher] No state saved yet — run without --status first")
            sys.exit(1)
        print(json.dumps(saved, indent=2))
        return

    print("[agent_launcher] Detecting hardware...")
    state = await initialize_environment()

    # ── Print routing state ───────────────────────────────────────────────
    print("\n┌─ AGENT ROUTING STATE ─────────────────────────────────────────┐")
    mode = "DISTRIBUTED (Mac + Windows)" if state["distributed"] else "MAC-ONLY (degraded)"
    print(f"│  Mode        : {mode}")
    print(f"│  Manager     : {state['manager_endpoint']}  [{state['manager_model']}]")
    print(f"│  Coder       : {state['coder_endpoint']}  [{state['coder_model']}]  ({state['coder_backend']})")
    if state["mac_only"]:
        print("│  NOTE: Windows worker offline — all tasks routed to Mac")
    print("└" + "─" * 55)

    # Interactive prompt — skip in --write-state (non-interactive) mode
    if not args.write_state:
        if state["windows_ollama_ok"]:
            # Explicit confirmation only when primary Win Ollama path is active
            proceed = input("\nProceed with distributed mode? [Y/n]: ").strip().lower()
            if proceed == "n":
                print("  To set up the Windows instance first, run: python setup_wizard.py")
                return
        elif state["windows_lm_studio_ok"]:
            pass  # LM Studio is the active coder backend — no prompt needed
        elif state["mac_reachable"]:
            print("\nWindows worker not detected. Running in Mac-only mode.")
            print("  To configure Windows: python agent_launcher.py --configure")
            print("  To install on Windows first: python setup_wizard.py")

    # Persist routing state for orchestrator consumers
    save_routing_state(state)
    # Write confirmed live endpoints back to .env so future runs start correctly
    _persist_detected_ips(state)

    if args.write_state:
        # Machine-readable one-liner for start.sh
        bk = state["coder_backend"]
        print(f"[agent_launcher] manager={state['manager_endpoint']}  "
              f"coder={state['coder_endpoint']} ({bk})  "
              f"distributed={state['distributed']}")
        return state

    print(f"\n[agent_launcher] Routing state saved to {STATE_FILE}")
    print("[agent_launcher] Ready. Import routing state in your orchestrator:")
    print("  from agent_launcher import initialize_environment")

    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Hardware-aware agent launcher for Perpetua-Tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python agent_launcher.py                # detect + print + interactive\n"
            "  python agent_launcher.py --write-state  # detect, save, exit (non-interactive)\n"
            "  python agent_launcher.py --status       # print saved state, no probing\n"
            "  python agent_launcher.py --configure    # set hardware IPs interactively\n"
        ),
    )
    parser.add_argument(
        "--configure",
        action="store_true",
        help="Interactively configure hardware IP addresses and ports",
    )
    parser.add_argument(
        "--write-state",
        dest="write_state",
        action="store_true",
        help="Detect backends, write .state/routing.json, exit (non-interactive). "
             "Used by start.sh and automated callers.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print the last saved .state/routing.json without re-probing. "
             "Exits 1 if no state file exists yet.",
    )
    args = parser.parse_args()
    asyncio.run(main(args))
