#!/usr/bin/env python3
"""
alphaclaw_bootstrap.py — Perpetua-Tools
------------------------------------------
Canonical AlphaClaw (@chrysb/alphaclaw) gateway install / commandeer / start
logic. ultrathink-system delegates to this script via PT_HOME env var.

Idempotency precedence (a running PT commandeers, else starts, else installs):
  0. Probe candidate ports (incl AlphaClaw :18789 AND OpenClaw :19001) for a
     running gateway -> commandeer it (covers a running AlphaClaw OR OpenClaw).
  3. else, if @chrysb/alphaclaw is installed -> start it (npx alphaclaw start).
  4. else, if the bare OpenClaw CLI is installed -> start its gateway
     (openclaw gateway run; best-effort, falls through if it can't bind).
  5. else -> npm-install @chrysb/alphaclaw, then start.
Then: write ~/.openclaw/openclaw.json from PT routing.json, create agent
workspaces, poll /health (30 s), ensure ~/autoresearch.

NOTE: gateway start can be blocked by an OpenClaw version skew (AlphaClaw-bundled
vs standalone `openclaw` vs the version that wrote openclaw.json) and by the
ai.openclaw.gateway LaunchAgent state — align versions if /health never binds.

Usage:
    python alphaclaw_bootstrap.py --bootstrap [--force]

Environment variables:
    PT_HOME               path to this repo (default: $HOME/Perpetua-Tools)
    UTS_HOME              path to ultrathink-system (fallback for bin/agents/)
    ALPHACLAW_INSTALL_DIR npm install target directory (default: $HOME/.alphaclaw)
    OPENCLAW_GATEWAY_PORT gateway port (default: 18789)
    OPENCLAW_EXTRA_PORTS  comma-separated additional ports to probe
    PT_AGENTS_STATE       path to .state/routing.json produced by agent_launcher
    MAC_IP / WIN_IP       LAN IPs (exported by start.sh)
    LM_STUDIO_*           LM Studio endpoints and token
"""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parents[2]
def _parse_single_port(raw: str, *, default: int, env_name: str) -> int:
    try:
        port = int(raw)
    except ValueError:
        print(f"[alphaclaw] ⚠  Invalid {env_name}: {raw!r}; using {default}")
        return default
    if not 1 <= port <= 65535:
        print(f"[alphaclaw] ⚠  Out-of-range {env_name}: {port}; using {default}")
        return default
    return port

OPENCLAW_GATEWAY_PORT = _parse_single_port(
    os.getenv("OPENCLAW_GATEWAY_PORT", "18789"),
    default=18789,
    env_name="OPENCLAW_GATEWAY_PORT",
)


def _parse_port_list(raw: str) -> list[int]:
    """Parse comma-separated port env vars; skip invalid tokens instead of crashing."""
    ports: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            port = int(token)
        except ValueError:
            print(f"[alphaclaw] ⚠  Ignoring invalid port in OPENCLAW_EXTRA_PORTS: {token!r}")
            continue
        if 1 <= port <= 65535:
            ports.append(port)
    return ports


_extra = _parse_port_list(os.getenv("OPENCLAW_EXTRA_PORTS", ""))
# Probe AlphaClaw's default (18789) AND OpenClaw's native gateway (19001, also the
# --dev port) so a running OpenClaw instance is discovered + commandeered rather
# than missed — otherwise a live OpenClaw on 19001 would be ignored and we'd
# needlessly start a second runtime.
OPENCLAW_CANDIDATE_PORTS: list[int] = list(dict.fromkeys(
    [OPENCLAW_GATEWAY_PORT, 19001, 11435, 8080, 3000, 4000, 9000] + _extra
))

# SOUL source: prefer PT's own bin/agents/, fall back to UTS_HOME/bin/agents/
_UTS_HOME = os.getenv("UTS_HOME", str(Path.home() / "ultrathink-system"))
SOUL_SRC: Path = (
    SCRIPT_DIR / "bin" / "agents"
    if (SCRIPT_DIR / "bin" / "agents").is_dir()
    else Path(_UTS_HOME) / "bin" / "agents"
)

from utils.env_paths import resolve_alphaclaw_install_dir
from utils.model_endpoint_url import ModelEndpointPolicyError, validate_model_endpoint_url

ALPHACLAW_INSTALL_DIR = resolve_alphaclaw_install_dir()

# env-var defaults (exported by start.sh)
# Locality rule (2026-06-24): when running ON a machine, always reach its
# services via localhost. Use the LAN IP only for cross-machine calls.
# Never put bare IP literals here — read from env vars; code-fallback defaults only.
_platform_ovr = os.getenv("ORAMA_PLATFORM", "").strip().lower()
RUNNING_ON_MAC = _platform_ovr in {"mac", "macos", "darwin"} or (
    not _platform_ovr and __import__("sys").platform == "darwin")
RUNNING_ON_WINDOWS = _platform_ovr in {"win", "windows", "win32"} or (
    not _platform_ovr and __import__("sys").platform.startswith("win"))

MAC_IP     = os.getenv("MAC_IP",  "")  # LAN IP; set by discover.py / start.ps1 — never hardcode DHCP
WIN_IP     = os.getenv("WIN_IP",  "192.0.2.1")  # LAN IP; only used cross-machine

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _endpoint_port(parsed, default: int) -> int:
    """Return parsed port or *default*, tolerating malformed urlparse ports."""
    try:
        return parsed.port or default
    except ValueError:
        return default


def _first_csv_endpoint(value: str) -> str:
    """First comma-separated endpoint (LM_STUDIO_WIN_ENDPOINTS is often a CSV list)."""
    return value.split(",")[0].strip() if value else ""


def _canonical_endpoint(url: str) -> str:
    """Ensure a URL has an http:// scheme.

    Bare host:port strings (e.g. ``127.0.1.2:1234`` or ``localhost:11434``)
    are accepted by urlparse but rejected by HTTP clients and by
    ``build_openclaw_config``'s ``baseUrl`` fields.  Every return boundary in
    the locality helpers must go through this guard so callers always receive a
    full URL regardless of the env-var or routing.json source format.
    """
    return url if "://" in url else f"http://{url}"


