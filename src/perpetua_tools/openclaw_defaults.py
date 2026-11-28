"""One reviewed source of truth for the OpenClaw defaults (stdlib only).

The data lives in ``config/openclaw-defaults.json``: names only, never a key value. This module loads and validates it,
renders the OpenClaw config patches the staged restore applies (both config shapes), reports drift against a config
(read-only), and stamps a vendored copy so a consumer can tell when the copy is stale, old or hand-edited.

Nothing here writes a config. Emitting a patch and applying it stay two separate, human-gated steps.

    python -m perpetua_tools.openclaw_defaults --validate
    python -m perpetua_tools.openclaw_defaults --render-patch --shape entries
    python -m perpetua_tools.openclaw_defaults --check ~/.openclaw/openclaw.json
    python -m perpetua_tools.openclaw_defaults --fingerprint
    python -m perpetua_tools.openclaw_defaults --vendor-copy      # prints the stamped copy; writes nothing
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "openclaw-defaults.json"
SCHEMA_VERSION = 1
REQUIRED_DENY = ("exec", "process", "browser", "canvas", "nodes", "cron", "gateway")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
SECRET_VALUE = re.compile(r"sk-[A-Za-z0-9]{20,}|[0-9a-f]{40,}")
SECRET_KEY = re.compile(r"api_?key|token|secret|password|credential", re.I)
KEY_FIELDS = ("apiKey", "api_key_env", "api_key_placeholder")  # each has its own rule in _key_field_problem
LOCAL_PLACEHOLDERS = ("ollama-local", "lm-studio")  # what a local engine takes where it needs no credential
ENV_REFERENCE = re.compile(r"^\$\{(?:env:)?[A-Z][A-Z0-9_]*\}$")
REDACTED = "<redacted>"
MISSING = "<missing>"


def load(path: Path | str | None = None) -> dict[str, Any]:
    with open(path or DEFAULT_PATH, encoding="utf-8") as fh:
        return json.load(fh)


# ----------------------------------------------------------------------------------------------- chains


def chain_for(data: dict[str, Any], seat: str | None = None) -> list[str]:
    """The model chain: the default chain, or the seat's own model followed by the default chain."""
    default = list(data["chain"]["default"])
    if seat is None:
        return default
    return [data["seats"][seat]["model"], *default]


# ------------------------------------------------------------------------------------------- validation


def _is_local_model(model: str) -> bool:
    """True for a route that loads weights on the host: Ollama or Mac LM Studio, not an Ollama cloud model."""
    return model.startswith(("ollama/", "lmstudio-mac/")) and not model.endswith((":cloud", "-cloud"))


def _key_field_problem(field: str, value: Any) -> str | None:
    """A key field holds a name or a documented local placeholder, never a credential."""
    is_name = isinstance(value, str) and bool(ENV_NAME.match(value))
    if field == "api_key_env":
        return None if is_name else "is not an env name (A-Z, digits, underscore)"
    if field == "api_key_placeholder":
        return None if value in LOCAL_PLACEHOLDERS else "is not a documented local placeholder"
    if isinstance(value, str):
        allowed = value in LOCAL_PLACEHOLDERS or bool(ENV_REFERENCE.match(value))
    else:
        allowed = (isinstance(value, dict) and set(value) == {"source", "provider", "id"} and value["source"] == "env"
                   and isinstance(value["id"], str) and bool(ENV_NAME.match(value["id"])))
    return None if allowed else "must be an env reference or a documented local placeholder, not a value"


def _secret_problems(obj: Any, path: str = "") -> list[str]:
    problems: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = f"{path}.{key}" if path else str(key)
            if key in KEY_FIELDS:
                reason = _key_field_problem(key, value)
                if reason:
                    problems.append(f"{here} {reason}")
            else:
                problems.extend(_secret_problems(value, here))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            problems.extend(_secret_problems(value, f"{path}[{index}]"))
    elif isinstance(obj, str):
        leaf = path.rsplit(".", 1)[-1].split("[")[0]
        if SECRET_VALUE.search(obj):
            problems.append("secret-looking value at %s" % path)
        elif SECRET_KEY.search(leaf) and leaf != "login" and obj:
            problems.append("secret field %s must reference an env name, not hold a value" % path)
    return problems


