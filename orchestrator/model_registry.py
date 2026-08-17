from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import yaml

from orchestrator.connectivity import endpoint_online as _endpoint_online
from orchestrator.gate import filter_chain_by_gate
from utils.endpoint_policy_core import build_transport_url

_DISABLE_LIVE_PROBES = {"1", "true", "yes", "on"}


def _build_tilting_url(tilted: str, port: int, *, default_scheme: str = "http") -> Optional[str]:
    """Rebuild scheme://hostname:port from active_tilting discovery output.

    Compatibility wrapper around the shared endpoint policy core. Preserves the
    transport scheme when discovery returns an absolute URL (e.g. https
    overrides). Returns None when hostname cannot be parsed so callers can fall
    back to models.yml host expansion.
    """
    return build_transport_url(tilted, port, default_scheme=default_scheme)


def _expand_env_default(value: str) -> str:
    """Expand ${VAR:-default} in config strings (e.g. OLLAMA host)."""
    if not isinstance(value, str) or "${" not in value:
        return value
    m = re.match(r"^\$\{([^}:]+)(?::-([^}]*))?\}$", value.strip())
    if m:
        var, default = m.group(1), m.group(2) if m.group(2) is not None else ""
        return os.environ.get(var, default)
    return value


def _host_has_port(host: str) -> bool:
    """True if a host URL already carries a :port (e.g. http://1.2.3.4:1234)."""
    authority = host.split("://", 1)[-1].split("/", 1)[0]
    if authority.startswith("["):
        close = authority.find("]")
        return close != -1 and len(authority) > close + 1 and authority[close + 1] == ":"
    if authority.count(":") > 1:
        return False
    return ":" in authority


@dataclass
class ModelTarget:
    name: str
    backend: str  # ollama | mlx | lm-studio | perplexity | online
    device: str  # mac-studio | win-rtx3080 | shared-ollama-host | cloud
    host: str
    port: int
    context_window: Optional[int]
    roles: List[str]
    priority: int
    online: bool
    reasoning: str
    # Real provider model ID to send to the API. Defaults to `name`; set it in
    # models.yml only when the routing key differs from the wire ID. Dispatchers
    # should send `api_model`, never `name`.
    api_model: str = ""
    # Optional provider-native endpoint suffix. Cloud adapters use the target's
    # configured path rather than inventing a provider URL from a routing alias.
    api_path: str = ""
    # Model-scoped provider options. These are validated by the provider
    # adapter; they are never forwarded as arbitrary request parameters.
    provider_options: Mapping[str, Any] | None = None
    # Evidence for a provider wire ID. Routing aliases can remain stable while
    # a provider API model is upgraded, but cloud dispatch must retain the
    # official source that verified the replacement.
    provenance: Mapping[str, Any] | None = None
    # Optional frugality_router.py tier classification (0-6, see
    # orchestrator/frugality_router.py TIERS / fable5-tier-based-routing
    # skill). Additive-only field (2026-07-22): route_task() does not read
    # or filter on this yet — see docs/plans/2026-07-22-p4-skill-trimming-
    # p3-frugality-wiring.md and its follow-up reconciliation plan for why.
    # Set it in models.yml per-model as that reconciliation lands; leaving
    # it unset (None) is always safe and does not change existing routing
    # behavior.
    frugality_tier: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.api_model:
            self.api_model = self.name


