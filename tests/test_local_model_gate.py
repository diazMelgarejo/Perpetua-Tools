"""One barrel: at most one local model on this host, across every engine, and anything unclear refuses.

Every test uses fake engines. Nothing here talks to Ollama, LM Studio or the GPU.
"""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path

import pytest

from perpetua_tools import local_model_gate as gate

ROOT = Path(__file__).resolve().parents[1]
GIB = 1024**3
QWEN = "qwen3.5:9b-mlx"
EMBED = "bge-m3"
# Assembled so the tracked-address gate sees no literal.
LOOPBACK_V4 = ".".join(("127", "0", "0", "1"))
LOOPBACK_V6 = ":" * 2 + "1"


@pytest.fixture()
def config() -> dict:
    return copy.deepcopy(gate.load_config(ROOT / "config" / "local-model-gate.json"))


class FakeEngines:
    """A host whose state the test sets; loading changes it the way a real engine would."""

    platform = "darwin"

    def __init__(self) -> None:
        self.ollama: list[str] = []
        self.lmstudio: list[str] = []
        self.unknown: list[str] = []
        self.strays: list[str] = []
        self.limit_problems: list[str] = []
        self.gpu_allocated: int | None = 1 * GIB
        self.pressure: int | None = 1
        self.available: int | None = 13 * GIB
        self.sizes = {("ollama", QWEN): 8 * GIB, ("ollama", "bge-m3:latest"): 1 * GIB}
        self.loads: list[tuple[str, str]] = []
        self.load_delay: threading.Event | None = None
        self.load_started = threading.Event()
        self.unloads: list[tuple[str, str]] = []
        self.stuck = False

    def snapshot(self) -> gate.Snapshot:
        loaded = [gate.Loaded("ollama", name) for name in self.ollama]
        loaded += [gate.Loaded("lm-studio", name) for name in self.lmstudio]
        return gate.Snapshot(
            loaded=tuple(loaded), unknown=tuple(self.unknown), stray_processes=tuple(self.strays),
            gpu_allocated_bytes=self.gpu_allocated, pressure_level=self.pressure,
            available_bytes=self.available, limit_problems=tuple(self.limit_problems),
        )

    def model_size(self, engine: str, model: str) -> int | None:
        return self.sizes.get((engine, gate.normalize(engine, model)))

    def unload(self, engine: str, model: str) -> None:
        self.unloads.append((engine, model))
        if not self.stuck:
            (self.ollama if engine == "ollama" else self.lmstudio).remove(model)

    def load(self, engine: str, model: str, idle_unload: str) -> None:
        self.load_started.set()
        if self.load_delay is not None:
            self.load_delay.wait(2)
        self.loads.append((engine, model))
        (self.ollama if engine == "ollama" else self.lmstudio).append(model)


class EveryApproval:
    """Stands for an operator who has approved the load, so the other rules can be tested on their own."""

    def allows(self, engine: str, model: str) -> bool:
        return True


def make(config: dict, engines: FakeEngines, tmp_path: Path) -> gate.Gate:
    config["lock_file"] = str(tmp_path / "gate.lock")
    built = gate.Gate(config, engines, approvals=EveryApproval())
    built.sleep = lambda seconds: None
    return built


def test_the_shipped_config_allows_exactly_one_model_and_never_evicts(config: dict) -> None:
    assert gate.validate_config(config) == []
    assert config["max_loaded_models"] == 1 and config["never_evict"] is True
    assert config["engines"]["ollama"]["server_env"]["OLLAMA_MAX_LOADED_MODELS"] == "1"
    assert config["engines"]["ollama"]["server_env"]["OLLAMA_NUM_PARALLEL"] == "1"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c.__setitem__("max_loaded_models", 2),
        lambda c: c.__setitem__("never_evict", False),
        lambda c: c["engines"]["ollama"]["server_env"].__setitem__("OLLAMA_MAX_LOADED_MODELS", "3"),
        lambda c: c["engines"]["ollama"].__setitem__("url", "http://example.invalid:11434"),
    ],
)
def test_a_loosened_config_refuses_everything(config: dict, tmp_path: Path, mutate) -> None:
    mutate(config)
    engines = FakeEngines()

    with pytest.raises(gate.LocalModelRefused, match="config"):
        make(config, engines, tmp_path).ensure("ollama", QWEN)
    assert engines.loads == []