# Everything the renderer and the checks below read: dotted path and the type it is read as. ``*`` is every entry.
_STRUCTURE: tuple[tuple[str, Any], ...] = (
    ("chain.default", list), ("human_gated_models", list), ("thinking.default", str), ("plugins", dict),
    ("model_aliases", dict), ("model_aliases.*.alias", str), ("manual_only", dict), ("manual_only.*", dict),
    ("baseline.update.channel", str), ("baseline.update.check_on_start", bool), ("baseline.update.auto", bool),
    ("env.shell_import.enabled", bool), ("env.shell_import.timeout_ms", int),
    ("providers", dict), ("providers.*", dict), ("seats", dict), ("seats.*.model", str),
    ("seats.*.description", str), ("seats.*.thinking", str), ("seats.*.tools_deny", list), ("seats.*.skills", list),
)
_PROVIDER_FIELDS = (("api", str), ("base_url", str), ("models", list))
_MODEL_FIELDS = (("id", str), ("name", str), ("reasoning", bool), ("input", list), ("context_window", int),
                 ("max_tokens", int))
_HEARTBEAT_FIELDS = (("every", str), ("model", str), ("target", str), ("light_context", bool),
                     ("isolated_session", bool), ("prompt", str))


def _values(obj: Any, parts: list[str], path: str = ""):
    """Yield (path, value) for a dotted pattern; a missing or non-mapping step yields a value of None."""
    if not parts:
        yield path, obj
        return
    head, rest = parts[0], parts[1:]
    if not isinstance(obj, dict):
        yield path or head, None
        return
    for key in (list(obj) if head == "*" else [head]):
        yield from _values(obj.get(key), rest, f"{path}.{key}" if path else str(key))


def _fields_problems(entry: Any, fields: tuple, path: str) -> list[str]:
    if not isinstance(entry, dict):
        return ["%s must be a mapping" % path]
    return ["%s.%s is missing or has the wrong type" % (path, name) for name, kind in fields
            if not isinstance(entry.get(name), kind)]


def _structure_problems(data: dict[str, Any]) -> list[str]:
    problems = ["%s is missing or has the wrong type" % path
                for pattern, kind in _STRUCTURE
                for path, value in _values(data, pattern.split("."))
                if not isinstance(value, kind)]
    if problems:
        return problems
    for name, prov in data["providers"].items():
        if prov.get("builtin"):
            continue
        problems.extend(_fields_problems(prov, _PROVIDER_FIELDS, f"providers.{name}"))
        models = prov.get("models") if isinstance(prov.get("models"), list) else []
        for index, model in enumerate(models):
            problems.extend(_fields_problems(model, _MODEL_FIELDS, f"providers.{name}.models[{index}]"))
    for name, seat in data["seats"].items():
        if seat.get("heartbeat"):
            problems.extend(_fields_problems(seat["heartbeat"], _HEARTBEAT_FIELDS, f"seats.{name}.heartbeat"))
    return problems