def _heal_pt_endpoint_url(
    url: str | None,
    *,
    running_on_target: bool,
    port: int,
) -> str:
    """Apply locality self-heal to a routing.json endpoint override."""
    if not url:
        return ""
    url = _first_csv_endpoint(url.strip())
    if not url:
        return ""
    canonical = _canonical_endpoint(url)
    if not running_on_target:
        return canonical
    parsed = urlparse(canonical)
    if parsed.hostname not in _LOOPBACK_HOSTS:
        return f"http://localhost:{_endpoint_port(parsed, port)}"
    return canonical


def _locality_resolve_endpoint(
    env_var: str,
    *,
    default: str,
    running_on_target: bool,
    port: int,
) -> str:
    """Resolve a service URL with locality self-heal for explicit env overrides.

    When bootstrap runs ON the target machine, a stale LAN IP in the env var
  (e.g. from start.sh cross-machine exports) must normalize to localhost —
    matching agent_launcher.py resolve_local_or_remote() (40d3f65 fixed defaults only).
    """
    raw = os.getenv(env_var, "").strip()
    raw_first = _first_csv_endpoint(raw)
    url = raw_first or _first_csv_endpoint(default) or default
    canonical = _canonical_endpoint(url)
    try:
        canonical = validate_model_endpoint_url(canonical)
    except ModelEndpointPolicyError as exc:
        print(
            f"[alphaclaw] WARNING: {env_var} resolved to a blocked endpoint policy "
            f"target ({canonical!r}: {exc}) -- falling back to http://localhost:{port}",
            file=sys.stderr,
        )
        return f"http://localhost:{port}"
    if not running_on_target:
        return canonical
    parsed = urlparse(canonical)
    if parsed.hostname not in _LOOPBACK_HOSTS:
        healed = f"http://localhost:{_endpoint_port(parsed, port)}"
        if raw:
            print(
                f"[alphaclaw] WARNING: {env_var}={raw} is non-loopback but bootstrap "
                f"runs on the target machine — normalizing to {healed}",
                file=sys.stderr,
            )
        return healed
    return canonical


# Each endpoint resolves to localhost when this process runs ON the target machine.
OLLAMA_MAC = _locality_resolve_endpoint(
    "OLLAMA_MAC_ENDPOINT",
    default="http://localhost:11434" if RUNNING_ON_MAC else f"http://{MAC_IP}:11434",
    running_on_target=RUNNING_ON_MAC,
    port=11434,
)
OLLAMA_WIN = _locality_resolve_endpoint(
    "OLLAMA_WINDOWS_ENDPOINT",
    default="http://localhost:11434" if RUNNING_ON_WINDOWS else f"http://{WIN_IP}:11434",
    running_on_target=RUNNING_ON_WINDOWS,
    port=11434,
)
LMS_MAC = _locality_resolve_endpoint(
    "LM_STUDIO_MAC_ENDPOINT",
    default="http://localhost:1234" if RUNNING_ON_MAC else f"http://{MAC_IP}:1234",
    running_on_target=RUNNING_ON_MAC,
    port=1234,
)
LMS_WIN = _locality_resolve_endpoint(
    "LM_STUDIO_WIN_ENDPOINTS",
    default="http://localhost:1234" if RUNNING_ON_WINDOWS else f"http://{WIN_IP}:1234",
    running_on_target=RUNNING_ON_WINDOWS,
    port=1234,
)
LMS_TOKEN  = os.getenv("LM_STUDIO_API_TOKEN", "lm-studio")
MAC_MODEL  = os.getenv("MAC_LMS_MODEL", "Qwen3.5-9B-MLX-4bit")
WIN_MODEL  = os.getenv("WINDOWS_LMS_MODEL",
                        "qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2")


def _find_npx_v22plus() -> str:
    """
    Selects an npx executable whose bundled Node.js is version 22.14.0 or newer.

    Searches in this order: the npx found in PATH, nvm-installed Node versions (~/.nvm/...), and common Homebrew node@22+/node@24 locations. Returns the first npx whose associated node reports a major/minor version of at least 22.14; if none qualify, falls back to the PATH npx and prints a warning or informational message.
    Returns:
        str: Filesystem path to an npx executable whose Node.js is >= 22.14.0, or the PATH npx when no qualifying binary is found.
    """
    def _node_semver(npx_path: str) -> tuple[int, int]:
        """
        Determine the major and minor Node.js semantic version reported by the `node` executable adjacent to a given `npx` path.
        
        Parameters:
            npx_path (str): Filesystem path to an `npx` executable; the function looks for a sibling `node` executable in the same directory.
        
        Returns:
            tuple[int, int]: A tuple (major, minor) containing the parsed Node.js major and minor version numbers. Returns (0, 0) if the version cannot be determined.
        """
        node_exe = str(Path(npx_path).parent / "node")
        try:
            out = subprocess.check_output(
                [node_exe, "--version"], timeout=3, stderr=subprocess.DEVNULL, text=True
            ).strip()             # "v24.14.1"
            parts = out.lstrip("v").split(".")
            return int(parts[0]), int(parts[1])
        except Exception:
            return (0, 0)

    current_npx = shutil.which("npx") or "npx"
    maj, min_ = _node_semver(current_npx)
    if maj > 22 or (maj == 22 and min_ >= 14):
        return current_npx

    # nvm search — pick highest installed version >= 22.14
    nvm_dir = Path(os.environ.get("NVM_DIR", Path.home() / ".nvm")) / "versions" / "node"
    if nvm_dir.is_dir():
        candidates: list[tuple[int, int, str]] = []
        for node_dir in nvm_dir.iterdir():
            if not node_dir.name.startswith("v"):
                continue
            try:
                parts = node_dir.name[1:].split(".")
                v_maj, v_min = int(parts[0]), int(parts[1])
            except (ValueError, IndexError):
                continue
            if v_maj > 22 or (v_maj == 22 and v_min >= 14):
                npx_cand = node_dir / "bin" / "npx"
                if npx_cand.is_file():
                    candidates.append((v_maj, v_min, str(npx_cand)))
        if candidates:
            candidates.sort(reverse=True)
            found = candidates[0][2]
            print(f"[alphaclaw] ℹ  Node v{maj}.{min_} in PATH is < 22.14"
                  f" — using nvm node v{candidates[0][0]}.{candidates[0][1]}"
                  f" ({found})")
            return found

    # Homebrew fallbacks
    for brew_path in [
        "/opt/homebrew/opt/node@24/bin/npx",
        "/opt/homebrew/opt/node@22/bin/npx",
        "/usr/local/opt/node@24/bin/npx",
        "/usr/local/opt/node@22/bin/npx",
    ]:
        if Path(brew_path).is_file():
            print(f"[alphaclaw] ℹ  Using Homebrew Node at {brew_path}")
            return brew_path

    # Warn and fall back — the gateway will crash with a clear error
    print(
        f"[alphaclaw] ⚠  Node.js v22.14.0+ is required (node:sqlite); "
        f"current node is v{maj}.{min_}.\n"
        f"           Install: brew install node  OR  nvm install 24"
    )
    return current_npx


