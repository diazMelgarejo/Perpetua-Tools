"""
orchestrator/alphaclaw_manager.py — Perpetua-Tools  v0.9.9.9
-------------------------------------------------------------
Authoritative AlphaClaw lifecycle manager and backend probe.

This module owns all gateway/backend decisions for the three-repo stack:
  - Backend probing (was: start.sh § 2a — agent_launcher.py)
  - Mode determination (was: start.sh § 2c — routing.json reader)
  - AlphaClaw bootstrap delegation (wraps alphaclaw_bootstrap.py)

orama-system delegates to this module via a single subprocess call:
    python -m orchestrator.alphaclaw_manager --resolve

which writes a JSON payload to stdout that orama reads to configure itself.

Architecture invariant:
  PT is authoritative for gateway discovery, route choice, topology, and
  readiness. orama-system ONLY applies PT-resolved config — it makes zero
  gateway decisions.

References:
  docs/adapter-interface-contract.md
  docs/MIGRATION.md § Resolved Tensions — Tension 2
  docs/adr/ADR-001-three-repo-adapter-architecture.md
"""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import subprocess
import sys

_log = logging.getLogger(__name__)
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from utils.hardware_policy import check_affinity

SCRIPT_DIR = Path(__file__).resolve().parent.parent   # PT root or site-packages
STATE_DIR = SCRIPT_DIR / ".state"
ROUTING_JSON = STATE_DIR / "routing.json"


def _tool_script(module_name: str) -> Path:
    """Resolve a perpetua_tools CLI script for source checkout and wheel installs.

    Defers import errors so callers get a structured probe/bootstrap failure
    instead of an ImportError that breaks module-level import.
    """
    try:
        mod = importlib.import_module(module_name)
        return Path(mod.__file__).resolve()
    except Exception as exc:
        # Sentinel path; callers guard with .is_file() before use.
        sentinel = SCRIPT_DIR / "src" / module_name.replace(".", "/")
        _log.debug("_tool_script(%r) failed (%s) — sentinel: %s", module_name, exc, sentinel)
        return sentinel


AGENT_LAUNCHER_SCRIPT = _tool_script("perpetua_tools.agent_launcher")
ALPHACLAW_BOOTSTRAP_SCRIPT = _tool_script("perpetua_tools.alphaclaw_bootstrap")
TOOLS_DIR = AGENT_LAUNCHER_SCRIPT.parent


def _pt_subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """PYTHONPATH for perpetua_tools CLIs (orchestrator + src packages)."""
    env = {**os.environ, **(extra or {})}
    paths = [str(SCRIPT_DIR)]
    src_dir = SCRIPT_DIR / "src"
    if src_dir.is_dir():
        paths.append(str(src_dir))
    existing = env.get("PYTHONPATH", "")
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env

# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class BackendProbeResult:
    """Result of probing available AI backends."""
    mac_reachable: bool = False
    windows_reachable: bool = False
    distributed: bool = False
    mac_ip: str = ""
    win_ip: str = ""
    ollama_mac_ok: bool = False
    ollama_win_ok: bool = False
    lm_studio_mac_ok: bool = False
    lm_studio_win_ok: bool = False
    error: str = ""


@dataclass
class RuntimeMode:
    """Operational mode determined from backend probe results."""
    mode: str = "offline"          # "distributed" | "single" | "offline"
    description: str = "no backends found"
    mac_reachable: bool = False
    windows_reachable: bool = False
    distributed: bool = False


@dataclass
class AlphaClawState:
    """State of the AlphaClaw gateway after bootstrap."""
    running: bool = False
    port: int = 0
    commandeered: bool = False
    started: bool = False
    error: str = ""
    gateway_url: str = ""
    openclaw_config: dict | None = None
    role_routing: dict | None = None
    tls_enabled: bool = False
    tls_fingerprint: str = ""


def _port_from_gateway_url(url: str) -> int:
    if not url:
        return 0
    try:
        return int(str(url).rsplit(":", 1)[-1].rstrip("/"))
    except (TypeError, ValueError):
        return 0


def _parse_bootstrap_json(stdout: str) -> dict:
    """Parse alphaclaw_bootstrap --json stdout; return {} on failure.

    Handles mixed output where progress log lines precede the final JSON blob.
    """
    text = (stdout or "").strip()
    if not text:
        return {}
    # Fast path: pure JSON output
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        pass
    # Slow path: scan lines from the end to find the last JSON object blob
    lines = text.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith("{"):
            candidate = "\n".join(lines[i:])
            try:
                data = json.loads(candidate)
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                continue
    return {}