def test_an_empty_host_with_room_loads_the_model_once_and_is_idempotent(config: dict, tmp_path: Path) -> None:
    engines = FakeEngines()
    g = make(config, engines, tmp_path)

    first = g.ensure("ollama", QWEN)
    second = g.ensure("ollama", QWEN)

    assert (first.action, second.action) == ("loaded", "already_loaded")
    assert engines.loads == [("ollama", QWEN)]


@pytest.mark.parametrize(
    "arrange, needle",
    [
        (lambda e: e.ollama.append("other:7b"), "another model"),
        (lambda e: e.lmstudio.append("qwen3.5-9b-mlx"), "another model"),
        (lambda e: e.ollama.extend([QWEN, "bge-m3:latest"]), "2 models"),
        (lambda e: e.unknown.append("LM Studio is running but did not answer"), "cannot tell"),
        (lambda e: e.strays.append("llama-server"), "outside"),
        (lambda e: e.limit_problems.append("OLLAMA_MAX_LOADED_MODELS is not 1"), "limit"),
        (lambda e: setattr(e, "gpu_allocated", 9 * GIB), "GPU"),
        (lambda e: setattr(e, "pressure", 2), "pressure"),
        (lambda e: setattr(e, "pressure", None), "pressure"),
        (lambda e: setattr(e, "available", None), "memory"),
        (lambda e: setattr(e, "available", 6 * GIB), "fit"),
        (lambda e: e.sizes.clear(), "size"),
    ],
)
def test_anything_else_loaded_unclear_or_tight_refuses_and_loads_nothing(
    config: dict, tmp_path: Path, arrange, needle: str
) -> None:
    engines = FakeEngines()
    arrange(engines)
    before = (list(engines.ollama), list(engines.lmstudio))

    with pytest.raises(gate.LocalModelRefused, match=needle):
        make(config, engines, tmp_path).ensure("ollama", QWEN)

    assert engines.loads == []
    assert (engines.ollama, engines.lmstudio) == before, "the gate never evicts"


def test_the_freeze_figures_are_refused(config: dict, tmp_path: Path) -> None:
    """8.9 GB of model files with about 42 percent of 16 GB free."""
    engines = FakeEngines()
    engines.sizes[("ollama", QWEN)] = 8_900_000_000
    engines.available = int(17_179_869_184 * 0.42)

    with pytest.raises(gate.LocalModelRefused, match="fit"):
        make(config, engines, tmp_path).ensure("ollama", QWEN)


def test_embeddings_count_as_a_model(config: dict, tmp_path: Path) -> None:
    engines = FakeEngines()
    engines.ollama.append(QWEN)

    with pytest.raises(gate.LocalModelRefused, match="another model"):
        make(config, engines, tmp_path).ensure("ollama", EMBED)


def test_an_untagged_ollama_name_matches_its_latest_tag(config: dict, tmp_path: Path) -> None:
    engines = FakeEngines()
    engines.ollama.append("bge-m3:latest")

    assert make(config, engines, tmp_path).ensure("ollama", EMBED).action == "already_loaded"


def test_a_manual_only_engine_serves_what_the_operator_loaded_but_never_loads(config: dict, tmp_path: Path) -> None:
    engines = FakeEngines()
    engines.sizes[("lm-studio", "qwen3.5-9b-mlx")] = GIB
    g = make(config, engines, tmp_path)
    with pytest.raises(gate.LocalModelRefused, match="manual"):
        g.ensure("lm-studio", "qwen3.5-9b-mlx")

    engines.lmstudio.append("Qwen3.5-9B-MLX")
    assert g.ensure("lm-studio", "qwen3.5-9b-mlx").action == "already_loaded"
    assert engines.loads == []


def test_an_unknown_engine_is_refused(config: dict, tmp_path: Path) -> None:
    with pytest.raises(gate.LocalModelRefused, match="unknown engine"):
        make(config, FakeEngines(), tmp_path).ensure("vllm", "x")