@dataclass
class AlphaClawBootstrapResult:
    ok: bool
    gateway_ready: bool
    gateway_url: str = ""
    gateway_port: int = OPENCLAW_GATEWAY_PORT
    runtime: str = "alphaclaw"
    commandeered: bool = False
    install_dir: str = str(ALPHACLAW_INSTALL_DIR)
    config_path: str = str(Path.home() / ".openclaw" / "openclaw.json")
    error: str = ""
    role_routing: dict[str, object] | None = None
    openclaw_config: dict[str, object] | None = None


# ── ASCII progress bar: poll /health after gateway start ─────────────────────

async def _wait_for_gateway(url: str, timeout: int = 30) -> bool:
    """
    Waits until the gateway at the given base URL responds to /health or the timeout elapses.
    
    Parameters:
        url (str): Base gateway URL (e.g. "http://127.0.0.1:18789"); "/health" will be appended.
        timeout (int): Maximum number of seconds to wait.
    
    Returns:
        True if the gateway returned an HTTP status code < 400 before the timeout, False otherwise.
    """
    try:
        import httpx
    except ImportError:
        print("[alphaclaw] ⚠ httpx not installed — skipping health-check")
        return False

    bar_width = 38
    print(f"\n  [alphaclaw] Waiting for gateway at {url}\u2026")
    for elapsed in range(timeout + 1):
        filled = int(bar_width * elapsed / timeout)
        bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
        pct = int(100 * elapsed / timeout)
        left = timeout - elapsed
        print(f"\r  [alphaclaw] [{bar}] {pct:3d}%  ({left:2d}s)  ",
              end="", flush=True)
        try:
            async with httpx.AsyncClient(timeout=1.0) as c:
                r = await c.get(f"{url}/health")
                if r.status_code < 400:
                    ready_bar = "\u2588" * bar_width
                    print(
                        f"\r  [alphaclaw] [{ready_bar}] 100%  "
                        "\u2713 ready          "
                    )
                    return True
        except Exception:
            pass
        if elapsed < timeout:
            await asyncio.sleep(1)
    timeout_bar = "\u2591" * bar_width
    print(
        f"\r  [alphaclaw] [{timeout_bar}] timed out after {timeout}s           "
    )
    return False


# ── gateway discovery ─────────────────────────────────────────────────────────

async def _probe_url(url: str, client) -> bool:
    """
    Checks whether the given base URL behaves like an OpenClaw-compatible gateway.
    
    Attempts GET requests to the "/health" and "/v1/models" endpoints and treats any response with status code less than 400 as a positive probe.
    
    Parameters:
        url (str): Base URL to probe (may include or omit a trailing slash).
        client: Asynchronous HTTP client exposing an awaitable `get(url)` method.
    
    Returns:
        bool: `True` if either endpoint responds with a status code less than 400, `False` otherwise.
    """
    for path in ("/health", "/v1/models"):
        try:
            r = await client.get(f"{url.rstrip('/')}{path}")
            if r.status_code < 400:
                return True
        except Exception:
            pass
    return False


async def _find_any_gateway() -> str | None:
    """
    Finds a running OpenClaw-compatible gateway on the local candidate ports.
    
    Returns:
        str: Base URL (e.g., "http://127.0.0.1:18789") of the first responsive gateway, or `None` if no gateway is found or the required HTTP client (`httpx`) is unavailable.
    """
    try:
        import httpx
    except ImportError:
        return None
    async with httpx.AsyncClient(timeout=1.5) as client:
        for port in OPENCLAW_CANDIDATE_PORTS:
            url = f"http://127.0.0.1:{port}"
            if await _probe_url(url, client):
                return url
    return None


def _gateway_port_from_url(url: str) -> int:
    """Extract the numeric port from a gateway base URL."""
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError:
        print(f"[alphaclaw] ⚠  Invalid port in gateway URL {url!r}; using {OPENCLAW_GATEWAY_PORT}")
        return OPENCLAW_GATEWAY_PORT
    if port is not None:
        return port
    return OPENCLAW_GATEWAY_PORT


async def _bootstrap_via_bare_openclaw(
    config_dir: Path,
    config_file: Path,
    *,
    force: bool,
) -> dict[str, object] | None:
    """Start bare OpenClaw when AlphaClaw is absent — no npm required."""
    if _is_alphaclaw_installed() or not _is_openclaw_installed():
        return None
    ALPHACLAW_INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    _oc_creds = _gather_alphaclaw_credentials(timeout=30)
    _oc_url = await _start_openclaw_gateway(
        ALPHACLAW_INSTALL_DIR / "logs", str(_oc_creds["password"])
    )
    if not _oc_url:
        return None
    os.environ["OPENCLAW_GATEWAY_URL"] = _oc_url
    _oc_pt = _load_pt_state()
    _oc_cfg = (
        _write_openclaw_config(config_dir, config_file)
        if (not config_file.exists() or force)
        else build_openclaw_config(_oc_pt)
    )
    _ensure_agent_workspaces(config_dir)
    _ensure_autoresearch()
    return asdict(
        AlphaClawBootstrapResult(
            ok=True,
            gateway_ready=True,
            gateway_url=_oc_url,
            gateway_port=_gateway_port_from_url(_oc_url),
            runtime="openclaw",
            role_routing=build_role_routing(_oc_pt),
            openclaw_config=_oc_cfg,
        )
    )


def _is_alphaclaw_installed() -> bool:
    """
    Determine whether AlphaClaw is available on the system.
    
    Checks for a global "alphaclaw" executable on PATH or for the package directory at ALPHACLAW_INSTALL_DIR/node_modules/@chrysb/alphaclaw.
    
    Returns:
        `True` if AlphaClaw is available as a system executable or a local package, `False` otherwise.
    """
    if shutil.which("alphaclaw"):
        return True
    nm = ALPHACLAW_INSTALL_DIR / "node_modules" / "@chrysb" / "alphaclaw"
    return nm.exists()


