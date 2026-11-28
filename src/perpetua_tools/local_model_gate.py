"""One barrel: at most one local model on this host, across every engine (stdlib only).

The double-barrel rule forbade sending one heavy model to two LM Studio endpoints that share a GPU. This
extends it: a host holds at most one local model, whatever the engine, embeddings included, and nothing
loads unless that can be shown to be true afterwards.

``ensure(engine, model)`` is idempotent. Under one exclusive lock it either finds the requested model already
alone, loads it onto an empty host with room for it, or refuses. It never unloads anything, and whatever it
cannot determine is a refusal. Rules live in ``config/local-model-gate.json``.

Nothing loads without a person's approval for that model (``approve``, typed in a terminal, with an expiry).
A request aimed at any other local port than the engine's own is refused, and while a test runs the real
engines refuse every request.

When another model holds the host, ``ensure`` waits a few seconds, looks once more, then raises
``LocalModelBusy``: the caller carries on without a local model (memory search falls back to keywords).
Only a person can change which model is loaded, with ``swap`` in a terminal.

    python -m perpetua_tools.local_model_gate status                      # read-only
    python -m perpetua_tools.local_model_gate check ollama <model>        # decision only, loads nothing
    python -m perpetua_tools.local_model_gate approve ollama <model>      # a person allows loads, in a terminal
    python -m perpetua_tools.local_model_gate revoke                      # withdraws every approval
    python -m perpetua_tools.local_model_gate ensure ollama <model>       # loads only if allowed and approved
    python -m perpetua_tools.local_model_gate swap ollama <model>         # a person confirms, in a terminal
    python -m perpetua_tools.local_model_gate limits [--apply]            # engine limits (macOS)

It protects callers that go through it. A program that calls an engine directly is bounded only by that
engine's own limits, which the gate requires to be in force before it loads anything.
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterator

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "local-model-gate.json"
SCHEMA_VERSION = 1
GIB = 1024**3
LOOPBACK_NAMES = {"localhost", "0.0.0.0", "::"}
RUNNER = re.compile(r"ollama runner|llama-server|llama-cli|llama-diffusion|mlx_lm|mlx_vlm|mlx-engine|llmster")


class LocalModelRefused(RuntimeError):
    """The request would break the one-model rule, or the rule could not be shown to hold."""


class LocalModelBusy(LocalModelRefused):
    """Another model holds the host. Carry on without a local model, or ask a person to swap."""

    def __init__(self, reason: str, held: str) -> None:
        super().__init__(reason)
        self.held = held


class LocalModelNotApproved(LocalModelRefused):
    """The load would be allowed, but no person has approved it."""


class SwapNotConfirmed(LocalModelRefused):
    """The person asked to confirm a swap or an approval did not."""


@dataclass(frozen=True)
class Loaded:
    engine: str
    model: str
    size: int | None = None


@dataclass(frozen=True)
class Snapshot:
    """What this host holds right now. ``unknown`` lists every reason the picture may be incomplete."""

    loaded: tuple[Loaded, ...] = ()
    unknown: tuple[str, ...] = ()
    stray_processes: tuple[str, ...] = ()
    gpu_allocated_bytes: int | None = None
    pressure_level: int | None = None
    available_bytes: int | None = None
    limit_problems: tuple[str, ...] = ()
    engines_down: tuple[str, ...] = ()


@dataclass(frozen=True)
class Decision:
    action: str  # already_loaded | load | loaded | needs_approval | busy | refuse | not_enforced | approved
    reason: str
    held: str = ""


# ------------------------------------------------------------------------------------------------- policy


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    with open(path or DEFAULT_CONFIG_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def validate_config(config: dict[str, Any]) -> list[str]:
    """Problems that would loosen the rule; an empty list means the config is acceptable."""
    problems: list[str] = []
    if config.get("schema_version") != SCHEMA_VERSION:
        problems.append("schema_version must be %d" % SCHEMA_VERSION)
    if config.get("max_loaded_models") != 1:
        problems.append("max_loaded_models must be 1")
    if config.get("never_evict") is not True:
        problems.append("never_evict must be true")
    if "darwin" not in config.get("enforce_on", []):
        problems.append("enforce_on must include darwin")
    conflict = config.get("conflict", {})
    if not 0 <= conflict.get("wait_seconds", -1) <= 60:
        problems.append("conflict.wait_seconds must be between 0 and 60")
    if conflict.get("swap") != "human_confirmed":
        problems.append("conflict.swap must be human_confirmed: only a person may change the loaded model")
    approval = config.get("approval", {})
    if approval.get("required") is not True or not approval.get("file"):
        problems.append("approval.required must be true, with a file to record approvals in")
    if not 1 <= approval.get("max_minutes", 0) <= 1440:
        problems.append("approval.max_minutes must be between 1 and 1440")
    if str(config.get("idle_unload", "")).startswith("-"):
        problems.append("idle_unload must not pin a model in memory")
    fit = config.get("fit", {})
    if not (fit.get("size_factor", 0) >= 1 and fit.get("reserve_gib", 0) >= 1):
        problems.append("fit must keep size_factor >= 1 and reserve_gib >= 1")
    engines = config.get("engines", {})
    for name, engine in engines.items():
        host = urllib.parse.urlsplit(engine.get("url", "")).hostname or ""
        if not is_local_host(host):
            problems.append("engines.%s.url must be an address of this host" % name)
    env = engines.get("ollama", {}).get("server_env", {})
    for key in ("OLLAMA_MAX_LOADED_MODELS", "OLLAMA_NUM_PARALLEL"):
        if env.get(key) != "1":
            problems.append("engines.ollama.server_env.%s must be \"1\"" % key)
    if engines.get("lm-studio", {}).get("automatic_loads") is not False:
        problems.append("engines.lm-studio.automatic_loads must be false: Mac LM Studio is manual use only")
    return problems


def normalize(engine: str, model: str) -> str:
    name = model.strip()
    if engine == "ollama":
        return name if ":" in name.rsplit("/", 1)[-1] else name + ":latest"
    return name.lower()


def is_local_host(host: str) -> bool:
    """True for loopback and for any address this machine itself holds."""
    if not host:
        return False
    if host.lower() in LOOPBACK_NAMES or host.lower() == socket.gethostname().lower():
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, 0))  # succeeds only for an address of this machine
        except OSError:
            return False
    return True


def needs_gate(url: str, model: str) -> bool:
    """True when the request would put model weights into this host's memory."""
    tag = model.rsplit("/", 1)[-1].partition(":")[2]
    if tag == "cloud" or tag.endswith("-cloud"):
        return False
    host = urllib.parse.urlsplit(url if "://" in url else "http://" + url).hostname
    return bool(host) and is_local_host(host)


