"""One reviewed source of truth for the OpenClaw defaults, with invariants, renderers and stale-copy protection."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from perpetua_tools import openclaw_defaults as od

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "config" / "openclaw-defaults.json"
W_AND_B = "wandb/deepseek-ai/DeepSeek-V4.1-Flash-1017"
DENY = {"exec", "process", "browser", "canvas", "nodes", "cron", "gateway"}


@pytest.fixture()
def data() -> dict:
    return copy.deepcopy(od.load(DATA_PATH))


def test_the_shipped_defaults_validate_cleanly(data: dict) -> None:
    assert od.validate(data) == []


def test_the_default_chain_has_the_agreed_order_and_no_mac_lm_studio(data: dict) -> None:
    chain = od.chain_for(data)
    assert chain == [W_AND_B, "google/gemini-3.8-flash", "ollama/qwen3.5:9b-mlx", "openrouter/free"]
    assert not any(m.startswith("lmstudio-mac/") for m in chain)


def test_both_seats_start_on_terra_then_the_default_chain_so_wandb_is_never_dropped(data: dict) -> None:
    for seat in ("biafra", "autoresearcher"):
        chain = od.chain_for(data, seat)
        assert chain[0] == "openai/gpt-6.1-terra"
        assert chain[1:] == od.chain_for(data)
        assert W_AND_B in chain


def test_the_seats_deny_the_agreed_tools_and_biafra_may_delegate_to_autoresearcher(data: dict) -> None:
    for seat in ("biafra", "autoresearcher"):
        assert DENY <= set(data["seats"][seat]["tools_deny"])
    assert data["seats"]["biafra"]["subagents_allow"] == ["autoresearcher"]
    assert data["seats"]["biafra"]["alias"] == "MetaResearcher"


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda d: d["chain"]["default"].append("lmstudio-mac/qwen3.5-9b-mlx"), "lmstudio-mac"),
        (lambda d: d["chain"]["default"].remove(W_AND_B), "W&B"),
        (lambda d: d["chain"]["default"].insert(1, "openai/gpt-6.2-sol"), "human-gated"),
        (lambda d: d["seats"]["autoresearcher"].__setitem__("model", "openai/gpt-6.2-astra"), "human-gated"),
        (lambda d: d["seats"]["biafra"]["tools_deny"].remove("exec"), "exec"),
        (lambda d: d["manual_only"]["lmstudio-mac"].__setitem__("enabled", True), "manual_only"),
        (lambda d: d["providers"]["wandb"].__setitem__("api_key", "sk-" + "a" * 40), "secret"),
        (lambda d: d["providers"]["wandb"].__setitem__("api_key_env", "not-an-env-name"), "env name"),
        (lambda d: d["seats"]["biafra"].__setitem__("subagents_allow", ["ghost"]), "unknown seat"),
    ],
)
def test_each_invariant_is_enforced(data: dict, mutate, needle: str) -> None:
    mutate(data)
    problems = od.validate(data)
    assert problems, "the broken defaults must be rejected"
    assert any(needle.lower() in p.lower() for p in problems), problems


def test_the_data_file_holds_names_only_never_a_value_that_looks_like_a_secret() -> None:
    text = DATA_PATH.read_text(encoding="utf-8")
    assert not re.search(r"sk-[A-Za-z0-9]{20,}|[0-9a-f]{40,}", text)
    assert "/Users/" not in text and not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", text)


def test_entries_patch_uses_env_secret_refs_and_the_agreed_models(data: dict) -> None:
    patch = od.render_patch(data, shape="entries")
    assert patch["agents"]["defaults"]["model"]["primary"] == W_AND_B
    assert patch["agents"]["defaults"]["model"]["fallbacks"] == od.chain_for(data)[1:]
    wandb = patch["models"]["providers"]["wandb"]
    assert wandb["apiKey"] == {"source": "env", "provider": "default", "id": "WANDB_API_KEY"}
    assert patch["models"]["providers"]["openai"]["agentRuntime"] == {"id": "codex"}
    assert patch["plugins"]["entries"]["codex"] == {"enabled": True}
    biafra = patch["agents"]["entries"]["biafra"]
    assert biafra["model"]["primary"] == "openai/gpt-6.1-terra"
    assert biafra["thinkingDefault"] == "medium"
    assert biafra["tools"]["deny"] == data["seats"]["biafra"]["tools_deny"]
    assert biafra["subagents"] == {"allowAgents": ["autoresearcher"]}
    assert "lmstudio-mac" not in json.dumps(patch)


def test_list_patch_is_the_legacy_shape_with_the_same_models(data: dict) -> None:
    patch = od.render_patch(data, shape="list")
    ids = {a["id"]: a for a in patch["agents"]["list"]}
    assert set(ids) == {"biafra", "autoresearcher"}
    assert ids["autoresearcher"]["model"]["primary"] == "openai/gpt-6.1-terra"
    assert "entries" not in patch["agents"]
    assert "lmstudio-mac" not in json.dumps(patch)


def test_drift_is_empty_for_a_config_that_matches_and_names_the_path_when_it_does_not(data: dict) -> None:
    config = od.render_patch(data, shape="entries")
    assert od.drift(data, config) == []
    config["agents"]["defaults"]["model"]["fallbacks"].insert(0, "lmstudio-mac/qwen3.5-9b-mlx")
    found = od.drift(data, config)
    assert [d["path"] for d in found] == ["agents.defaults.model.fallbacks"]


def test_drift_ignores_fields_openclaw_adds_to_a_model_entry_but_catches_a_real_change(data: dict) -> None:
    config = od.render_patch(data, shape="entries")
    config["models"]["providers"]["google"]["models"][0]["thinkingLevelMap"] = {}  # normalized by OpenClaw itself
    assert od.drift(data, config) == []
    config["models"]["providers"]["google"]["models"][0]["maxTokens"] = 1
    found = od.drift(data, config)
    assert len(found) == 1 and found[0]["path"].endswith("gemini-3.8-flash.maxTokens")


def test_only_biafra_renders_an_identity_because_the_live_autoresearcher_has_none(data: dict) -> None:
    entries = od.render_patch(data, shape="entries")["agents"]["entries"]
    assert entries["biafra"]["identity"] == {"name": "Biafra (MetaResearcher)"}
    assert "identity" not in entries["autoresearcher"]


def test_drift_never_prints_a_secret_value(data: dict) -> None:
    config = od.render_patch(data, shape="entries")
    config["models"]["providers"]["wandb"]["apiKey"] = "sk-" + "b" * 40
    found = od.drift(data, config)
    assert found and "sk-" + "b" * 10 not in json.dumps(found)


def test_fingerprint_ignores_key_order_and_the_vendor_stamp(data: dict) -> None:
    shuffled = json.loads(json.dumps(data, sort_keys=True))
    assert od.fingerprint(shuffled) == od.fingerprint(data)
    stamped = dict(data, _vendor={"source_sha256": "x"})
    assert od.fingerprint(stamped) == od.fingerprint(data)
    changed = copy.deepcopy(data)
    changed["chain"]["default"].reverse()
    assert od.fingerprint(changed) != od.fingerprint(data)


NOW = datetime(2026, 11, 27, tzinfo=timezone.utc)


def test_the_vendored_copy_carries_a_self_checking_stamp(data: dict) -> None:
    text = od.vendored_copy(data, now=NOW)
    stamp = json.loads(text)["_vendor"]
    assert stamp["source_sha256"] == od.fingerprint(data)
    assert stamp["source_updated"] == data["updated"] and stamp["vendored_at"].startswith("2026-11-27")
    assert od.verify_vendored(text, live_fingerprint=od.fingerprint(data), now=NOW)["status"] == "ok"


def test_a_stale_copy_warns_visibly_when_the_live_file_has_moved_on(data: dict) -> None:
    text = od.vendored_copy(data, now=NOW)
    verdict = od.verify_vendored(text, live_fingerprint="0" * 64, now=NOW)
    assert verdict["status"] == "stale"
    assert "differs from the live" in verdict["message"] and "sync" in verdict["message"].lower()


def test_an_old_copy_warns_when_the_live_file_cannot_be_reached(data: dict) -> None:
    text = od.vendored_copy(data, now=NOW)
    verdict = od.verify_vendored(text, live_fingerprint=None, now=NOW + timedelta(days=45), max_age_days=30)
    assert verdict["status"] == "old"
    assert "45 days" in verdict["message"] and "cannot verify" in verdict["message"].lower()


def test_a_hand_edited_copy_is_rejected(data: dict) -> None:
    obj = json.loads(od.vendored_copy(data, now=NOW))
    obj["chain"]["default"].append("lmstudio-mac/qwen3.5-9b-mlx")
    verdict = od.verify_vendored(json.dumps(obj), live_fingerprint=None, now=NOW)
    assert verdict["status"] == "tampered"


def test_the_cli_validates_renders_checks_and_fingerprints(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert od.main(["--validate"]) == 0
    assert od.main(["--fingerprint"]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()[-1]) == 64
    assert od.main(["--render-patch", "--shape", "entries"]) == 0
    patch = json.loads(capsys.readouterr().out)
    assert patch["agents"]["defaults"]["model"]["primary"] == W_AND_B
    good = tmp_path / "good.json"
    good.write_text(json.dumps(patch), encoding="utf-8")
    assert od.main(["--check", str(good)]) == 0
    patch["agents"]["defaults"]["model"]["primary"] = "openai/gpt-6.2-sol"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(patch), encoding="utf-8")
    assert od.main(["--check", str(bad)]) == 1


def test_drift_ignores_any_field_openclaw_adds_in_either_shape(data: dict) -> None:
    """OpenClaw normalizes entries on write (thinkingLevelMap, agentDir, workspace ...): extras are never drift."""
    config = od.render_patch(data, shape="entries")
    config["agents"]["entries"]["biafra"]["agentDir"] = "/x"
    config["agents"]["entries"]["biafra"]["workspace"] = "/y"
    config["agents"]["entries"]["biafra"]["model"]["thinkingLevelMap"] = {}
    config["agents"]["defaults"]["bootstrapMaxChars"] = 5000
    config["models"]["providers"]["wandb"]["models"][0]["thinkingLevelMap"] = {}
    config["models"]["providers"]["wandb"]["extraProviderField"] = True
    assert od.drift(data, config) == []
    legacy = od.render_patch(data, shape="list")
    for agent in legacy["agents"]["list"]:
        agent["agentDir"] = "/x"
        agent["model"]["thinkingLevelMap"] = {}
    assert od.drift(data, legacy) == []


def test_drift_still_reports_a_changed_or_missing_expected_field_next_to_extras(data: dict) -> None:
    config = od.render_patch(data, shape="entries")
    config["agents"]["entries"]["biafra"]["thinkingLevelMap"] = {}
    config["agents"]["entries"]["biafra"]["model"]["primary"] = "openai/gpt-6.2-astra"
    del config["agents"]["entries"]["autoresearcher"]["tools"]
    paths = {d["path"] for d in od.drift(data, config)}
    assert paths == {"agents.entries.biafra.model.primary", "agents.entries.autoresearcher.tools.deny"}


def test_the_stamp_also_covers_the_vendored_module(data: dict) -> None:
    source = "def f():\n    return 1\n"
    text = od.vendored_copy(data, now=NOW, module_source=source)
    assert json.loads(text)["_vendor"]["module_sha256"]
    assert od.verify_vendored(text, live_fingerprint=od.fingerprint(data), now=NOW, module_source=source)["status"] == "ok"
    edited = od.verify_vendored(text, live_fingerprint=od.fingerprint(data), now=NOW, module_source=source + "# hand edit\n")
    assert edited["status"] == "tampered" and "module" in edited["message"]
    bare = od.vendored_copy(data, now=NOW)  # stamped without a module hash
    assert od.verify_vendored(bare, now=NOW, module_source=source)["status"] == "invalid"