def _is_openclaw_installed() -> bool:
    """True if the bare OpenClaw CLI (the runtime AlphaClaw wraps) is on PATH."""
    return shutil.which("openclaw") is not None


async def _start_openclaw_gateway(log_dir: Path, setup_password: str, timeout: int = 20) -> str | None:
    """Best-effort start of the bare OpenClaw WebSocket gateway (`openclaw gateway run`).

    Detached; polls the candidate ports for a reachable gateway. Returns the
    gateway URL if one comes up within `timeout`, else None so the caller falls
    through to starting the installed AlphaClaw wrapper (precedence step 4).
    The HTTP readiness probe is best-effort — OpenClaw's gateway is WebSocket, so
    on builds without an HTTP /health this returns None and we fall back cleanly.
    """
    openclaw_bin = shutil.which("openclaw")
    if not openclaw_bin:
        return None
    print("[alphaclaw] → OpenClaw installed — starting bare OpenClaw gateway (openclaw gateway run)…")
    log_dir.mkdir(parents=True, exist_ok=True)
    _fh = None
    try:
        _fh = open(log_dir / "openclaw-gateway.log", "ab")  # noqa: SIM115 - detached child inherits the handle
        subprocess.Popen(
            [openclaw_bin, "gateway", "run"],
            stdin=subprocess.DEVNULL,
            env={**os.environ, "SETUP_PASSWORD": setup_password},
            stdout=_fh,
            stderr=subprocess.STDOUT,
        )
    except Exception as e:
        print(f"[alphaclaw] ⚠ OpenClaw gateway start failed ({e}) — falling back to AlphaClaw")
        return None
    finally:
        if _fh is not None:
            _fh.close()
    for _ in range(timeout):
        url = await _find_any_gateway()
        if url:
            print(f"[alphaclaw] ✓ OpenClaw gateway reachable at {url}")
            return url
        await asyncio.sleep(1)
    print(f"[alphaclaw] ⚠ OpenClaw gateway not reachable within {timeout}s — falling back to AlphaClaw")
    return None


# ── config + workspaces ───────────────────────────────────────────────────────

_PT_STATE_SCHEMA = {
    "type": "object",
    "properties": {
        "mac_lmstudio_endpoint": {"type": "string", "pattern": r"^https?://"},
        "lmstudio_endpoint": {"type": "string", "pattern": r"^https?://"},
        "manager_endpoint": {"type": "string", "pattern": r"^https?://"},
        "coder_endpoint": {"type": "string", "pattern": r"^https?://"},
        "coder_model": {"type": "string", "maxLength": 128},
        "manager_model": {"type": "string", "maxLength": 128},
        "coder_backend": {
            "type": "string",
            "enum": [
                "windows-lmstudio",
                "windows-ollama",
                "mac-lmstudio",
                "mac-ollama",
                "mac-degraded",
                "perplexity",
                "anthropic",
                "unknown",
            ],
        },
        "mac_lmstudio_ok": {"type": "boolean"},
        "manager_backend": {"type": "string"},
    },
    "additionalProperties": True,
}

_CLOUD_CODER_BACKENDS = frozenset({"perplexity", "anthropic"})
_ALLOWED_CLOUD_HOST_RE = re.compile(r"^(api\.perplexity\.ai|api\.anthropic\.com)$")


def _validate_endpoint_host(key: str, url: str, *, cloud: bool = False) -> None:
    """Reject malformed hosts; enforce localhost/RFC-1918 or allowed cloud APIs."""
    parsed = urlparse(url if "://" in url else f"http://{url}")
    host = parsed.hostname
    if not host:
        raise ValueError(f"routing.json {key}={url!r} is missing a hostname.")
    if cloud:
        if parsed.scheme != "https":
            raise ValueError(
                f"routing.json {key}={url!r} must use https for cloud coder "
                "backends — cleartext http would expose the cloud API key."
            )
        if not _ALLOWED_CLOUD_HOST_RE.match(host):
            raise ValueError(
                f"routing.json {key}={url!r} resolves to disallowed cloud host {host!r}. "
                "Only api.perplexity.ai and api.anthropic.com are permitted for cloud coder backends."
            )
        return
    if host == "localhost":
        return
    try:
        addr = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError(
            f"routing.json {key}={url!r} must use localhost or a loopback/RFC-1918 IP."
        ) from exc
    # IPv4-mapped IPv6 (::ffff:a.b.c.d) hides link-local/private checks on the wrapper.
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    if addr.is_link_local:
        raise ValueError(
            f"routing.json {key}={url!r} resolves to link-local host {host!r}. "
            "Only localhost and RFC-1918 addresses are permitted."
        )
    if not (addr.is_loopback or addr.is_private):
        raise ValueError(
            f"routing.json {key}={url!r} resolves to non-RFC-1918 host {host!r}. "
            "Only localhost and RFC-1918 addresses are permitted."
        )


def _validate_pt_state(state: dict) -> dict:
    """Schema-validate routing.json before use. Raises ValueError on violation."""
    from jsonschema import ValidationError, validate

    try:
        validate(state, _PT_STATE_SCHEMA)
    except ValidationError as exc:
        raise ValueError(f"routing.json schema violation: {exc.message}") from exc
    coder_backend = state.get("coder_backend", "")
    for key in (
        "mac_lmstudio_endpoint",
        "lmstudio_endpoint",
        "manager_endpoint",
        "coder_endpoint",
    ):
        url = state.get(key, "")
        if not url:
            continue
        _validate_endpoint_host(
            key,
            url,
            cloud=(key == "coder_endpoint" and coder_backend in _CLOUD_CODER_BACKENDS),
        )
    return state


def _load_pt_state() -> dict | None:
    """
    Load and parse the PT agents state JSON from the path specified by the PT_AGENTS_STATE environment variable.
    
    Returns:
        dict: Parsed JSON object from the file pointed to by `PT_AGENTS_STATE`.
        None: If `PT_AGENTS_STATE` is not set or the referenced file does not exist.
    """
    state_path = os.getenv("PT_AGENTS_STATE")
    if state_path and Path(state_path).exists():
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
        if isinstance(state, dict):
            return _validate_pt_state(state)
        raise ValueError("routing.json must be a JSON object")
    return None


def _lms_base_url(raw: str) -> str:
    """
    Normalize an LM Studio base URL so it ends with `/v1`.
    
    Parameters:
        raw (str): Base URL which may include a trailing slash or path.
    
    Returns:
        str: The input URL ensured to end with `/v1`.
    """
    raw = raw.rstrip("/")
    return raw if raw.endswith("/v1") else f"{raw}/v1"