def validate(data: dict[str, Any]) -> list[str]:
    """Return a list of problems; an empty list means the defaults satisfy every invariant."""
    problems: list[str] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        problems.append("schema_version must be %d" % SCHEMA_VERSION)
    for key in ("providers", "chain", "seats", "human_gated_models", "manual_only"):
        if key not in data:
            problems.append("missing required section: %s" % key)
    if problems:
        return problems

    # secrets: names only. Checked before the structure, so a credential is reported whatever else is wrong.
    problems.extend(_secret_problems(data))
    shape = _structure_problems(data)
    if shape:
        return problems + shape

    gated = set(data["human_gated_models"])
    seats = data["seats"]

    # chains
    chains = {"default": chain_for(data)}
    for seat in seats:
        chains["seat:" + seat] = chain_for(data, seat)
    for label, chain in chains.items():
        for model in chain:
            if model.startswith("lmstudio-mac/"):
                problems.append("lmstudio-mac in chain %s: Mac LM Studio is manual-only and in no chain" % label)
        if label == "default" or label.startswith("seat:"):
            if not any(m.startswith("wandb/") for m in chain):
                problems.append("W&B missing from chain %s: it is never removed from any agent's chain" % label)
    if data["chain"]["default"] and not data["chain"]["default"][0].startswith("wandb/"):
        problems.append("the default chain must start with the W&B model")
    for model in data["chain"]["default"]:
        if model in gated:
            problems.append("human-gated model %s is in the default chain" % model)
    for name, seat in seats.items():
        if seat["model"] in gated:
            problems.append("human-gated model %s is the default of seat %s" % (seat["model"], name))
        heartbeat_model = (seat.get("heartbeat") or {}).get("model")
        if heartbeat_model in gated:
            problems.append("human-gated model %s is the heartbeat of seat %s" % (heartbeat_model, name))
        missing = [t for t in REQUIRED_DENY if t not in seat.get("tools_deny", [])]
        if missing:
            problems.append("seat %s must deny %s" % (name, ", ".join(missing)))
        for target in seat.get("subagents_allow", []):
            if target not in seats:
                problems.append("seat %s allows unknown seat %s" % (name, target))

    local = {model for model in data["chain"]["default"] if _is_local_model(model)}
    for seat in seats.values():
        heartbeat = (seat.get("heartbeat") or {}).get("model", "")
        local.update(model for model in (seat["model"], heartbeat) if _is_local_model(model))
    if len(local) > 1:
        problems.append("routes may name only one local model (one barrel), found %s" % ", ".join(sorted(local)))

    for name, prov in data["manual_only"].items():
        if prov.get("enabled") is not False:
            problems.append("manual_only.%s must stay disabled (enabled: false)" % name)
    return problems


# ---------------------------------------------------------------------------------------------- render


def _secret_ref(env_name: str) -> dict[str, str]:
    return {"source": "env", "provider": "default", "id": env_name}


def _cost(cost: dict[str, Any]) -> dict[str, Any]:
    return {
        "input": cost.get("input", 0),
        "output": cost.get("output", 0),
        "cacheRead": cost.get("cache_read", 0),
        "cacheWrite": cost.get("cache_write", 0),
    }


def _provider_patch(prov: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"api": prov["api"], "baseUrl": prov["base_url"]}
    if "api_key_env" in prov:
        out["apiKey"] = _secret_ref(prov["api_key_env"])
    elif "api_key_placeholder" in prov:
        out["apiKey"] = prov["api_key_placeholder"]
    out["models"] = [
        {
            "id": m["id"],
            "name": m["name"],
            "reasoning": m["reasoning"],
            "input": m["input"],
            "contextWindow": m["context_window"],
            "maxTokens": m["max_tokens"],
            "cost": _cost(m.get("cost", {})),
        }
        for m in prov["models"]
    ]
    return out


def _seat_patch(data: dict[str, Any], name: str) -> dict[str, Any]:
    seat = data["seats"][name]
    chain = chain_for(data, name)
    entry: dict[str, Any] = {
        "description": seat["description"],
        "model": {"primary": chain[0], "fallbacks": chain[1:]},
        "thinkingDefault": seat["thinking"],
        "tools": {"deny": list(seat["tools_deny"])},
        "skills": list(seat["skills"]),
    }
    if seat.get("display_name"):
        entry["identity"] = {"name": seat["display_name"]}
    if seat.get("subagents_allow"):
        entry["subagents"] = {"allowAgents": list(seat["subagents_allow"])}
    hb = seat.get("heartbeat")
    if hb:
        entry["heartbeat"] = {
            "every": hb["every"],
            "model": hb["model"],
            "target": hb["target"],
            "lightContext": hb["light_context"],
            "isolatedSession": hb["isolated_session"],
            "prompt": hb["prompt"],
        }
    return entry