def decide(config: dict[str, Any], engine: str, model: str, snapshot: Snapshot, size: int | None) -> Decision:
    """The rule as a pure function: already_loaded, load or refuse."""

    def refuse(reason: str) -> Decision:
        return Decision("refuse", reason)

    if snapshot.unknown:
        return refuse("cannot tell what is loaded: " + "; ".join(snapshot.unknown))
    if len(snapshot.loaded) > config["max_loaded_models"]:
        listed = ", ".join(f"{item.engine}:{item.model}" for item in snapshot.loaded)
        return refuse(f"the one-model rule is already broken, {len(snapshot.loaded)} models are loaded: {listed}")
    if snapshot.stray_processes:
        return refuse("model processes outside the engines' own listing: " + "; ".join(snapshot.stray_processes))
    if snapshot.loaded:
        held = snapshot.loaded[0]
        if held.engine == engine and normalize(engine, held.model) == normalize(engine, model):
            return Decision("already_loaded", f"{engine}:{model} is the one loaded model")
        name = f"{held.engine}:{held.model}"
        return Decision("busy", f"another model is loaded ({name}) and the gate does not unload it on its own", name)
    if engine in snapshot.engines_down:
        return refuse(f"{engine} is not running")
    if not config["engines"][engine].get("automatic_loads"):
        return refuse(f"{engine} is manual use only on this host: load it by hand or use another engine")
    if snapshot.limit_problems:
        return refuse("engine limit not in force: " + "; ".join(snapshot.limit_problems))
    fit = config["fit"]
    ceiling = fit["max_idle_gpu_allocated_gib"] * GIB
    if snapshot.gpu_allocated_bytes is None or snapshot.gpu_allocated_bytes > ceiling:
        held_gib = "unknown" if snapshot.gpu_allocated_bytes is None else f"{snapshot.gpu_allocated_bytes / GIB:.1f} GiB"
        return refuse(f"GPU memory is in use with no model listed, or cannot be read ({held_gib})")
    if snapshot.pressure_level != 1:
        return refuse(f"memory pressure is not normal (level {snapshot.pressure_level})")
    if snapshot.available_bytes is None:
        return refuse("available memory cannot be read")
    if size is None:
        return refuse(f"the size of {engine}:{model} is unknown")
    needed = size * fit["size_factor"] + fit["reserve_gib"] * GIB
    if needed > snapshot.available_bytes:
        return refuse(
            f"{engine}:{model} does not fit: needs about {needed / GIB:.1f} GiB with headroom, "
            f"{snapshot.available_bytes / GIB:.1f} GiB available"
        )
    return Decision("load", f"nothing is loaded and {engine}:{model} fits")