def build_role_routing(pt: dict | None = None) -> dict[str, object]:
    """
    Builds a role routing specification for the gateway using PT agent state or sensible defaults.
    
    Parameters:
        pt (dict | None): Optional PT agents state dictionary; when omitted the function will attempt to load PT state internally. Recognized keys:
            - "manager_backend", "manager_endpoint", "manager_model"
            - "coder_backend", "coder_endpoint", "coder_model"
            - "distributed" (truthy enables distributed topology)
    
    Returns:
        dict: A routing dictionary with the following keys:
            - "topology" (str): either "manager-local_researcher-remote" when distributed is true or "single-node-local" otherwise.
            - "distributed" (bool): whether a distributed researcher/coder topology is selected.
            - "manager", "researcher", "coder", "autoresearcher" (dict): each contains "backend", "endpoint", and "model" entries describing where that role should be routed.
    """
    pt = pt or _load_pt_state() or {}
    manager_backend = pt.get("manager_backend", "mac-ollama")
    manager_endpoint = pt.get("manager_endpoint", OLLAMA_MAC)
    manager_model = pt.get("manager_model", MAC_MODEL)
    coder_backend = pt.get("coder_backend", "mac-degraded")
    coder_endpoint = pt.get("coder_endpoint", manager_endpoint)
    coder_model = pt.get("coder_model", manager_model)
    distributed = bool(pt.get("distributed"))
    researcher_backend = coder_backend if distributed else manager_backend
    researcher_endpoint = coder_endpoint if distributed else manager_endpoint
    researcher_model = coder_model if distributed else manager_model
    topology = "manager-local_researcher-remote" if distributed else "single-node-local"

    return {
        "topology": topology,
        "distributed": distributed,
        "manager": {
            "backend": manager_backend,
            "endpoint": manager_endpoint,
            "model": manager_model,
        },
        "researcher": {
            "backend": researcher_backend,
            "endpoint": researcher_endpoint,
            "model": researcher_model,
        },
        "coder": {
            "backend": coder_backend,
            "endpoint": coder_endpoint,
            "model": coder_model,
        },
        "autoresearcher": {
            "backend": coder_backend,
            "endpoint": coder_endpoint,
            "model": coder_model,
        },
    }


def build_openclaw_config(pt: dict | None = None) -> dict[str, object]:
    """
    Builds the OpenClaw configuration dictionary from Perpetua-Tools agent state or sensible defaults.
    
    Parameters:
    	pt (dict | None): Optional PT agents state (as returned by _load_pt_state()). When provided, its keys (e.g. `mac_lmstudio_endpoint`, `lmstudio_endpoint`, `coder_model`, `manager_model`, `coder_backend`, `mac_lmstudio_ok`) influence which endpoints, models, and provider selections are used. If omitted or None, environment-derived defaults are used.
    
    Returns:
    	config (dict): A configuration mapping suitable for writing to ~/.openclaw/openclaw.json with top-level keys:
    	- `gateway`: local gateway settings (`mode`, `port`, `bind`, `commandeered`).
    	- `agents`: `defaults` and `list` of agent entries with `id`, `model.primary`, and `workspace` paths.
    	- `models`: provider definitions for `lmstudio-mac`, `lmstudio-win`, `ollama-mac`, and `ollama-win`, including base URLs, API keys, and model metadata.
    """
    pt = pt or _load_pt_state()
    if pt:
        mac_lms_url = _heal_pt_endpoint_url(
            pt.get("mac_lmstudio_endpoint"),
            running_on_target=RUNNING_ON_MAC,
            port=1234,
        ) or LMS_MAC
        win_lms_url = _heal_pt_endpoint_url(
            pt.get("lmstudio_endpoint"),
            running_on_target=RUNNING_ON_WINDOWS,
            port=1234,
        ) or LMS_WIN
        coder_model   = pt.get("coder_model",   WIN_MODEL)
        manager_model = pt.get("manager_model", MAC_MODEL)
        coder_backend = pt.get("coder_backend", "mac-degraded")
        mac_lms_ok    = bool(pt.get("mac_lmstudio_ok"))
        ollama_mac_url = (
            _heal_pt_endpoint_url(
                pt.get("manager_endpoint"),
                running_on_target=RUNNING_ON_MAC,
                port=11434,
            )
            if pt.get("manager_backend") == "mac-ollama" and pt.get("manager_endpoint")
            else OLLAMA_MAC
        )
        ollama_win_url = (
            _heal_pt_endpoint_url(
                pt.get("coder_endpoint"),
                running_on_target=RUNNING_ON_WINDOWS,
                port=11434,
            )
            if pt.get("coder_backend") == "windows-ollama" and pt.get("coder_endpoint")
            else OLLAMA_WIN
        )
    else:
        mac_lms_url, win_lms_url = LMS_MAC, LMS_WIN
        coder_model, manager_model = WIN_MODEL, MAC_MODEL
        coder_backend, mac_lms_ok = "unknown", False
        ollama_mac_url, ollama_win_url = OLLAMA_MAC, OLLAMA_WIN

    if coder_backend == "windows-lmstudio":
        coder_primary = f"lmstudio-win/{coder_model}"
    elif coder_backend == "windows-ollama":
        coder_primary = f"ollama-win/{coder_model}"
    else:
        coder_primary = f"lmstudio-mac/{manager_model}"

    manager_primary = (
        f"lmstudio-mac/{manager_model}" if mac_lms_ok
        else f"ollama-mac/{manager_model}"
    )

    agents_root = str(Path.home() / ".openclaw" / "agents")
    return {
        "gateway": {
            "mode": "local",
            "port": OPENCLAW_GATEWAY_PORT,
            "bind": "loopback",
            "commandeered": False,
        },
        "agents": {
            "defaults": {
                "model": {"primary": manager_primary},
                "workspace": f"{agents_root}/default",
            },
            "list": [
                {"id": "mac-researcher",
                 "model": {"primary": manager_primary},
                 "workspace": f"{agents_root}/mac-researcher"},
                {"id": "win-researcher",
                 "model": {"primary": coder_primary},
                 "workspace": f"{agents_root}/win-researcher"},
                {"id": "orchestrator",
                 "model": {"primary": manager_primary},
                 "workspace": f"{agents_root}/orchestrator"},
                {"id": "coder",
                 "model": {"primary": coder_primary},
                 "workspace": f"{agents_root}/coder"},
                {"id": "autoresearcher",
                 "model": {"primary": coder_primary},
                 "workspace": str(Path.home() / "autoresearch")},
            ],
        },
        "models": {
            "providers": {
                "lmstudio-mac": {
                    "baseUrl": _lms_base_url(mac_lms_url),
                    "apiKey": LMS_TOKEN,
                    "api": "openai-completions",
                    "models": [{"id": manager_model,
                                "name": f"Mac LMS \u2014 {manager_model}",
                                "contextWindow": 32768, "maxTokens": 8192,
                                "cost": {"input": 0, "output": 0}}],
                },
                "lmstudio-win": {
                    "baseUrl": _lms_base_url(win_lms_url),
                    "apiKey": LMS_TOKEN,
                    "api": "openai-completions",
                    "models": [{"id": coder_model,
                                "name": f"Win LMS \u2014 {coder_model}",
                                "contextWindow": 32768, "maxTokens": 8192,
                                "cost": {"input": 0, "output": 0}}],
                },
                "ollama-mac": {
                    "apiKey": "ollama-local",
                    "baseUrl": ollama_mac_url,
                    "api": "ollama",
                    "models": [],
                },
                "ollama-win": {
                    "apiKey": "ollama-remote",
                    "baseUrl": ollama_win_url,
                    "api": "ollama",
                    "models": [],
                },
            },
        },
    }