class ModelRegistry:
    """
    Loads config/devices.yml, config/models.yml, config/routing.yml.
    Provides route_task(task_type, preferred_device) → ordered list of ModelTargets
    for use by the orchestrator's fallback chain.

    Top-level agents (Mac + Win) use this skill first (SKILL.md → ModelRegistry).
    Subagents use ECC-tools default logic unless explicitly overridden.
    """

    def __init__(self, config_dir: str = "config") -> None:
        self.config_dir = Path(config_dir)
        raw_devices = self._read_yaml("devices.yml")
        self.devices: Dict[str, Any] = self._normalize_devices(raw_devices)
        self.models_cfg: Dict[str, Any] = self._read_yaml("models.yml")
        self.routing_cfg: Dict[str, Any] = self._read_yaml("routing.yml")

    @staticmethod
    def _normalize_devices(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise devices.yml list format (v0.9.9.5+) to the dict format device_info() expects.

        Old format:  devices: {mac-studio: {...}, win-rtx3080: {...}}
        New format:  devices: [{id: "mac-studio", ...}, {id: "win-rtx3080", ...}]
        Both are handled transparently so callers never need to branch.
        """
        devs = raw.get("devices", {})
        if isinstance(devs, list):
            devs = {d["id"]: d for d in devs if "id" in d}
        return {**raw, "devices": devs}

    def _read_yaml(self, name: str) -> Dict[str, Any]:
        path = self.config_dir / name
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    # ── host resolution ────────────────────────────────────────────────────────

    def _resolve_host(self, item: Dict[str, Any], *, allow_live_discovery: bool = True) -> str:
        """Resolve the host URL for a model entry.

        For devices with identity_method=active_tilting (win-rtx3080), derives
        the Windows IP from the local subnet at runtime so the config is portable
        across 192.168.1.x (legacy) and 192.168.254.x (current) topologies without
        any config file changes.  Explicit env-var overrides always take priority
        (LAN_GPU_IP_OVERRIDE, LM_STUDIO_WIN_ENDPOINTS — checked inside
        detect_active_tilting_ip).

        For all other devices, falls through to the usual env-var expansion.

        Active tilting discovers the Win GPU host for lm-studio (:1234). Win Ollama
        models on the same device must keep their own port (11434) — reusing the
        lm-studio URL would probe the wrong endpoint and mark Ollama models offline.
        """
        device_name = item.get("device", "")
        dev_info = self.device_info(device_name)
        live_disabled = os.getenv("PT_DISABLE_LIVE_MODEL_PROBES", "").strip().lower() in _DISABLE_LIVE_PROBES
        if (
            allow_live_discovery
            and dev_info.get("identity_method") == "active_tilting"
            and not live_disabled
        ):
            from orchestrator.lan_discovery import detect_active_tilting_ip

            tilted = detect_active_tilting_ip()
            if item.get("backend") != "ollama":
                return tilted
            rebuilt = _build_tilting_url(tilted, int(item.get("port", 11434)))
            if rebuilt is None:
                return _expand_env_default(str(item.get("host", "")))
            return rebuilt
        return _expand_env_default(str(item.get("host", "")))

    # ── model listing ─────────────────────────────────────────────────────────

    def list_models(self, *, probe: bool = True) -> List[ModelTarget]:
        targets: List[ModelTarget] = []
        for item in self.models_cfg.get("models", []):
            # A caller that turns probes off is explicitly asking for static
            # configuration only. Avoid LAN discovery as well as endpoint I/O.
            host = self._resolve_host(item, allow_live_discovery=probe)
            port = int(item.get("port", 0))
            backend = item["backend"]
            # `online` is derived LIVE (endpoint reachable AND the model is served),
            # not read from the static models.yml flag — so a model that responds
            # to queries shows online even if the config said False, and a dead
            # endpoint shows offline regardless of config. Cached per-endpoint
            # (short TTL) so this stays cheap. models.yml `online:` is the seed
            # fallback if the live probe layer is unavailable.
            base = host if _host_has_port(host) else (f"{host}:{port}" if port else host)
            if not probe or os.getenv("PT_DISABLE_LIVE_MODEL_PROBES", "").strip().lower() in _DISABLE_LIVE_PROBES:
                online = item.get("online", False)
            else:
                try:
                    online = _endpoint_online(base, backend, item.get("api_model") or item["name"])
                except Exception:
                    online = item.get("online", False)
            targets.append(
                ModelTarget(
                    name=item["name"],
                    backend=backend,
                    device=item["device"],
                    host=host,
                    port=port,
                    context_window=item.get("context_window"),
                    roles=item.get("roles", ["general"]),
                    priority=item.get("priority", 100),
                    online=online,
                    reasoning=item.get("reasoning", "general"),
                    api_model=item.get("api_model", ""),
                    api_path=item.get("api_path", ""),
                    provider_options=item.get("provider_options"),
                    provenance=item.get("provenance"),
                    frugality_tier=item.get("frugality_tier"),
                )
            )
        return sorted(targets, key=lambda x: x.priority)

    def get_model(self, name: str, *, probe: bool = True) -> ModelTarget | None:
        """Return one configured target without making callers parse YAML."""
        return next((target for target in self.list_models(probe=probe) if target.name == name), None)

    def select_for_role(
        self, role: str, preferred_device: Optional[str] = None
    ) -> List[ModelTarget]:
        candidates = [
            m for m in self.list_models() if role in m.roles
        ]
        if preferred_device:
            device_first = [m for m in candidates if m.device == preferred_device]
            others = [m for m in candidates if m.device != preferred_device]
            candidates = device_first + others
        return candidates

    # ── routing ───────────────────────────────────────────────────────────────

    def route_task(
        self,
        task_type: str,
        preferred_device: Optional[str] = None,
        *,
        privacy_critical: bool = False,
        override_confirmed: bool = False,
        override_reason: Optional[str] = None,
    ) -> List[ModelTarget]:
        """
        Returns ordered fallback chain for a task_type.
        Local/preferred device models come first; online models serve as fallback.

        v1.1 P4 frugality wiring (additive, 2026-07-22): before returning,
        the chain is passed through `orchestrator.gate.filter_chain_by_gate()`
        -- the same canonical policy gate (backed by
        `orchestrator/frugality_router.py`) that `src/perpetua_tools/
        orchestrator.py`'s `/orchestrate` `privacy_critical` branch consults.
        Candidates whose `frugality_tier` is unset in `config/models.yml`
        are always kept unchanged -- the gate has no opinion about them, so
        existing callers that never pass the new keyword-only args see
        byte-identical output to before this change. A candidate with a
        classified `frugality_tier` is dropped only when that tier exceeds
        the current `ORAMASYS_OFFLINE` / `privacy_critical` ceiling; see
        `gate.py`'s override contract for how (and why) that can be relaxed.
        `privacy_critical`/`override_confirmed`/`override_reason` are
        additive keyword-only args -- existing positional-arg callers
        (`route_task(task_type, preferred_device)`) are unaffected.
        """
        routes = self.routing_cfg.get("routes", {})
        route = routes.get(task_type, routes.get("default", {}))
        roles: List[str] = route.get("roles", ["general"])

        ordered: List[ModelTarget] = []
        seen: set = set()
        for role in roles:
            for candidate in self.select_for_role(role, preferred_device=preferred_device):
                key = (candidate.name, candidate.device, candidate.backend)
                if key not in seen:
                    ordered.append(candidate)
                    seen.add(key)

        return filter_chain_by_gate(
            ordered,
            task_type=task_type,
            privacy_critical=privacy_critical,
            override_confirmed=override_confirmed,
            override_reason=override_reason,
        )

    def device_info(self, device_name: str) -> Dict[str, Any]:
        return self.devices.get("devices", {}).get(device_name, {})