@dataclass
class RuntimePayload:
    """
    Complete resolved runtime state — the single JSON output PT provides to orama.

    orama reads this to configure itself. It does NOT re-derive any of these
    values — that would violate the PT-is-authoritative invariant.
    """
    schema_version: str = "alphaclaw-manager-v1"
    mode: str = "offline"
    description: str = ""
    mac_ip: str = ""
    win_ip: str = ""
    distributed: bool = False
    mac_reachable: bool = False
    windows_reachable: bool = False
    alphaclaw_port: int = 0
    alphaclaw_running: bool = False
    alphaclaw_commandeered: bool = False
    alphaclaw_gateway_url: str = ""
    alphaclaw_tls_enabled: bool = False
    alphaclaw_tls_fingerprint: str = ""
    probe_error: str = ""
    bootstrap_error: str = ""
    env_exports: dict[str, str] = field(default_factory=dict)


# ─── Backend probe ─────────────────────────────────────────────────────────────

def _resolve_peer_ips(mac_ip: str = "", win_ip: str = "") -> tuple[str, str]:
    """Resolve mac/win IPs from explicit args, env vars, or documentation-net
    defaults (192.0.2.0/24, RFC 5737 — intentionally non-routable placeholders,
    not live LAN defaults).
    """
    mac_ip = mac_ip or os.getenv("MAC_IP", "192.0.2.2")
    win_ip = win_ip or os.getenv("WIN_IP", "192.0.2.1")
    return mac_ip, win_ip


def probe_backends(
    mac_ip: str = "",
    win_ip: str = "",
    max_tries: int = 5,
    retry_interval_s: float = 5.0,
) -> BackendProbeResult:
    """
    Probe available AI backends via agent_launcher.py.
    Retries up to max_tries times (matches start.sh §2a behaviour).

    Previously this logic lived in start.sh §2a. PT now owns it.

    Returns a BackendProbeResult with reachability flags and IPs.
    """
    mac_ip, win_ip = _resolve_peer_ips(mac_ip, win_ip)

    launcher = AGENT_LAUNCHER_SCRIPT
    if not launcher.is_file():
        return BackendProbeResult(
            mac_ip=mac_ip,
            win_ip=win_ip,
            error=f"agent_launcher.py not found at {launcher}",
        )

    env = _pt_subprocess_env({
        "WINDOWS_IP": win_ip,
        "OLLAMA_MAC_ENDPOINT": "http://localhost:11434",
        "MAC_IP": mac_ip,
        "WIN_IP": win_ip,
    })

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    last_error = ""
    for attempt in range(1, max_tries + 1):
        try:
            result = subprocess.run(
                [sys.executable, str(launcher), "--write-state"],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
                cwd=str(SCRIPT_DIR),
            )
            if result.returncode == 0 and ROUTING_JSON.stat().st_size > 0:
                return _parse_routing_json(mac_ip, win_ip)
        except subprocess.TimeoutExpired:
            last_error = "agent_launcher.py timed out"
        except Exception as e:
            last_error = str(e)

        if attempt < max_tries:
            import time
            print(
                f"  [alphaclaw_manager] probe attempt {attempt}/{max_tries} — "
                f"retrying in {retry_interval_s:.0f}s…",
                file=sys.stderr,
            )
            time.sleep(retry_interval_s)

    # All attempts exhausted — try reading existing routing.json if present
    if ROUTING_JSON.is_file() and ROUTING_JSON.stat().st_size > 0:
        r = _parse_routing_json(mac_ip, win_ip)
        r.error = f"probe failed after {max_tries} tries (using cached state): {last_error}"
        return r

    return BackendProbeResult(
        mac_ip=mac_ip,
        win_ip=win_ip,
        error=f"probe failed after {max_tries} tries: {last_error}",
    )