def _write_openclaw_config(config_dir: Path, config_file: Path) -> dict[str, object]:
    """
    Write the OpenClaw configuration to disk and return the generated config.
    
    Creates config_dir if missing, builds the OpenClaw configuration from PT agent state, writes it to config_file as pretty-printed JSON, prints a status line with the chosen coder backend, and returns the config dictionary.
    
    Parameters:
        config_dir (Path): Directory in which the configuration file will be placed; created if it does not exist.
        config_file (Path): Path to the JSON configuration file to write.
    
    Returns:
        dict[str, object]: The OpenClaw configuration dictionary that was written to disk.
    """
    pt = _load_pt_state()
    config = build_openclaw_config(pt)
    role_routing = build_role_routing(pt)
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
    config_file.chmod(0o600)  # contains API keys — restrict to owner
    coder_backend = role_routing["coder"]["backend"]
    print(
        f"[alphaclaw] \u2713 openclaw.json written \u2192 {config_file}"
        f"  (coder-backend={coder_backend})"
    )
    return config


def _ensure_agent_workspaces(config_dir: Path) -> None:
    """
    Ensure agent workspace directories exist under the OpenClaw config directory and populate missing SOUL.md files.
    
    For each role (mac-researcher, win-researcher, orchestrator, coder, autoresearcher) this creates a directory at
    `<config_dir>/agents/<role>` if missing. If that role's `SOUL.md` is absent, attempts to copy it from the repository
    SOUL source (`SOUL_SRC/<role>/SOUL.md`) and prints a status message; if the source file is missing, prints a warning.
    
    Parameters:
        config_dir (Path): Root OpenClaw configuration directory under which the `agents/` subdirectory will be created.
    """
    agents_dir = config_dir / "agents"
    roles = ["mac-researcher", "win-researcher", "orchestrator", "coder", "autoresearcher"]
    for role in roles:
        role_dir = agents_dir / role
        role_dir.mkdir(parents=True, exist_ok=True)
        soul_file = role_dir / "SOUL.md"
        if soul_file.exists():
            continue
        src = SOUL_SRC / role / "SOUL.md"
        if src.exists():
            shutil.copy(src, soul_file)
            print(f"[alphaclaw] \u2713 agent workspace: {role}")
        else:
            print(f"[alphaclaw] \u26a0 missing source: bin/agents/{role}/SOUL.md")


def _ensure_autoresearch() -> None:
    """
    Ensure the ~/autoresearch repository exists and is prepared for development.
    
    If ~/autoresearch already exists, the function does nothing. Otherwise it clones the configured remote into ~/autoresearch, sets or resets a dated branch for idempotent first-run setup, installs the `uv` package, and runs the repository's development sync. Failures during cloning, branch checkout, package installation, or sync are reported (printed) and treated as non-fatal; the function does not raise on these errors.
    """
    import datetime
    repo = Path.home() / "autoresearch"
    if repo.exists():
        print("[alphaclaw] ✓ ~/autoresearch already exists")
        return
    remote = os.environ.get(
        "AUTORESEARCH_REMOTE", "https://github.com/uditgoenka/autoresearch"
    )
    print(f"[alphaclaw] → Cloning {remote}…")
    try:
        subprocess.run(
            ["git", "clone", remote, str(repo)],
            check=True,
        )
        branch = f"autoresearch/{datetime.date.today().isoformat()}"
        # -B creates or resets the branch — idempotent on repeated runs same day.
        subprocess.run(["git", "checkout", "-B", branch], cwd=repo, check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "uv"], check=True, capture_output=True)
        subprocess.run(["uv", "sync", "--dev"], cwd=repo, check=True)
        print("[alphaclaw] ✓ autoresearch ready")
    except subprocess.CalledProcessError as e:
        print(f"[alphaclaw] ✗ autoresearch setup failed (non-fatal): {e}")

# ── first-run credentials ─────────────────────────────────────────────────────

_DEFAULT_SETUP_PASSWORD = "alpha1claw"