def render_patch(data: dict[str, Any], shape: str = "entries") -> dict[str, Any]:
    """The config patch for the staged restore. ``shape`` is ``entries`` (OpenClaw 2026.10.x) or ``list`` (older)."""
    if shape not in ("entries", "list"):
        raise ValueError("shape must be 'entries' or 'list'")
    default = chain_for(data)
    providers: dict[str, Any] = {}
    for name, prov in data["providers"].items():
        if prov.get("builtin"):
            if prov.get("runtime"):
                providers[name] = {"agentRuntime": {"id": prov["runtime"]}}
            continue
        providers[name] = _provider_patch(prov)
    aliases = {
        model: {k: v for k, v in {"alias": a["alias"], "params": a.get("params")}.items() if v is not None}
        for model, a in data["model_aliases"].items()
    }
    defaults = {
        "model": {"primary": default[0], "fallbacks": default[1:]},
        "thinkingDefault": data["thinking"]["default"],
        "models": aliases,
    }
    seats = {name: _seat_patch(data, name) for name in data["seats"]}
    agents: dict[str, Any] = {"defaults": defaults}
    if shape == "entries":
        agents["entries"] = seats
    else:
        agents["list"] = [{"id": name, **entry} for name, entry in seats.items()]
    update = data["baseline"]["update"]
    return {
        "models": {"mode": "merge", "providers": providers},
        "agents": agents,
        "plugins": {"entries": copy.deepcopy(data["plugins"])},
        "update": {"channel": update["channel"], "checkOnStart": update["check_on_start"], "auto": {"enabled": update["auto"]}},
        "env": {"shellEnv": {"enabled": data["env"]["shell_import"]["enabled"], "timeoutMs": data["env"]["shell_import"]["timeout_ms"]}},
    }


# ------------------------------------------------------------------------------------------------ drift


def _leaves(obj: Any, path: tuple[str, ...] = ()):
    """Yield (key tuple, value). Tuples, not dotted strings: model ids such as google/gemini-3.8-flash contain dots."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _leaves(v, (*path, k))
    else:
        yield path, obj


def _lookup(config: Any, path: tuple[str, ...]) -> Any:
    cur = config
    for part in path:
        if not isinstance(cur, dict) or part not in cur:
            return MISSING
        cur = cur[part]
    return cur


def _shown(path: str, value: Any) -> Any:
    if value == MISSING:
        return value
    under_key = any(SECRET_KEY.search(segment) for segment in path.split("."))
    if under_key or (isinstance(value, str) and SECRET_VALUE.search(value)):
        return REDACTED
    return value


def _index_by_id(obj: Any) -> Any:
    """Turn every list of dicts that all carry an id into a dict keyed by id, so extra fields OpenClaw adds to an
    entry (it normalizes model entries on write) are not mistaken for drift and lists compare entry by entry."""
    if isinstance(obj, dict):
        return {k: _index_by_id(v) for k, v in obj.items()}
    if isinstance(obj, list) and obj and all(isinstance(x, dict) and "id" in x for x in obj):
        return {x["id"]: _index_by_id({k: v for k, v in x.items() if k != "id"}) for x in obj}
    return obj


def drift(data: dict[str, Any], config: dict[str, Any], shape: str | None = None) -> list[dict[str, Any]]:
    """Read-only comparison of a config with the rendered defaults. Secret values are never reported."""
    if shape is None:
        shape = "list" if "list" in config.get("agents", {}) and "entries" not in config.get("agents", {}) else "entries"
    expected = _index_by_id(render_patch(data, shape=shape))
    config = _index_by_id(config)
    found = []
    for path, want in _leaves(expected):
        have = _lookup(config, path)
        if have != want:
            dotted = ".".join(path)
            found.append({"path": dotted, "expected": _shown(dotted, want), "actual": _shown(dotted, have)})
    return found


# ------------------------------------------------------------------------------- fingerprint and stamp


def _canonical(data: dict[str, Any]) -> str:
    body = {k: v for k, v in data.items() if k != "_vendor"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(data: dict[str, Any]) -> str:
    """sha256 of the canonical content, independent of key order and of any vendor stamp."""
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def vendored_copy(data: dict[str, Any], now: datetime | None = None, module_source: str | None = None) -> str:
    """The text of a stamped copy for a consumer repository. Pure: it returns the text and writes nothing.

    When ``module_source`` is given, the stamp also records the hash of this module's source, because a consumer that
    cannot reach Perpetua-Tools runs the vendored module and must be able to tell it was not edited by hand."""
    now = now or datetime.now(timezone.utc)
    out = {k: v for k, v in data.items() if k != "_vendor"}
    stamp = {
        "source": "perpetua-tools config/openclaw-defaults.json",
        "source_sha256": fingerprint(data),
        "source_updated": data["updated"],
        "vendored_at": now.isoformat(),
        "note": "Generated copy. Never edit by hand; re-sync it after a human confirms the diff.",
    }
    if module_source is not None:
        stamp["module_sha256"] = _sha256_text(module_source)
    out["_vendor"] = stamp
    return json.dumps(out, indent=2, ensure_ascii=False) + "\n"


def _utc(moment: datetime) -> datetime:
    """A time without an offset is read as UTC, which is what the stamp writes."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def verify_vendored(
    text: str,
    live_fingerprint: str | None = None,
    now: datetime | None = None,
    max_age_days: int = 30,
    module_source: str | None = None,
) -> dict[str, str]:
    """Judge a vendored copy: ok, stale (live file moved on), old (cannot verify), tampered or invalid."""
    now = _utc(now or datetime.now(timezone.utc))
    try:
        obj = json.loads(text)
        stamp = obj["_vendor"]
        source = stamp["source_sha256"]
        vendored_at = _utc(datetime.fromisoformat(stamp["vendored_at"]))
    except (ValueError, KeyError, TypeError):
        return {"status": "invalid", "message": "the vendored OpenClaw defaults have no readable stamp; do not use them"}
    if fingerprint(obj) != source:
        return {"status": "tampered", "message": "the vendored OpenClaw defaults were edited by hand (fingerprint mismatch); do not use them"}
    if module_source is not None:
        recorded = stamp.get("module_sha256")
        if recorded is None:
            return {"status": "invalid", "message": "the vendored stamp records no module hash, so the vendored module cannot be verified"}
        if recorded != _sha256_text(module_source):
            return {"status": "tampered", "message": "the vendored OpenClaw defaults module was edited by hand (hash mismatch); do not use it"}
    if live_fingerprint is not None and live_fingerprint != source:
        return {
            "status": "stale",
            "message": "the vendored OpenClaw defaults copy differs from the live Perpetua-Tools file; a human must confirm a sync",
        }
    if live_fingerprint is None:
        age = (now - vendored_at).days
        if age > max_age_days:
            return {
                "status": "old",
                "message": "the vendored OpenClaw defaults are %d days old and Perpetua-Tools is unreachable, so I cannot verify them" % age,
            }
    return {"status": "ok", "message": "vendored OpenClaw defaults verified"}