def _parse_routing_json(mac_ip: str, win_ip: str) -> BackendProbeResult:
    """Read routing.json written by agent_launcher --write-state."""
    try:
        data: dict[str, Any] = json.loads(ROUTING_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        return BackendProbeResult(
            mac_ip=mac_ip, win_ip=win_ip, error=f"routing.json parse error: {e}"
        )

    distributed = bool(data.get("distributed"))
    mac_ok      = bool(data.get("mac_reachable"))
    win_ok      = bool(data.get("windows_reachable") or data.get("win_reachable"))

    return BackendProbeResult(
        mac_reachable    = mac_ok,
        windows_reachable= win_ok,
        distributed      = distributed,
        mac_ip           = data.get("mac_ip", mac_ip),
        win_ip           = data.get("win_ip", win_ip),
        ollama_mac_ok    = bool(data.get("ollama_mac_ok") or data.get("ollama_mac")),
        ollama_win_ok    = bool(data.get("ollama_win_ok") or data.get("ollama_windows")),
        lm_studio_mac_ok = bool(data.get("lm_studio_mac_ok") or data.get("lm_studio_mac")),
        lm_studio_win_ok = bool(data.get("lm_studio_win_ok") or data.get("lm_studio_windows")),
    )


# ─── Mode determination ────────────────────────────────────────────────────────

def determine_mode(probe: BackendProbeResult) -> RuntimeMode:
    """
    Determine operational mode from probe results.

    Previously this logic lived in start.sh §2c. PT now owns it.

    Modes:
      distributed — Mac + Windows both reachable (tandem autoresearchers)
      single      — Mac only (single-agent mode)
      offline     — no backends found (warn; services still start)
    """
    if probe.distributed and probe.mac_reachable and probe.windows_reachable:
        return RuntimeMode(
            mode="distributed",
            description="Mac + Windows both reachable — tandem autoresearchers",
            mac_reachable=True,
            windows_reachable=True,
            distributed=True,
        )
    elif probe.mac_reachable:
        return RuntimeMode(
            mode="single",
            description="Mac only — single-agent mode",
            mac_reachable=True,
            windows_reachable=False,
            distributed=False,
        )
    else:
        return RuntimeMode(
            mode="offline",
            description="no backends responded — offline mode",
            mac_reachable=False,
            windows_reachable=False,
            distributed=False,
        )


# ─── Hardware affinity enforcement ────────────────────────────────────────────

class AlphaClawManager:
    """Thin OO wrapper for callers that expect a manager instance."""

    def validate_routing_affinity(self, model_id: str, platform: str) -> bool:
        """
        Validate a model/hardware assignment before agent spawn.

        Raises HardwareAffinityError on violation; returns True otherwise.
        """
        check_affinity(model_id=model_id, platform=platform)
        return True


def validate_routing_affinity(model_id: str, platform: str) -> bool:
    """Module-level wrapper so callers don't need an AlphaClawManager instance."""
    mgr = AlphaClawManager()
    return mgr.validate_routing_affinity(model_id=model_id, platform=platform)


# ─── AlphaClaw bootstrap ───────────────────────────────────────────────────────

def alphaclaw_tls_enabled() -> bool:
    """Env gate for the local HTTPS-in-front-of-AlphaClaw proxy, matching
    the parsing convention already established by
    orchestrator/dangerous_workers.py's PT_ALLOW_DANGEROUS_CLI_WORKERS.

    Off by default: this is new, optional-today infrastructure (see
    docs/v2/49-peer-mesh-auth-tls-v2-plan.md in orama-system for the full
    plan this is the v1 slice of) -- opt-in, not a behavior change to any
    existing deployment until an operator explicitly asks for it.
    """
    v = (os.environ.get("ALPHACLAW_TLS_ENABLED") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


_active_tls_proxy = None  # type: ignore[var-annotated]
"""The currently-running AlphaClawTlsProxy, if any. Module-level because
bootstrap_alphaclaw() can be called repeatedly across the process lifetime
(re-resolution, retries) -- without tracking this, each call would leak a
new socket + daemon thread rather than replacing the previous one."""


def _maybe_wrap_gateway_with_tls(state: AlphaClawState) -> AlphaClawState:
    """If ALPHACLAW_TLS_ENABLED, start a local HTTPS proxy in front of the
    resolved AlphaClaw gateway and return state with gateway_url replaced.

    This is the ONLY place gateway_url's scheme is decided -- matching
    this module's own architecture invariant (PT is authoritative for
    gateway discovery, route choice, topology, and readiness; orama-system
    makes zero gateway decisions). orama never independently decides to
    use HTTPS; it only ever reads whatever gateway_url PT resolved here.

    Never raises to the caller -- a TLS failure degrades to the original
    (HTTP) state with the error recorded, rather than blocking gateway
    resolution entirely. bootstrap_alphaclaw()'s own non-fatal-error
    convention is preserved: TLS is an enhancement to a working gateway,
    not a precondition for having one. Unlike the original version of this
    function, the failure IS now visible in the returned state's own
    `error` field (previously only logged) -- a fingerprint mismatch in
    particular is a real security signal that must reach the resolved
    runtime payload, not just a log line an operator might not be
    watching.
    """
    global _active_tls_proxy
    if not alphaclaw_tls_enabled():
        return state
    if not state.running or not state.port:
        return state
    if _active_tls_proxy is not None:
        try:
            _active_tls_proxy.stop()
        except OSError as exc:
            _log.debug("AlphaClaw TLS: error stopping previous proxy instance: %s", exc)
        _active_tls_proxy = None
    try:
        from orchestrator.alphaclaw_tls_proxy import (
            AlphaClawCertFingerprintMismatch,
            AlphaClawTlsProxy,
            AlphaClawTlsUnavailable,
        )

        proxy = AlphaClawTlsProxy(upstream_port=state.port)
        https_url = proxy.start()
        _active_tls_proxy = proxy
        _log.info(
            "AlphaClaw TLS: gateway now served at %s (upstream http on port %d), "
            "fingerprint=%s...",
            https_url, state.port, proxy.fingerprint[:16],
        )
        return AlphaClawState(
            running=state.running,
            port=state.port,
            commandeered=state.commandeered,
            started=state.started,
            error=state.error,
            gateway_url=https_url,
            openclaw_config=state.openclaw_config,
            role_routing=state.role_routing,
            tls_enabled=True,
            tls_fingerprint=proxy.fingerprint,
        )
    except (AlphaClawTlsUnavailable, AlphaClawCertFingerprintMismatch, OSError) as exc:
        # Narrowed from a bare `except Exception` -- catching everything
        # here would also swallow genuine programming errors (a typo'd
        # attribute, an import cycle) as if they were routine "TLS isn't
        # available" cases. A fingerprint mismatch especially must not be
        # confused with an ordinary startup failure -- it's a MITM-
        # detection signal (see alphaclaw_tls_proxy.py's own docstring).
        tls_error = f"AlphaClaw TLS unavailable ({type(exc).__name__}): {exc}"
        _log.error(
            "AlphaClaw TLS: could not start proxy (%s) -- gateway remains "
            "on plain HTTP. If this is a certificate fingerprint mismatch, "
            "investigate before dismissing it.",
            tls_error,
        )
        return AlphaClawState(
            running=state.running,
            port=state.port,
            commandeered=state.commandeered,
            started=state.started,
            error=state.error or tls_error,
            gateway_url=state.gateway_url,
            openclaw_config=state.openclaw_config,
            role_routing=state.role_routing,
            tls_enabled=False,
            tls_fingerprint="",
        )


def bootstrap_alphaclaw(mac_ip: str = "", win_ip: str = "") -> AlphaClawState:
    """
    Delegate to alphaclaw_bootstrap.py — PT's canonical AlphaClaw lifecycle.

    This replaces start.sh §2b's delegation logic. PT orchestrates AlphaClaw;
    orama is told where the gateway ended up via the resolved payload.
    """
    bootstrap = ALPHACLAW_BOOTSTRAP_SCRIPT
    if not bootstrap.is_file():
        return AlphaClawState(error=f"alphaclaw_bootstrap.py not found at {bootstrap}")

    mac_ip, win_ip = _resolve_peer_ips(mac_ip, win_ip)

    env = _pt_subprocess_env({
        "PT_HOME": str(SCRIPT_DIR),
        "MAC_IP": mac_ip,
        "WIN_IP": win_ip,
    })

    try:
        result = subprocess.run(
            [sys.executable, str(bootstrap), "--bootstrap", "--json"],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
            cwd=str(SCRIPT_DIR),
            stdin=subprocess.DEVNULL,
        )
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        if result.returncode == 0:
            payload = _parse_bootstrap_json(result.stdout)
            state = _read_alphaclaw_state()
            gateway_url = str(payload.get("gateway_url") or state.gateway_url or "")
            port = _port_from_gateway_url(gateway_url) or state.port
            resolved = AlphaClawState(
                running=bool(payload.get("gateway_ready", state.running)),
                port=port,
                commandeered=bool(payload.get("commandeered", state.commandeered)),
                started=bool(payload.get("gateway_ready", state.started)),
                error=str(payload.get("error") or state.error or ""),
                gateway_url=gateway_url,
                openclaw_config=payload.get("openclaw_config"),
                role_routing=payload.get("role_routing"),
            )
            # The ONLY place gateway_url's scheme is decided -- see
            # _maybe_wrap_gateway_with_tls's own docstring for the
            # architecture-invariant rationale. No-op unless
            # ALPHACLAW_TLS_ENABLED is set.
            return _maybe_wrap_gateway_with_tls(resolved)
        return AlphaClawState(error=f"bootstrap exited {result.returncode}")
    except subprocess.TimeoutExpired:
        return AlphaClawState(error="alphaclaw_bootstrap.py timed out after 120s")
    except Exception as e:
        return AlphaClawState(error=str(e))


def _read_alphaclaw_state() -> AlphaClawState:
    """
    Read onboarding.json written by alphaclaw_bootstrap.py after health poll.
    Falls back to a healthy default if the file doesn't exist yet.
    """
    onboarding = STATE_DIR / "onboarding.json"
    try:
        if onboarding.is_file():
            data = json.loads(onboarding.read_text(encoding="utf-8"))
            ac = data.get("alphaclaw", {})
            return AlphaClawState(
                running=bool(ac.get("running", True)),
                port=int(ac.get("port", 18789)),
                commandeered=bool(ac.get("commandeered", False)),
                started=bool(ac.get("started", False)),
            )
    except Exception:
        pass
    # Bootstrap succeeded but no state file yet — assume default port, running
    return AlphaClawState(running=True, port=18789, started=True)


# ─── Unified resolve ──────────────────────────────────────────────────────────

def resolve_runtime(
    mac_ip: str = "",
    win_ip: str = "",
    skip_probe: bool = False,
    skip_bootstrap: bool = False,
    probe_max_tries: int = 5,
    probe_retry_interval: float = 5.0,
) -> RuntimePayload:
    """
    Full resolution sequence — the single entry point orama calls.

    Steps:
      1. Probe backends (agent_launcher.py) — unless skip_probe
      2. Determine mode from probe results
      3. Bootstrap AlphaClaw (alphaclaw_bootstrap.py) — unless skip_bootstrap
      4. Return RuntimePayload JSON

    The returned payload is the single source of truth for all services.
    orama reads it; it makes zero additional gateway decisions.
    """
    mac_ip, win_ip = _resolve_peer_ips(mac_ip, win_ip)

    # Step 1: probe
    if skip_probe:
        probe = BackendProbeResult(mac_ip=mac_ip, win_ip=win_ip)
    else:
        print("  [alphaclaw_manager] probing backends…", file=sys.stderr)
        probe = probe_backends(
            mac_ip=mac_ip,
            win_ip=win_ip,
            max_tries=probe_max_tries,
            retry_interval_s=probe_retry_interval,
        )
        if probe.error:
            print(f"  [alphaclaw_manager] probe: {probe.error}", file=sys.stderr)

    # Step 2: mode
    mode = determine_mode(probe)
    print(f"  [alphaclaw_manager] mode={mode.mode}  ({mode.description})", file=sys.stderr)

    # Step 2.5 — affinity pre-flight on resolved models
    _coder_model = os.getenv("CODER_MODEL", "")
    _mgr_model = os.getenv("MANAGER_MODEL", "")
    _coder_backend = os.getenv("CODER_BACKEND", "unknown")
    _coder_platform = "win" if "win" in _coder_backend else "mac"  # canonical: "win" not "windows"
    if _coder_model:
        try:
            validate_routing_affinity(_coder_model, _coder_platform)
            print(f"  [alphaclaw_manager] ✓ coder affinity OK: {_coder_model} → {_coder_platform}", file=sys.stderr)
        except Exception as exc:
            print(f"  [alphaclaw_manager] ⚠ coder affinity violation: {exc}", file=sys.stderr)
    if _mgr_model:
        try:
            validate_routing_affinity(_mgr_model, "mac")
            print(f"  [alphaclaw_manager] ✓ manager affinity OK: {_mgr_model} → mac", file=sys.stderr)
        except Exception as exc:
            print(f"  [alphaclaw_manager] ⚠ manager affinity violation: {exc}", file=sys.stderr)

    # Step 3: bootstrap AlphaClaw
    ac_state = AlphaClawState()
    bootstrap_error = ""
    if skip_bootstrap:
        pass
    else:
        print("  [alphaclaw_manager] bootstrapping AlphaClaw…", file=sys.stderr)
        ac_state = bootstrap_alphaclaw(mac_ip=mac_ip, win_ip=win_ip)
        if ac_state.error:
            bootstrap_error = ac_state.error
            print(
                f"  [alphaclaw_manager] bootstrap non-fatal: {ac_state.error}",
                file=sys.stderr,
            )

    # Step 4: assemble payload
    env_exports = {
        "MAC_IP": mac_ip,
        "WIN_IP": win_ip,
        "OLLAMA_MAC_ENDPOINT": "http://localhost:11434",
        "OLLAMA_WINDOWS_ENDPOINT": f"http://{win_ip}:11434",
        "LM_STUDIO_MAC_ENDPOINT": "http://localhost:1234",
        "LM_STUDIO_WIN_ENDPOINTS": f"http://{win_ip}:1234",
        "WINDOWS_IP": win_ip,
        "GPU_BOX": f"WINUSER@{win_ip}",
        "PT_AGENTS_STATE": str(ROUTING_JSON),
    }
    if ac_state.running and ac_state.port:
        env_exports["ALPHACLAW_PORT"] = str(ac_state.port)
    if ac_state.gateway_url:
        env_exports["ALPHACLAW_GATEWAY_URL"] = ac_state.gateway_url

    return RuntimePayload(
        mode=mode.mode,
        description=mode.description,
        mac_ip=mac_ip,
        win_ip=win_ip,
        distributed=mode.distributed,
        mac_reachable=probe.mac_reachable,
        windows_reachable=probe.windows_reachable,
        alphaclaw_port=ac_state.port,
        alphaclaw_running=ac_state.running,
        alphaclaw_commandeered=ac_state.commandeered,
        alphaclaw_gateway_url=ac_state.gateway_url,
        alphaclaw_tls_enabled=ac_state.tls_enabled,
        alphaclaw_tls_fingerprint=ac_state.tls_fingerprint,
        probe_error=probe.error,
        bootstrap_error=bootstrap_error,
        env_exports=env_exports,
    )


# ─── CLI entrypoint ───────────────────────────────────────────────────────────

def main() -> None:
    """
    CLI used by orama start.sh:

        python -m orchestrator.alphaclaw_manager --resolve \\
            [--mac-ip IP] [--win-ip IP] [--skip-probe] [--skip-bootstrap] \\
            [--probe-tries N] [--quiet]

    Writes the RuntimePayload JSON to stdout. orama reads it via:
        eval $(python -m orchestrator.alphaclaw_manager --resolve --env-only)
    """
    import argparse
    parser = argparse.ArgumentParser(
        description="PT AlphaClaw manager — resolves runtime and prints JSON payload"
    )
    parser.add_argument("--resolve", action="store_true", help="Run full resolve sequence")
    parser.add_argument("--mac-ip",  default="", help="Override MAC_IP")
    parser.add_argument("--win-ip",  default="", help="Override WIN_IP")
    parser.add_argument("--skip-probe",     action="store_true", help="Skip backend probe")
    parser.add_argument("--skip-bootstrap", action="store_true", help="Skip AlphaClaw bootstrap")
    parser.add_argument("--probe-tries",    type=int, default=5)
    parser.add_argument("--probe-interval", type=float, default=5.0)
    parser.add_argument("--env-only", action="store_true",
                        help="Output shell eval-able env exports instead of full JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress to stderr")
    args = parser.parse_args()

    if args.quiet:
        import io
        sys.stderr = io.StringIO()

    if not args.resolve:
        parser.print_help()
        sys.exit(0)

    payload = resolve_runtime(
        mac_ip=args.mac_ip,
        win_ip=args.win_ip,
        skip_probe=args.skip_probe,
        skip_bootstrap=args.skip_bootstrap,
        probe_max_tries=args.probe_tries,
        probe_retry_interval=args.probe_interval,
    )

    if args.env_only:
        # Emit shell-eval-able export lines for use in start.sh
        for k, v in payload.env_exports.items():
            safe_v = str(v).replace("'", "'\\''")
            print(f"export {k}='{safe_v}'")
        # Also emit mode info
        print(f"export PT_MODE='{payload.mode}'")
        print(f"export PT_DISTRIBUTED='{'yes' if payload.distributed else 'no'}'")
        print(f"export PT_ALPHACLAW_PORT='{payload.alphaclaw_port}'")
    else:
        print(json.dumps(asdict(payload), indent=2))


if __name__ == "__main__":
    main()