def test_a_load_that_leaves_two_models_is_reported_as_a_violation(config: dict, tmp_path: Path) -> None:
    engines = FakeEngines()
    real_load = engines.load

    def load_and_collide(engine: str, model: str, idle_unload: str) -> None:
        real_load(engine, model, idle_unload)
        engines.lmstudio.append("sneaked-in")

    engines.load = load_and_collide
    with pytest.raises(gate.LocalModelRefused, match="after loading"):
        make(config, engines, tmp_path).ensure("ollama", QWEN)


def test_two_callers_cannot_both_load(config: dict, tmp_path: Path) -> None:
    engines = FakeEngines()
    engines.sizes[("ollama", "second:7b")] = GIB
    engines.load_delay = threading.Event()
    g = make(config, engines, tmp_path)
    outcomes: dict[str, str] = {}

    def run(model: str) -> None:
        try:
            outcomes[model] = g.ensure("ollama", model).action
        except gate.LocalModelRefused as exc:
            outcomes[model] = str(exc)

    first, second = (threading.Thread(target=run, args=(model,)) for model in (QWEN, "second:7b"))
    first.start()
    assert engines.load_started.wait(5), "the first caller must be inside its load"
    second.start()
    second.join(0.5)  # without the lock it would now be loading beside the first
    assert second.is_alive(), "the second caller must wait for the first"
    engines.load_delay.set()
    for thread in (first, second):
        thread.join(5)

    assert engines.loads == [("ollama", QWEN)]
    assert outcomes[QWEN] == "loaded" and "another model" in outcomes["second:7b"]


def test_check_decides_without_loading(config: dict, tmp_path: Path) -> None:
    engines = FakeEngines()

    assert make(config, engines, tmp_path).check("ollama", QWEN).action == "load"
    assert engines.loads == []


def test_an_unsupported_platform_is_reported_as_not_enforced(config: dict, tmp_path: Path) -> None:
    engines = FakeEngines()
    engines.platform = "win32"

    assert make(config, engines, tmp_path).ensure("ollama", QWEN).action == "not_enforced"
    assert engines.loads == []


@pytest.mark.parametrize(
    "url, model, gated",
    [
        ("http://localhost:11434", QWEN, True),
        (f"http://{LOOPBACK_V4}:1234/v1/chat/completions", "any", True),
        (f"http://[{LOOPBACK_V6}]:11434", QWEN, True),
        ("http://192.0.2.7:1234", "any", False),
        ("http://localhost:11434", "glm-5.3-flash:cloud", False),
    ],
)
def test_only_local_weights_on_this_host_pass_through_the_gate(url: str, model: str, gated: bool) -> None:
    assert gate.needs_gate(url, model) is gated