def _gather_alphaclaw_credentials(timeout: int = 30) -> dict[str, object]:
    """
    Prompt for an AlphaClaw admin password, falling back to a default after a timeout.
    
    If the SETUP_PASSWORD environment variable is set that value is returned immediately. If stdin is not a TTY, the default password is used without prompting. When interactive, the function prompts for input and uses the provided value; if no input is given within `timeout` seconds the default password is used.
    
    Parameters:
        timeout (int): Seconds to wait for user input before using the default password.
    
    Returns:
        dict: A dictionary with keys:
            - "password" (str): The chosen or default password.
            - "is_default" (bool): `true` if the returned password is the default, `false` if provided via env or user input.
    """
    password = os.getenv("SETUP_PASSWORD", "").strip()
    if password:
        return {"password": password, "is_default": False}

    # Non-interactive guard: when stdin is not a tty (e.g. start.sh </dev/null),
    # skip the daemon thread entirely to prevent the stdin BufferedReader deadlock
    # that causes "Abort trap: 6" at interpreter shutdown.
    if not sys.stdin.isatty():
        print("  [credentials] non-interactive — using default password"
              " (set SETUP_PASSWORD= in .env to override)")
        return {"password": _DEFAULT_SETUP_PASSWORD, "is_default": True}

    print("\n  ┌─────────────────────────────────────────────────────────────────┐")
    print("  │  ALPHACLAW FIRST-RUN SETUP                                      │")
    print(f"  │  Set an admin password (default: {_DEFAULT_SETUP_PASSWORD!r} if no input in 30s)   │")
    print("  │  ⚠  Change this password immediately after setup completes      │")
    print("  └─────────────────────────────────────────────────────────────────┘")

    result: dict[str, object] = {"value": None}

    def _read() -> None:
        """
        Read a password prompt from stdin and store the entered value in the shared `result` mapping.
        
        Attempts to read a line with the prompt "  Password (blank = use default): " and assigns the stripped input to result["value"]. If an EOFError or OSError occurs, stores an empty string instead.
        """
        try:
            result["value"] = input("  Password (blank = use default): ").strip()
        except (EOFError, OSError):
            result["value"] = ""

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(timeout)

    raw = result.get("value") or ""
    password = raw if raw else _DEFAULT_SETUP_PASSWORD
    is_default = password == _DEFAULT_SETUP_PASSWORD
    if is_default:
        print(f"\n  ⏰ No input — using default password: {_DEFAULT_SETUP_PASSWORD!r}")
        print("  🔴 SECURITY: Run with SETUP_PASSWORD=<yourpassword> or set it in .env\n")
    return {"password": password, "is_default": is_default}


# ── main bootstrap ────────────────────────────────────────────────────────────