# ---------------------------------------------------------------------------------------------- approvals


class Approvals:
    """Which loads a person has allowed, and until when. Anything unreadable approves nothing."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(os.path.expanduser(str(path)))

    def _rows(self) -> list[dict[str, Any]]:
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict) and isinstance(row.get("engine"), str)
                and isinstance(row.get("model"), str) and isinstance(row.get("expires"), (int, float))]

    def allows(self, engine: str, model: str) -> bool:
        wanted = normalize(engine, model)
        return any(row["engine"] == engine and normalize(engine, row["model"]) == wanted
                   and row["expires"] > time.time() for row in self._rows())

    def _write(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=2)
        os.replace(temporary, self.path)

    def grant(self, engine: str, model: str, minutes: int) -> None:
        kept = [row for row in self._rows() if row["expires"] > time.time()
                and not (row["engine"] == engine and row["model"] == model)]
        self._write([*kept, {"engine": engine, "model": model, "expires": time.time() + minutes * 60}])

    def revoke(self) -> None:
        self._write([])


# --------------------------------------------------------------------------------------------------- gate


class Gate:
    def __init__(self, config: dict[str, Any], engines: Any, approvals: Any = None) -> None:
        self.config = config
        self.engines = engines
        self.approvals = approvals or Approvals(config.get("approval", {}).get("file", os.devnull))
        self.sleep: Callable[[float], None] = time.sleep

    @contextmanager
    def _lock(self) -> Iterator[None]:
        import fcntl  # POSIX only; the platform check keeps other systems away from here

        path = Path(os.path.expanduser(self.config["lock_file"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + float(self.config.get("lock_timeout_s", 600))
        with open(path, "a", encoding="utf-8") as handle:
            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() > deadline:
                        raise LocalModelRefused("another load has held the gate too long") from None
                    time.sleep(0.05)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _preflight(self, engine: str) -> Decision | None:
        problems = validate_config(self.config)
        if problems:
            return Decision("refuse", "config would loosen the rule: " + "; ".join(problems))
        if engine not in self.config["engines"]:
            return Decision("refuse", f"unknown engine {engine!r}")
        if self.engines.platform not in self.config["enforce_on"]:
            return Decision("not_enforced", f"the gate has no probes for {self.engines.platform}")
        return None

    def _decide(self, engine: str, model: str) -> Decision:
        snapshot = self.engines.snapshot()
        size = None if snapshot.loaded else self.engines.model_size(engine, model)
        return decide(self.config, engine, model, snapshot, size)

    def check(self, engine: str, model: str) -> Decision:
        """What ``ensure`` would do now. Loads nothing."""
        decision = self._preflight(engine) or self._decide(engine, model)
        if decision.action == "load" and not self.approvals.allows(engine, model):
            return Decision("needs_approval", self._how_to_approve(engine, model))
        return decision

    @staticmethod
    def _how_to_approve(engine: str, model: str) -> str:
        return (f"loading {engine}:{model} needs a person's approval; in a terminal run: "
                f"python -m perpetua_tools.local_model_gate approve {engine} {model}")

    def require(self, engine: str, model: str, url: str) -> Decision:
        """``ensure`` for a request about to be sent to ``url``, which must be the managed engine."""
        if getattr(self.engines, "under_test", False):
            raise LocalModelRefused("a test is running: the real engines take no requests")
        early = self._preflight(engine)
        if early is not None:
            if early.action == "refuse":
                raise LocalModelRefused(early.reason)
            return early
        target = urllib.parse.urlsplit(url if "://" in url else "http://" + url).port
        managed = urllib.parse.urlsplit(self.config["engines"][engine]["url"]).port
        if target != managed:
            raise LocalModelRefused(
                f"{url} is not the managed endpoint of {engine} (port {managed}); the gate loads nowhere else")
        return self.ensure(engine, model)

    def ensure(self, engine: str, model: str) -> Decision:
        """Make ``model`` the one loaded model, or raise. Idempotent; never unloads.

        A host held by another model is looked at once more after ``conflict.wait_seconds``, outside the lock,
        and then reported as ``LocalModelBusy``.
        """
        early = self._preflight(engine)
        if early is not None:
            if early.action == "refuse":
                raise LocalModelRefused(early.reason)
            return early
        decision = self._attempt(engine, model)
        if decision.action == "busy":
            self.sleep(self.config["conflict"]["wait_seconds"])
            decision = self._attempt(engine, model)
        if decision.action == "busy":
            raise LocalModelBusy(
                f"{decision.reason}. Carry on without it, or a person can run: "
                f"python -m perpetua_tools.local_model_gate swap {engine} {model}", decision.held)
        return decision

    def _attempt(self, engine: str, model: str) -> Decision:
        with self._lock():
            decision = self._decide(engine, model)
            if decision.action == "refuse":
                raise LocalModelRefused(decision.reason)
            if decision.action != "load":
                return decision
            if not self.approvals.allows(engine, model):
                raise LocalModelNotApproved(self._how_to_approve(engine, model))
            return self._load_and_verify(engine, model)

    def _load_and_verify(self, engine: str, model: str) -> Decision:
        self.engines.load(engine, model, self.config["idle_unload"])
        after = self.engines.snapshot().loaded
        if not (len(after) == 1 and after[0].engine == engine
                and normalize(engine, after[0].model) == normalize(engine, model)):
            listed = ", ".join(f"{item.engine}:{item.model}" for item in after) or "nothing"
            raise LocalModelRefused(f"after loading, expected only {engine}:{model} but found {listed}")
        return Decision("loaded", f"{engine}:{model} is now the one loaded model")

    def swap(self, engine: str, model: str, confirm: Callable[[str, str], bool]) -> Decision:
        """Replace the loaded model with ``model`` after a person confirms. Only the ``swap`` command calls this.

        Everything that can be checked is checked before asking and again under the lock; the old model is
        unloaded only if the new one would then be allowed to load, and the new one loads only once the host
        is seen to be empty.
        """
        early = self._preflight(engine)
        if early is not None:
            if early.action == "refuse":
                raise LocalModelRefused(early.reason)
            return early
        held, decision = self._plan_swap(engine, model)
        if held is None:
            return self.ensure(engine, model) if decision.action == "load" else decision
        if not confirm(f"{held.engine}:{held.model}", f"{engine}:{model}"):
            raise SwapNotConfirmed("the swap was not confirmed; nothing changed")
        with self._lock():
            now_held, decision = self._plan_swap(engine, model)
            if now_held != held:
                raise LocalModelRefused("the loaded model changed while waiting for confirmation; nothing changed")
            self.engines.unload(held.engine, held.model)
            for _ in range(60):
                seen = self.engines.snapshot()
                if not seen.loaded and not seen.stray_processes:  # the old runner has exited too
                    break
                self.sleep(0.5)
            else:
                raise LocalModelRefused(f"{held.engine}:{held.model} is still loaded; nothing else was loaded")
            decision = self._decide(engine, model)
            if decision.action != "load":
                raise LocalModelRefused(f"the host is empty but the load is not allowed: {decision.reason}")
            return self._load_and_verify(engine, model)

    def _plan_swap(self, engine: str, model: str) -> tuple[Loaded | None, Decision]:
        """The model a swap would unload, after proving the new one would be allowed once it is gone."""
        snapshot = self.engines.snapshot()
        if len(snapshot.loaded) != 1:
            decision = self._decide(engine, model)
            if decision.action != "load" and decision.action != "already_loaded":
                raise LocalModelRefused(decision.reason)
            return None, decision
        held = snapshot.loaded[0]
        current = decide(self.config, engine, model, snapshot, None)
        if current.action == "already_loaded":
            return None, current
        if current.action != "busy":
            raise LocalModelRefused(current.reason)
        released = held.size or 0
        emptied = replace(
            snapshot, loaded=(),
            gpu_allocated_bytes=None if snapshot.gpu_allocated_bytes is None
            else max(snapshot.gpu_allocated_bytes - released, 0),
            available_bytes=None if snapshot.available_bytes is None else snapshot.available_bytes + released,
        )
        after = decide(self.config, engine, model, emptied, self.engines.model_size(engine, model))
        if after.action != "load":
            raise LocalModelRefused(after.reason)
        return held, after


# --------------------------------------------------------------------------------------------- real host


class SystemEngines:
    """Read-only probes of this machine, plus the single load call each engine offers."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.platform = sys.platform
        self.under_test = bool(os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("PYTEST_VERSION"))

    def _url(self, engine: str) -> str:
        return self.config["engines"][engine]["url"].rstrip("/")

    @staticmethod
    def _run(*command: str) -> str | None:
        try:
            done = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        return done.stdout if done.returncode == 0 else None

    def _request(self, engine: str, path: str, body: dict[str, Any] | None = None, timeout: float = 5.0) -> Any:
        if self.under_test:
            raise LocalModelRefused("a test is running: the real engines take no requests")
        headers = {"Content-Type": "application/json"}
        token = os.getenv("LM_STUDIO_API_TOKEN") or os.getenv("LM_API_TOKEN")
        if engine == "lm-studio" and token:
            headers["Authorization"] = f"Bearer {token}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(self._url(engine) + path, data=data, headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never through a proxy
        with opener.open(request, timeout=timeout) as response:
            return json.loads(response.read() or b"{}")

    def _inventory(self, engine: str, path: str) -> Any:
        try:
            return self._request(engine, path)
        except (OSError, ValueError, LocalModelRefused):
            return None

    def _processes(self) -> list[tuple[int, str]] | None:
        out = self._run("ps", "-axo", "pid=,command=")
        if out is None:
            return None
        rows = (line.strip().partition(" ") for line in out.splitlines())
        return [(int(pid), command.strip()) for pid, _, command in rows if pid.isdigit()]

    @staticmethod
    def _is_ollama_server(command: str) -> bool:
        return bool(re.search(r"(^|/)ollama serve\b", command))

    @staticmethod
    def _is_lmstudio(command: str) -> bool:
        return "LM Studio.app/" in command or "/.lmstudio/" in command or "llmster" in command

    def snapshot(self) -> Snapshot:
        loaded: list[Loaded] = []
        unknown: list[str] = []
        strays: list[str] = []
        down: list[str] = []
        processes = self._processes()
        if processes is None:
            unknown.append("the process list cannot be read")
            processes = []

        server_pids = [pid for pid, command in processes if self._is_ollama_server(command)]
        listing = self._inventory("ollama", "/api/ps")
        ollama_count = 0
        if listing is None:
            if server_pids:
                unknown.append("Ollama is running but did not answer")
            down.append("ollama")
        elif not isinstance(listing.get("models"), list):
            unknown.append("Ollama answered in an unexpected shape")
        else:
            rows = [(row.get("name") or row.get("model") or "?", row.get("size")) for row in listing["models"]]
            ollama_count = len(rows)
            loaded += [Loaded("ollama", name, size) for name, size in rows]

        studio = self._inventory("lm-studio", "/api/v1/models")
        studio_running = any(self._is_lmstudio(command) for _, command in processes)
        if studio is None:
            if studio_running:
                unknown.append("LM Studio is running but its server did not answer")
            down.append("lm-studio")
        elif not isinstance(studio.get("models"), list):
            unknown.append("LM Studio answered in an unexpected shape")
        else:
            loaded += [Loaded("lm-studio", row.get("key", "?"), row.get("size_bytes")) for row in studio["models"]
                       if row.get("loaded_instances")]

        ollama_runners = 0
        for _, command in processes:
            runner = RUNNER.search(command)
            if runner is None:
                continue
            if "ollama" in command.lower():
                ollama_runners += 1
            elif not self._is_lmstudio(command):
                strays.append(runner.group())
        if ollama_runners > ollama_count:
            strays.append(f"{ollama_runners} Ollama runner process(es) but {ollama_count} listed, a load may be in progress")

        available, pressure = self._memory()
        return Snapshot(
            loaded=tuple(loaded), unknown=tuple(unknown), stray_processes=tuple(strays),
            gpu_allocated_bytes=self._gpu_allocated(), pressure_level=pressure, available_bytes=available,
            limit_problems=tuple(self._limit_problems(server_pids, studio_running)), engines_down=tuple(down),
        )

    def _memory(self) -> tuple[int | None, int | None]:
        total = self._run("sysctl", "-n", "hw.memsize")
        report = self._run("memory_pressure", "-Q")
        level = self._run("sysctl", "-n", "kern.memorystatus_vm_pressure_level")
        free = re.search(r"free percentage:\s*(\d+)%", report or "")
        available = int(total) * int(free.group(1)) // 100 if total and free else None
        return available, int(level) if level and level.strip().isdigit() else None

    def _gpu_allocated(self) -> int | None:
        report = self._run("ioreg", "-r", "-d", "1", "-w", "0", "-c", "IOAccelerator")
        values = [int(value) for value in re.findall(r'"Alloc system memory"=(\d+)', report or "")]
        return max(values) if values else None

    def _limit_problems(self, server_pids: list[int], studio_running: bool) -> list[str]:
        problems: list[str] = []
        wanted = self.config["engines"]["ollama"].get("server_env", {})
        for pid in server_pids:
            # The server's environment can hold secrets: only the configured names are read out of it.
            report = self._run("ps", "eww", "-o", "command=", "-p", str(pid)) or ""
            for key, value in wanted.items():
                found = re.search(rf"(?:^|\s){key}=(\S*)", report)
                if found is None or found.group(1) != value:
                    problems.append(f"{key} is not {value} in the running Ollama server")
        if studio_running:
            required = self.config["engines"]["lm-studio"].get("required_settings", {})
            try:
                settings = json.loads((Path.home() / ".lmstudio" / "settings.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                settings = {}
            for dotted, value in required.items():
                current: Any = settings
                for part in dotted.split("."):
                    current = current.get(part) if isinstance(current, dict) else None
                if current != value:
                    problems.append(f"LM Studio setting {dotted} is not {value}")
        return problems

    def model_size(self, engine: str, model: str) -> int | None:
        if engine == "ollama":
            listing = self._inventory(engine, "/api/tags") or {}
            sizes = {normalize(engine, row.get("name", "")): row.get("size") for row in listing.get("models", [])}
        else:
            listing = self._inventory(engine, "/api/v1/models") or {}
            sizes = {normalize(engine, row.get("key", "")): row.get("size_bytes") for row in listing.get("models", [])}
        return sizes.get(normalize(engine, model))

    def unload(self, engine: str, model: str) -> None:
        try:
            if engine != "ollama":
                listing = self._request(engine, "/api/v1/models")
                for row in listing.get("models", []):
                    if normalize(engine, row.get("key", "")) == normalize(engine, model):
                        for instance in row.get("loaded_instances", []):
                            self._request(engine, "/api/v1/models/unload", {"instance_id": instance["id"]}, 60)
                return
            try:
                self._request(engine, "/api/generate", {"model": model, "keep_alive": 0, "stream": False}, 60)
            except urllib.error.HTTPError as exc:
                if b"does not support generate" not in exc.read():
                    raise
                self._request(engine, "/api/embed", {"model": model, "input": " ", "keep_alive": 0}, 60)
        except (OSError, ValueError, KeyError) as exc:
            raise LocalModelRefused(f"{engine} could not unload {model}: {type(exc).__name__}") from exc

    def load(self, engine: str, model: str, idle_unload: str) -> None:
        try:
            if engine != "ollama":
                self._request(engine, "/api/v1/models/load", {"model": model}, timeout=600)
                return
            try:
                self._request(engine, "/api/generate", {"model": model, "keep_alive": idle_unload, "stream": False}, 600)
            except urllib.error.HTTPError as exc:
                if b"does not support generate" not in exc.read():
                    raise
                self._request(engine, "/api/embed", {"model": model, "input": " ", "keep_alive": idle_unload}, 600)
        except (OSError, ValueError) as exc:
            raise LocalModelRefused(f"{engine} could not load {model}: {type(exc).__name__}") from exc


# -------------------------------------------------------------------------------------------- call sites


def default_gate() -> Gate:
    config = load_config()
    return Gate(config, SystemEngines(config))


def require_local_slot(engine: str, model: str, url: str) -> Decision | None:
    """Call before any request that may load a model. Remote hosts and cloud models pass untouched."""
    if not needs_gate(url, model):
        return None
    return default_gate().require(engine, model, url)


async def require_local_slot_async(engine: str, model: str, url: str) -> Decision | None:
    return await asyncio.to_thread(require_local_slot, engine, model, url)


# ---------------------------------------------------------------------------------------------------- CLI


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _approve(gate: Gate, engine: str, model: str, minutes: int) -> int:
    if not _is_interactive():
        print("refusing: an approval needs a person at a terminal for both input and output", file=sys.stderr)
        return 5
    ceiling = gate.config["approval"]["max_minutes"]
    if engine not in gate.config["engines"] or not 1 <= minutes <= ceiling:
        print(f"refusing: name a known engine and between 1 and {ceiling} minutes", file=sys.stderr)
        return 3
    phrase = f"approve {engine}:{model} for {minutes} minutes"
    print(f"This lets the gate load {engine}:{model} on this machine until the approval expires.")
    if input(f"Type exactly `{phrase}` to continue: ").strip() != phrase:
        print("not approved; nothing changed")
        return 4
    gate.approvals.grant(engine, model, minutes)
    print(f"approved for {minutes} minutes")
    return 0


def _ask_to_swap(held: str, wanted: str) -> bool:
    phrase = f"swap {held} for {wanted}"
    print(f"{held} will be unloaded and {wanted} loaded. Anything using {held} will be interrupted.")
    return input(f"Type exactly `{phrase}` to continue: ").strip() == phrase


def _apply_limits(config: dict[str, Any], apply: bool) -> int:
    if sys.platform != "darwin":
        print("limits are applied through launchctl, which exists only on macOS")
        return 2
    for key, value in config["engines"]["ollama"]["server_env"].items():
        if apply:
            subprocess.run(["launchctl", "setenv", key, value], check=True, timeout=10)
        print(("set " if apply else "would set ") + f"{key}={value}")
    print("restart Ollama so the running server picks these up; they last until the next reboot")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One local model at a time.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="what this host holds now (read-only)")
    for name in ("check", "ensure", "swap"):
        sub = commands.add_parser(name)
        sub.add_argument("engine")
        sub.add_argument("model")
    commands.add_parser("limits", help="engine limits").add_argument("--apply", action="store_true")
    approve = commands.add_parser("approve", help="allow one model to be loaded for a while (a person, in a terminal)")
    approve.add_argument("engine")
    approve.add_argument("model")
    approve.add_argument("--minutes", type=int, default=60)
    commands.add_parser("revoke", help="withdraw every approval")
    args = parser.parse_args(argv)

    if args.command == "limits":
        config = load_config()
        problems = validate_config(config)
        if problems:
            print("refusing: " + "; ".join(problems), file=sys.stderr)
            return 3
        return _apply_limits(config, args.apply)
    gate = default_gate()
    if args.command == "revoke":
        gate.approvals.revoke()
        print("every approval is withdrawn")
        return 0
    if args.command == "approve":
        return _approve(gate, args.engine, args.model, args.minutes)
    if args.command == "status":
        print(json.dumps(asdict(gate.engines.snapshot()), indent=2))
        return 0
    code = 0
    try:
        if args.command == "swap":
            if not _is_interactive():
                print("refusing: a swap needs a person at a terminal for both input and output", file=sys.stderr)
                return 5
            decision = gate.swap(args.engine, args.model, _ask_to_swap)
        else:
            decision = getattr(gate, args.command)(args.engine, args.model)
    except SwapNotConfirmed as exc:
        decision, code = Decision("refuse", str(exc)), 4
    except LocalModelBusy as exc:
        decision = Decision("busy", str(exc), exc.held)
    except LocalModelRefused as exc:
        decision = Decision("refuse", str(exc))
    print(json.dumps(asdict(decision)))
    return code or (3 if decision.action in ("refuse", "busy", "needs_approval") else 0)


if __name__ == "__main__":
    raise SystemExit(main())