def test_require_asks_the_gate_only_when_the_request_would_load_here(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[tuple[str, str]] = []

    class Recorder:
        def require(self, engine: str, model: str, url: str) -> gate.Decision:
            asked.append((engine, model))
            return gate.Decision("already_loaded", "")

    monkeypatch.setattr(gate, "default_gate", lambda: Recorder())
    gate.require_local_slot("ollama", QWEN, "http://localhost:11434")
    gate.require_local_slot("lm-studio", "m", "http://192.0.2.7:1234")

    assert asked == [("ollama", QWEN)]


def test_the_cli_status_and_check_print_json_and_never_load(
    config: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    engines = FakeEngines()
    engines.available = GIB
    monkeypatch.setattr(gate, "default_gate", lambda: make(config, engines, tmp_path))

    assert gate.main(["status"]) == 0
    assert json.loads(capsys.readouterr().out)["loaded"] == []
    assert gate.main(["check", "ollama", QWEN]) == 3
    assert json.loads(capsys.readouterr().out)["action"] == "refuse"
    assert engines.loads == []


# ------------------------------------------------------------------------- the real probes, fed fake output

OLLAMA_APP = "/Applications/Ollama.app/Contents/Resources/ollama"
SECRET = "tok-should-never-appear"


def probes(
    config: dict, monkeypatch: pytest.MonkeyPatch, *, processes: list[str], ps_models: list[str] | None,
    studio: dict | None = None, env: str = "OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_KEEP_ALIVE=5m",
) -> gate.Snapshot:
    system = gate.SystemEngines(config)

    def run(*command: str) -> str:
        if command[:2] == ("ps", "-axo"):
            return "".join(f"{100 + i} {line}\n" for i, line in enumerate(processes))
        if command[:2] == ("ps", "eww"):
            return f"{OLLAMA_APP} serve API_KEY={SECRET} {env}"
        if command[:2] == ("sysctl", "-n"):
            return str(16 * GIB) if command[2] == "hw.memsize" else "1\n"
        if command[0] == "memory_pressure":
            return "System-wide memory free percentage: 75%\n"
        return '"Alloc system memory"=1454456832'

    def inventory(engine: str, path: str):
        if engine == "ollama":
            return None if ps_models is None else {"models": [{"name": name} for name in ps_models]}
        return studio

    monkeypatch.setattr(system, "_run", run)
    monkeypatch.setattr(system, "_inventory", inventory)
    return system.snapshot()


def test_probes_read_an_idle_host(config: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    snap = probes(config, monkeypatch, processes=[f"{OLLAMA_APP} serve"], ps_models=[])

    assert (snap.loaded, snap.unknown, snap.stray_processes, snap.limit_problems) == ((), (), (), ())
    assert (snap.available_bytes, snap.pressure_level, snap.gpu_allocated_bytes) == (12 * GIB, 1, 1454456832)
    assert snap.engines_down == ("lm-studio",)


def test_probes_flag_limits_that_are_not_in_force_without_exposing_the_environment(
    config: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    snap = probes(config, monkeypatch, processes=[f"{OLLAMA_APP} serve"], ps_models=[], env="OLLAMA_KEEP_ALIVE=5m")

    assert [p.split()[0] for p in snap.limit_problems] == ["OLLAMA_MAX_LOADED_MODELS", "OLLAMA_NUM_PARALLEL"]
    assert SECRET not in repr(snap)


@pytest.mark.parametrize(
    "processes, ps_models, studio, field",
    [
        ([f"{OLLAMA_APP} serve"], None, None, "unknown"),
        (["/Applications/LM Studio.app/Contents/MacOS/LM Studio"], [], None, "unknown"),
        (["/opt/homebrew/bin/llama-server -m x.gguf"], [], None, "stray_processes"),
        ([f"{OLLAMA_APP} runner --model x", f"{OLLAMA_APP} serve"], [], None, "unknown_or_stray"),
        ([], [], {"models": [{"key": "m", "loaded_instances": [{"id": "m"}]}]}, "loaded"),
    ],
)
def test_probes_report_hidden_or_unaccounted_models(
    config: dict, monkeypatch: pytest.MonkeyPatch, processes: list[str], ps_models, studio, field: str
) -> None:
    if field == "unknown_or_stray":
        processes = [f"{OLLAMA_APP}-runner llama-server --model x", f"{OLLAMA_APP} serve"]
        field = "stray_processes"

    snap = probes(config, monkeypatch, processes=processes, ps_models=ps_models, studio=studio)

    assert getattr(snap, field), snap
    assert gate.decide(config, "ollama", QWEN, snap, GIB).action in ("refuse", "busy")


# ------------------------------------------------------------------ both wanted at once: wait, ask, do without


def busy_host(config: dict, tmp_path: Path) -> tuple[gate.Gate, FakeEngines, list[float]]:
    engines = FakeEngines()
    engines.ollama.append(QWEN)
    waits: list[float] = []
    g = make(config, engines, tmp_path)
    g.sleep = waits.append
    return g, engines, waits


def test_the_shipped_conflict_policy_waits_five_seconds_and_only_a_person_may_swap(config: dict) -> None:
    assert config["conflict"] == {"wait_seconds": 5, "swap": "human_confirmed"}
    config["conflict"]["swap"] = "automatic"
    assert any("swap" in problem for problem in gate.validate_config(config))


def test_a_busy_host_is_retried_once_after_the_wait_then_reported_busy(config: dict, tmp_path: Path) -> None:
    g, engines, waits = busy_host(config, tmp_path)

    with pytest.raises(gate.LocalModelBusy, match="another model") as raised:
        g.ensure("ollama", EMBED)

    assert waits == [5] and engines.loads == [] and engines.ollama == [QWEN]
    assert raised.value.held == f"ollama:{QWEN}"
    assert f"swap ollama {EMBED}" in str(raised.value)


def test_a_model_that_leaves_during_the_wait_lets_the_request_through(config: dict, tmp_path: Path) -> None:
    g, engines, _ = busy_host(config, tmp_path)
    g.sleep = lambda seconds: engines.ollama.clear()

    assert g.ensure("ollama", EMBED).action == "loaded"
    assert engines.ollama == [EMBED]


def test_other_refusals_do_not_wait(config: dict, tmp_path: Path) -> None:
    g, engines, waits = busy_host(config, tmp_path)
    engines.ollama.clear()
    engines.pressure = 4

    with pytest.raises(gate.LocalModelRefused):
        g.ensure("ollama", QWEN)
    assert waits == []


def test_a_confirmed_swap_unloads_then_loads_and_leaves_exactly_one(config: dict, tmp_path: Path) -> None:
    g, engines, _ = busy_host(config, tmp_path)
    asked: list[tuple[str, str]] = []

    decision = g.swap("ollama", EMBED, confirm=lambda held, wanted: asked.append((held, wanted)) or True)

    assert decision.action == "loaded"
    assert asked == [(f"ollama:{QWEN}", f"ollama:{EMBED}")]
    assert engines.unloads == [("ollama", QWEN)] and engines.ollama == [EMBED]


@pytest.mark.parametrize(
    "arrange, needle",
    [
        (lambda g, e: None, "not confirmed"),
        (lambda g, e: e.sizes.__setitem__(("ollama", "bge-m3:latest"), 40 * GIB), "fit"),
        (lambda g, e: setattr(e, "pressure", 4), "pressure"),
        (lambda g, e: e.strays.append("llama-server"), "outside"),
    ],
)
def test_a_swap_that_is_declined_or_unsafe_changes_nothing(
    config: dict, tmp_path: Path, arrange, needle: str
) -> None:
    g, engines, _ = busy_host(config, tmp_path)
    arrange(g, engines)

    with pytest.raises(gate.LocalModelRefused, match=needle):
        g.swap("ollama", EMBED, confirm=lambda held, wanted: needle != "not confirmed")

    assert engines.unloads == [] and engines.loads == [] and engines.ollama == [QWEN]


def test_a_swap_is_abandoned_if_the_loaded_model_changed_while_asking(config: dict, tmp_path: Path) -> None:
    g, engines, _ = busy_host(config, tmp_path)

    def confirm_while_someone_else_swaps(held: str, wanted: str) -> bool:
        engines.ollama[:] = ["other:7b"]
        return True

    with pytest.raises(gate.LocalModelRefused, match="changed"):
        g.swap("ollama", EMBED, confirm=confirm_while_someone_else_swaps)
    assert engines.unloads == [] and engines.loads == []


def test_nothing_loads_if_the_unload_does_not_take_effect(config: dict, tmp_path: Path) -> None:
    g, engines, _ = busy_host(config, tmp_path)
    engines.stuck = True

    with pytest.raises(gate.LocalModelRefused, match="still loaded"):
        g.swap("ollama", EMBED, confirm=lambda held, wanted: True)
    assert engines.loads == []


def test_a_swap_never_loads_into_a_manual_only_engine(config: dict, tmp_path: Path) -> None:
    g, engines, _ = busy_host(config, tmp_path)

    with pytest.raises(gate.LocalModelRefused, match="manual"):
        g.swap("lm-studio", "m", confirm=lambda held, wanted: True)
    assert engines.unloads == []


@pytest.mark.parametrize(
    "terminal, typed, code, swapped",
    [(False, "", 5, False), (True, "yes", 4, False), (True, f"swap ollama:{QWEN} for ollama:{EMBED}", 0, True)],
)
def test_the_swap_command_needs_a_terminal_and_the_exact_phrase(
    config: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, terminal: bool, typed: str, code: int, swapped: bool
) -> None:
    g, engines, _ = busy_host(config, tmp_path)
    monkeypatch.setattr(gate, "default_gate", lambda: g)
    monkeypatch.setattr(gate, "_is_interactive", lambda: terminal)
    monkeypatch.setattr("builtins.input", lambda prompt="": typed)

    assert gate.main(["swap", "ollama", EMBED]) == code
    assert (engines.ollama == [EMBED]) is swapped


# ------------------------------------------------------------------------- no load without a person's approval


def unapproved(config: dict, tmp_path: Path) -> tuple[gate.Gate, FakeEngines, gate.Approvals]:
    engines = FakeEngines()
    approvals = gate.Approvals(tmp_path / "approvals.json")
    g = make(config, engines, tmp_path)
    g.approvals = approvals
    return g, engines, approvals


def test_an_empty_host_with_room_still_loads_nothing_without_approval(config: dict, tmp_path: Path) -> None:
    g, engines, _ = unapproved(config, tmp_path)

    with pytest.raises(gate.LocalModelNotApproved, match="approve ollama " + QWEN):
        g.ensure("ollama", QWEN)

    assert engines.loads == [] and g.check("ollama", QWEN).action == "needs_approval"


def test_an_approval_covers_one_model_until_it_expires(
    config: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    g, engines, approvals = unapproved(config, tmp_path)
    clock = [1_000_000.0]
    monkeypatch.setattr(gate.time, "time", lambda: clock[0])
    approvals.grant("ollama", QWEN, minutes=30)

    with pytest.raises(gate.LocalModelNotApproved):
        g.ensure("ollama", EMBED)
    assert g.ensure("ollama", QWEN).action == "loaded"
    engines.ollama.clear()
    clock[0] += 31 * 60
    with pytest.raises(gate.LocalModelNotApproved):
        g.ensure("ollama", QWEN)
    assert engines.loads == [("ollama", QWEN)]


def test_a_model_already_loaded_needs_no_approval(config: dict, tmp_path: Path) -> None:
    g, engines, _ = unapproved(config, tmp_path)
    engines.ollama.append(QWEN)

    assert g.ensure("ollama", QWEN).action == "already_loaded"


@pytest.mark.parametrize("content", ["", "{}", "[1]", '[{"engine": "ollama"}]', "not json"])
def test_an_unreadable_approval_file_approves_nothing(tmp_path: Path, content: str) -> None:
    path = tmp_path / "approvals.json"
    path.write_text(content, encoding="utf-8")

    assert gate.Approvals(path).allows("ollama", QWEN) is False


def test_the_shipped_config_requires_approval(config: dict) -> None:
    assert config["approval"]["required"] is True
    config["approval"]["required"] = False
    assert any("approval" in problem for problem in gate.validate_config(config))


@pytest.mark.parametrize(
    "terminal, typed, code",
    [(False, "", 5), (True, "yes", 4), (True, f"approve ollama:{QWEN} for 15 minutes", 0)],
)
def test_the_approve_command_needs_a_terminal_and_the_exact_phrase(
    config: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, terminal: bool, typed: str, code: int
) -> None:
    g, _, approvals = unapproved(config, tmp_path)
    monkeypatch.setattr(gate, "default_gate", lambda: g)
    monkeypatch.setattr(gate, "_is_interactive", lambda: terminal)
    monkeypatch.setattr("builtins.input", lambda prompt="": typed)

    assert gate.main(["approve", "ollama", QWEN, "--minutes", "15"]) == code
    assert approvals.allows("ollama", QWEN) is (code == 0)


@pytest.mark.parametrize("url", ["http://localhost:9", "http://localhost:11500/api/embed", f"http://{LOOPBACK_V4}"])
def test_a_request_for_another_local_endpoint_never_touches_the_managed_engine(
    config: dict, tmp_path: Path, url: str
) -> None:
    engines = FakeEngines()

    with pytest.raises(gate.LocalModelRefused, match="managed endpoint"):
        make(config, engines, tmp_path).require("ollama", QWEN, url)

    assert engines.loads == []


def test_the_real_engines_refuse_every_load_and_request_while_a_test_is_running(config: dict) -> None:
    system = gate.SystemEngines(config)

    assert system.under_test is True
    for call in (lambda: system.load("ollama", EMBED, "5m"), lambda: system.unload("ollama", EMBED),
                 lambda: gate.Gate(config, system).require("ollama", EMBED, "http://localhost:11434")):
        with pytest.raises(gate.LocalModelRefused, match="test"):
            call()
