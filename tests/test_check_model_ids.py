"""Tests for configuration-derived model provenance validation."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_model_ids.py"
_spec = importlib.util.spec_from_file_location("check_model_ids", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_normalize = _mod._normalize
_check_model_id = _mod._check_model_id
configured_model_ids = _mod.configured_model_ids
scan_models_yml = _mod.scan_models_yml
scan_env_example = _mod.scan_env_example
main = _mod.main


def _models(*rows: str) -> str:
    return "version: 1\nmodels:\n" + "\n".join(rows) + "\n"


def _cloud_model(api_model: str = "claude-sonnet-5") -> str:
    return f'''  - name: strategy\n    api_model: {api_model}\n    backend: anthropic\n    device: cloud\n    provenance:\n      kind: provider-api\n      source_model_id: {api_model}\n      source_url: https://platform.claude.com/docs/models\n      verified_on: "2026-08-11"'''


def _patch_files(monkeypatch, tmp_path: Path, models: str, env: str = "") -> None:
    models_path = tmp_path / "models.yml"
    env_path = tmp_path / ".env.example"
    providers_path = tmp_path / "providers.yml"
    models_path.write_text(models, encoding="utf-8")
    env_path.write_text(env, encoding="utf-8")
    providers_path.write_text(
        "providers:\n  anthropic:\n    documentation_hosts: [platform.claude.com]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(_mod, "MODEL_YML", models_path)
    monkeypatch.setattr(_mod, "ENV_EXAMPLE", env_path)
    monkeypatch.setattr(_mod, "PROVIDERS_YML", providers_path)


def test_normalize_is_case_and_quote_insensitive() -> None:
    assert _normalize(' "Claude-Sonnet-5" ') == "claude-sonnet-5"


def test_cloud_wire_id_requires_matching_provider_provenance(monkeypatch, tmp_path) -> None:
    _patch_files(monkeypatch, tmp_path, _models(_cloud_model()))
    assert scan_models_yml() == []
    configured, errors = configured_model_ids()
    assert errors == []
    assert configured == {"strategy", "claude-sonnet-5"}


def test_cloud_model_without_api_model_fails(monkeypatch, tmp_path) -> None:
    _patch_files(monkeypatch, tmp_path, _models("  - name: strategy\n    device: cloud"))
    assert "requires api_model" in scan_models_yml()[0]


def test_cloud_model_with_mismatched_provenance_fails(monkeypatch, tmp_path) -> None:
    _patch_files(
        monkeypatch,
        tmp_path,
        _models(_cloud_model().replace("source_model_id: claude-sonnet-5", "source_model_id: stale-id")),
    )
    assert "must equal api_model" in scan_models_yml()[0]


def test_provenance_source_must_be_https(monkeypatch, tmp_path) -> None:
    _patch_files(
        monkeypatch,
        tmp_path,
        _models(_cloud_model().replace("https://platform.claude.com/docs/models", "http://example.test/models")),
    )
    assert "must be HTTPS" in scan_models_yml()[0]


def test_provenance_source_must_match_provider_documentation_host(monkeypatch, tmp_path) -> None:
    _patch_files(
        monkeypatch,
        tmp_path,
        _models(_cloud_model().replace("https://platform.claude.com/docs/models", "https://example.test/models")),
    )
    assert "outside its provider documentation authority" in scan_models_yml()[-1]


def test_provenance_rejects_missing_documentation_authority_and_missing_providers_yml(
    monkeypatch, tmp_path
) -> None:
    _patch_files(
        monkeypatch,
        tmp_path,
        _models(_cloud_model().replace("backend: anthropic", "backend: unknown_backend")),
    )
    assert "backend lacks documentation authority" in scan_models_yml()[-1]

    # Test missing providers.yml
    monkeypatch.setattr(
        _mod,
        "PROVIDERS_YML",
        tmp_path / "non_existent_providers.yml",
    )
    assert any("missing required file" in err for err in scan_models_yml())


def test_local_routing_alias_does_not_need_provider_provenance(monkeypatch, tmp_path) -> None:
    _patch_files(monkeypatch, tmp_path, _models("  - name: local-deployment\n    device: mac"))
    assert scan_models_yml() == []


def test_environment_model_must_be_configured(monkeypatch, tmp_path) -> None:
    _patch_files(monkeypatch, tmp_path, _models(_cloud_model()), "CODER_MODEL=claude-sonnet-5\n")
    assert scan_env_example() == []
    assert _check_model_id("missing-model", {"strategy"}, "x", "X_MODEL") is not None


def test_environment_model_placeholder_is_allowed(monkeypatch, tmp_path) -> None:
    _patch_files(monkeypatch, tmp_path, _models(_cloud_model()), "CODER_MODEL=${CODER_MODEL_OVERRIDE}\n")
    assert scan_env_example() == []


def test_environment_model_unknown_fails(monkeypatch, tmp_path) -> None:
    _patch_files(monkeypatch, tmp_path, _models(_cloud_model()), "CODER_MODEL=made-up-model\n")
    assert "absent from config/models.yml" in scan_env_example()[-1]


def test_main_reports_each_provenance_failure_once(monkeypatch, tmp_path, capsys) -> None:
    _patch_files(monkeypatch, tmp_path, _models("  - name: strategy\n    device: cloud"))
    assert main() == 1
    assert capsys.readouterr().err.count("requires api_model") == 1