async def bootstrap_alphaclaw(force: bool = False) -> dict[str, object]:
    """
    Idempotently ensure an AlphaClaw gateway is installed, configured, and running, suitable to call on every start.sh run.
    
    Performs discovery to reuse an existing gateway when available, writes or updates ~/.openclaw/openclaw.json and agent workspaces, installs @chrysb/alphaclaw locally when needed, prepares ~/.alphaclaw/.env with setup credentials, starts the gateway, and polls its /health endpoint for readiness.
    
    Parameters:
    	force (bool): If True, overwrite existing configuration and environment files even if they already exist.
    
    Returns:
    	A dict with the bootstrap outcome, matching AlphaClawBootstrapResult fields:
    	  - ok (bool): overall success indicator
    	  - gateway_ready (bool): whether the gateway passed the readiness check
    	  - gateway_url (str): base URL of the active gateway (if available)
    	  - gateway_port (int|None): numeric gateway port when known
    	  - runtime (str|None): runtime identifier when set
    	  - commandeered (bool): True if an existing gateway was reused
    	  - install_dir (str|None): path to the local AlphaClaw install directory
    	  - config_path (str|None): path to the written openclaw config file
    	  - error (str): error message when ok is False, empty otherwise
    	  - role_routing (dict): computed role routing payload
    	  - openclaw_config (dict): computed OpenClaw configuration payload
    """
    try:
        import httpx  # noqa: F401
    except ImportError:
        print("[alphaclaw] \u2717 httpx not installed \u2014 run: pip install httpx")
        return asdict(
            AlphaClawBootstrapResult(
                ok=False,
                gateway_ready=False,
                error="httpx not installed",
            )
        )

    config_dir  = Path.home() / ".openclaw"
    config_file = config_dir  / "openclaw.json"

    # Step 0: commandeer any already-running compatible gateway
    print(
        f"[alphaclaw] \u2192 Probing {len(OPENCLAW_CANDIDATE_PORTS)} candidate ports:"
        f" {OPENCLAW_CANDIDATE_PORTS}"
    )
    existing_url = await _find_any_gateway()

    if existing_url:
        existing_port = _gateway_port_from_url(existing_url)
        if existing_port != OPENCLAW_GATEWAY_PORT:
            print(
                f"[alphaclaw] \u2713 Found gateway at {existing_url}"
                f" (port :{existing_port}) \u2014 commandeering"
            )
        else:
            print(f"[alphaclaw] \u2713 Gateway already running at {existing_url} \u2014 commandeering")
        os.environ["OPENCLAW_GATEWAY_URL"] = existing_url
        pt_state = _load_pt_state()
        if not config_file.exists() or force:
            config = _write_openclaw_config(config_dir, config_file)
        else:
            config = build_openclaw_config(pt_state)
        _ensure_agent_workspaces(config_dir)
        _ensure_autoresearch()
        return asdict(
            AlphaClawBootstrapResult(
                ok=True,
                gateway_ready=True,
                gateway_url=existing_url,
                gateway_port=existing_port,
                commandeered=True,
                role_routing=build_role_routing(pt_state),
                openclaw_config=config,
            )
        )

    print("[alphaclaw] No running gateway found \u2014 proceeding with full bootstrap")

    # Bare OpenClaw path (no npm) — evaluate before any npm-dependent step.
    _openclaw_payload = await _bootstrap_via_bare_openclaw(
        config_dir, config_file, force=force
    )
    if _openclaw_payload is not None:
        return _openclaw_payload
    if not _is_alphaclaw_installed() and _is_openclaw_installed():
        print("[alphaclaw] \u2192 OpenClaw gateway unavailable \u2014 installing AlphaClaw (step 5)")

    # Step 1: npm check (required for AlphaClaw install/start)
    if not shutil.which("npm"):
        print("[alphaclaw] \u2717 npm not found \u2014 install Node 22.14.0+ from https://nodejs.org/ or: nvm install 24")
        return asdict(
            AlphaClawBootstrapResult(
                ok=False,
                gateway_ready=False,
                error="npm not found",
            )
        )

    # Step 1.5: write package.json anchor so npm postinstall (patch-package)
    # resolves the project root to ALPHACLAW_INSTALL_DIR — not the filesystem root.
    ALPHACLAW_INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    _pkg_json = ALPHACLAW_INSTALL_DIR / "package.json"
    if not _pkg_json.exists():
        _pkg_json.write_text(
            json.dumps({"name": "alphaclaw-workspace", "version": "1.0.0", "private": True}),
            encoding="utf-8",
        )

    # Step 2: install @chrysb/alphaclaw locally if missing.
    if not _is_alphaclaw_installed():
        print(
            f"[alphaclaw] \u2192 Installing @chrysb/alphaclaw into"
            f" {ALPHACLAW_INSTALL_DIR}\u2026"
        )
        try:
            # Stream output live; postinstall applies patches (safe, no TTY needed).
            subprocess.run(
                ["npm", "install", "@chrysb/alphaclaw"],
                cwd=str(ALPHACLAW_INSTALL_DIR),
                check=True,
            )
            print("[alphaclaw] \u2713 @chrysb/alphaclaw installed")
        except subprocess.CalledProcessError as e:
            print(f"[alphaclaw] \u2717 install failed: {e}")
            return asdict(
                AlphaClawBootstrapResult(
                    ok=False,
                    gateway_ready=False,
                    error=f"install failed: {e}",
                )
            )
    else:
        print("[alphaclaw] \u2713 @chrysb/alphaclaw already installed \u2014 skipping")

    # Step 3: write config
    pt_state = _load_pt_state()
    if not config_file.exists() or force:
        config = _write_openclaw_config(config_dir, config_file)
    else:
        config = build_openclaw_config(pt_state)

    # Step 4: agent workspaces
    _ensure_agent_workspaces(config_dir)

    # Step 4.5: gather SETUP_PASSWORD + pre-write ~/.alphaclaw/.env
    # This bypasses the AlphaClaw first-run wizard entirely.
    # SETUP_PASSWORD is *required* by alphaclaw start — it will fail without it.
    creds = _gather_alphaclaw_credentials(timeout=30)
    _alphaclaw_env_file = ALPHACLAW_INSTALL_DIR / ".env"
    if not _alphaclaw_env_file.exists() or force:
        try:
            from dotenv import set_key as _set_key
            _set_key(str(_alphaclaw_env_file), "SETUP_PASSWORD", str(creds["password"]))
            _set_key(str(_alphaclaw_env_file), "ALPHACLAW_ROOT_DIR", str(ALPHACLAW_INSTALL_DIR))
            _alphaclaw_env_file.chmod(0o600)  # contains SETUP_PASSWORD \u2014 restrict to owner
            print(f"[alphaclaw] \u2713 .env written \u2192 {_alphaclaw_env_file}")
        except Exception as e:
            print(f"[alphaclaw] \u26a0 .env write failed (non-fatal): {e}")

    # Step 5: start gateway
    gateway_url = f"http://127.0.0.1:{OPENCLAW_GATEWAY_PORT}"
    print("[alphaclaw] \u2192 Starting AlphaClaw gateway\u2026")
    _log_dir = ALPHACLAW_INSTALL_DIR / "logs"
    _log_dir.mkdir(parents=True, exist_ok=True)
    try:
        npx_bin = _find_npx_v22plus()   # node:sqlite needs >= 22.14.0
        # Log to file instead of DEVNULL so hangs are diagnosable.
        # The file handle is intentionally kept open: Popen inherits it and writes
        # gateway stdout to the log. It closes when the Popen process exits or this
        # Python process exits (whichever is first). This is the correct pattern for
        # a detached subprocess log — do not wrap in `with` (that closes it early).
        _log_fh = open(_log_dir / "alphaclaw.log", "a")  # noqa: SIM115 — kept open intentionally; see comment above
        subprocess.Popen(
            [npx_bin, "alphaclaw", "start"],
            cwd=str(ALPHACLAW_INSTALL_DIR),
            stdin=subprocess.DEVNULL,  # prevent stdin inheritance from parent shell
            env={**os.environ,
                 "SETUP_PASSWORD": str(creds["password"]),
                 "ALPHACLAW_ROOT_DIR": str(ALPHACLAW_INSTALL_DIR)},
            stdout=_log_fh,
            stderr=subprocess.STDOUT,
        )
    except Exception as e:
        print(f"[alphaclaw] \u2717 gateway start failed: {e}")
        return asdict(
            AlphaClawBootstrapResult(
                ok=False,
                gateway_ready=False,
                error=f"gateway start failed: {e}",
                openclaw_config=config,
                role_routing=build_role_routing(pt_state),
            )
        )

    # Step 6: poll /health with progress bar
    ready = await _wait_for_gateway(gateway_url, timeout=30)
    if not ready:
        print(
            "[alphaclaw] \u26a0 Gateway did not respond within 30 s "
            "\u2014 continuing anyway (non-fatal)"
        )
    else:
        os.environ["OPENCLAW_GATEWAY_URL"] = gateway_url

    # Persist onboarding state for portal v1.1 + start.sh security warning
    try:
        from orchestrator.onboarding import write_onboarding_state
        write_onboarding_state({
            "alphaclaw": {
                "password_is_default": bool(creds["is_default"]),
                "gateway_url": gateway_url if ready else "",
                "gateway_ready": ready,
                "install_dir": str(ALPHACLAW_INSTALL_DIR),
                "key_configured": bool(os.getenv("GITHUB_TOKEN")),
                "windows_detected": bool(os.getenv("WIN_IP")),
            }
        })
    except Exception as _oe:
        print(f"[alphaclaw] \u26a0 onboarding state write failed (non-fatal): {_oe}")

    # Step 7: autoresearch
    _ensure_autoresearch()
    return asdict(
        AlphaClawBootstrapResult(
            ok=ready,
            gateway_ready=ready,
            gateway_url=os.environ.get("OPENCLAW_GATEWAY_URL", gateway_url),
            gateway_port=_gateway_port_from_url(
                os.environ.get("OPENCLAW_GATEWAY_URL", gateway_url)
            ),
            error="" if ready else "gateway did not pass readiness check",
            role_routing=build_role_routing(pt_state),
            openclaw_config=config,
        )
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Perpetua-Tools AlphaClaw gateway bootstrap",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python alphaclaw_bootstrap.py --bootstrap          # idempotent bootstrap\n"
            "  python alphaclaw_bootstrap.py --bootstrap --force  # force-rewrite config\n"
        ),
    )
    parser.add_argument("--bootstrap", action="store_true",
                        help="Idempotent AlphaClaw install + configure + start")
    parser.add_argument("--force", action="store_true",
                        help="Force-rewrite openclaw.json even if it already exists")
    parser.add_argument("--json", action="store_true",
                        help="Print structured result as JSON")
    _args = parser.parse_args()
    if _args.bootstrap:
        result = asyncio.run(bootstrap_alphaclaw(force=_args.force))
        if _args.json:
            print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("ok") else 1)
    else:
        parser.print_help()
        sys.exit(1)