# ------------------------------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenClaw defaults: validate, render, check, fingerprint (read-only).")
    parser.add_argument("--data", help="path to the defaults file (default: the repository copy)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate", action="store_true")
    mode.add_argument("--render-patch", action="store_true")
    mode.add_argument("--check", metavar="CONFIG", help="compare a config file with the defaults (exit 1 on drift)")
    mode.add_argument("--fingerprint", action="store_true")
    mode.add_argument("--vendor-copy", action="store_true", help="print the stamped vendored copy; writes nothing")
    parser.add_argument("--shape", choices=("entries", "list"), default="entries")
    args = parser.parse_args(argv)

    data = load(args.data)
    if args.validate:
        problems = validate(data)
        print("\n".join(problems) if problems else "ok: the defaults satisfy every invariant")
        return 1 if problems else 0
    problems = validate(data)
    if problems:
        print("refusing: the defaults are invalid\n" + "\n".join(problems), file=sys.stderr)
        return 2
    if args.fingerprint:
        print(fingerprint(data))
        return 0
    if args.render_patch:
        print(json.dumps(render_patch(data, shape=args.shape), indent=2))
        return 0
    if args.vendor_copy:
        sys.stdout.write(vendored_copy(data))
        return 0
    with open(args.check, encoding="utf-8") as fh:
        config = json.load(fh)
    found = drift(data, config)
    for item in found:
        print("drift %s: expected %s, actual %s" % (item["path"], json.dumps(item["expected"]), json.dumps(item["actual"])))
    print("no drift" if not found else "%d drift item(s)" % len(found))
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
