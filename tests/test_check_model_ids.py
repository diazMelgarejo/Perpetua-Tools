"""Tests for scripts/check_model_ids.py (T2-B positive allowlist)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import mock

import pytest

# Load the script module from its non-package location
_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_model_ids.py"
_spec = importlib.util.spec_from_file_location("check_model_ids", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_normalize = _mod._normalize
_check_model_id = _mod._check_model_id
scan_models_yml = _mod.scan_models_yml
scan_env_example = _mod.scan_env_example
main = _mod.main
ALLOWED_MODEL_IDS = _mod.ALLOWED_MODEL_IDS
_ALLOWED_LC = _mod._ALLOWED_LC


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_strips_whitespace(self):
        assert _normalize("  qwen3.5-9b-mlx  ") == "qwen3.5-9b-mlx"

    def test_strips_double_quotes(self):
        assert _normalize('"claude-sonnet-4-5"') == "claude-sonnet-4-5"

    def test_strips_single_quotes(self):
        assert _normalize("'sonar-reasoning-pro'") == "sonar-reasoning-pro"

    def test_lowercases(self):
        assert _normalize("QWEN3.5-9B-MLX") == "qwen3.5-9b-mlx"

    def test_empty_string(self):
        assert _normalize("") == ""

    def test_strips_outer_quotes_then_lowercases(self):
        assert _normalize('"Qwen3.5-9b-MLX"') == "qwen3.5-9b-mlx"


# ---------------------------------------------------------------------------
# _check_model_id
# ---------------------------------------------------------------------------


class TestCheckModelId:
    def test_allowlisted_id_returns_none(self):
        assert _check_model_id("claude-sonnet-4-5", "config/models.yml", "name:") is None

    def test_allowlisted_id_case_insensitive(self):
        # All IDs in ALLOWED_MODEL_IDS are lowercase; check case normalisation works
        assert _check_model_id("CLAUDE-SONNET-4-5", "config/models.yml", "name:") is None

    def test_disallowed_id_returns_violation_string(self):
        result = _check_model_id("gpt-4o-hallucinated", "config/models.yml", "name:")
        assert result is not None
        assert "gpt-4o-hallucinated" in result
        assert "ALLOWED_MODEL_IDS" in result

    def test_empty_id_returns_none(self):
        """Empty model ID (after normalisation) must be skipped."""
        assert _check_model_id("", "config/models.yml", "name:") is None

    def test_env_placeholder_skipped(self):
        """${VAR} env substitution placeholders must be skipped."""
        assert _check_model_id("${CODER_MODEL}", "config/models.yml", "CODER_MODEL") is None

    def test_violation_message_includes_source_and_hint(self):
        result = _check_model_id("invented-model", ".env.example", "MY_MODEL")
        assert ".env.example" in result
        assert "MY_MODEL" in result

    def test_openrouter_allowlisted_id(self):
        assert _check_model_id("openrouter/nvidia/nemotron-3-super-120b-a12b:free", "f", "h") is None

    def test_quoted_allowlisted_id(self):
        assert _check_model_id('"qwen3.5-9b-mlx"', "config/models.yml", "name:") is None


# ---------------------------------------------------------------------------
# scan_models_yml
# ---------------------------------------------------------------------------


class TestScanModelsYml:
    def _patch_yml(self, monkeypatch, content: str, tmp_path: Path) -> None:
        yml = tmp_path / "models.yml"
        yml.write_text(content, encoding="utf-8")
        monkeypatch.setattr(_mod, "MODEL_YML", yml)

    def test_missing_file_returns_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_mod, "MODEL_YML", tmp_path / "nonexistent.yml")
        violations = scan_models_yml()
        assert len(violations) == 1
        assert "missing" in violations[0]

    def test_empty_file_no_violations(self, monkeypatch, tmp_path):
        self._patch_yml(monkeypatch, "", tmp_path)
        assert scan_models_yml() == []

    def test_allowlisted_name_no_violation(self, monkeypatch, tmp_path):
        self._patch_yml(
            monkeypatch,
            "- name: qwen3.5-9b-mlx\n  api_model: qwen3.5-9b-mlx\n",
            tmp_path,
        )
        assert scan_models_yml() == []

    def test_disallowed_name_only_not_scanned(self, monkeypatch, tmp_path):
        """Internal routing aliases (name:) are not external model IDs."""
        self._patch_yml(
            monkeypatch,
            "- name: hallucinated-model-9000\n",
            tmp_path,
        )
        assert scan_models_yml() == []

    def test_disallowed_api_model_violation(self, monkeypatch, tmp_path):
        self._patch_yml(
            monkeypatch,
            "  api_model: gpt-4o-unknown-version\n",
            tmp_path,
        )
        violations = scan_models_yml()
        assert len(violations) == 1
        assert "api_model:" in violations[0]

    def test_multiple_allowlisted_entries_no_violation(self, monkeypatch, tmp_path):
        self._patch_yml(
            monkeypatch,
            (
                "- name: claude-sonnet-4-5\n"
                "  api_model: claude-sonnet-4-5\n"
                "- name: sonar-reasoning-pro\n"
                "  api_model: sonar-reasoning-pro\n"
            ),
            tmp_path,
        )
        assert scan_models_yml() == []

    def test_quoted_name_allowlisted(self, monkeypatch, tmp_path):
        self._patch_yml(
            monkeypatch,
            '- name: "qwen3.5-9b-mlx-4bit"\n',
            tmp_path,
        )
        assert scan_models_yml() == []

    def test_comment_not_parsed_as_model_id(self, monkeypatch, tmp_path):
        """Text after # on a name: line must not be scanned as a model ID."""
        self._patch_yml(
            monkeypatch,
            "- name: qwen3.5-9b-mlx  # this-is-not-a-model-id\n",
            tmp_path,
        )
        # The regex strips trailing comments — the captured group ends at # or newline
        # So this should pass (the comment is not captured)
        violations = scan_models_yml()
        # qwen3.5-9b-mlx is allowlisted
        assert violations == []


# ---------------------------------------------------------------------------
# scan_env_example
# ---------------------------------------------------------------------------


class TestScanEnvExample:
    def _patch_env(self, monkeypatch, content: str, tmp_path: Path) -> None:
        env = tmp_path / ".env.example"
        env.write_text(content, encoding="utf-8")
        monkeypatch.setattr(_mod, "ENV_EXAMPLE", env)

    def test_missing_file_returns_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_mod, "ENV_EXAMPLE", tmp_path / "nonexistent")
        violations = scan_env_example()
        assert len(violations) == 1
        assert "missing" in violations[0]

    def test_no_model_vars_no_violations(self, monkeypatch, tmp_path):
        self._patch_env(monkeypatch, "ORAMA_PLATFORM=mac\nAPI_KEY=secret\n", tmp_path)
        assert scan_env_example() == []

    def test_allowlisted_model_var_no_violation(self, monkeypatch, tmp_path):
        self._patch_env(
            monkeypatch,
            "CODER_MODEL=claude-sonnet-4-5\n",
            tmp_path,
        )
        assert scan_env_example() == []

    def test_disallowed_model_var_violation(self, monkeypatch, tmp_path):
        self._patch_env(
            monkeypatch,
            "MANAGER_MODEL=gpt-5-hallucinated\n",
            tmp_path,
        )
        violations = scan_env_example()
        assert len(violations) == 1
        assert "gpt-5-hallucinated" in violations[0]

    def test_env_placeholder_no_violation(self, monkeypatch, tmp_path):
        """${VAR} placeholders in .env.example must be skipped."""
        self._patch_env(
            monkeypatch,
            "CODER_MODEL=${CODER_MODEL_OVERRIDE}\n",
            tmp_path,
        )
        assert scan_env_example() == []

    def test_multiple_model_vars_mixed(self, monkeypatch, tmp_path):
        self._patch_env(
            monkeypatch,
            "CODER_MODEL=claude-sonnet-4-5\nMANAGER_MODEL=gpt-4-fake\n",
            tmp_path,
        )
        violations = scan_env_example()
        assert len(violations) == 1
        assert "gpt-4-fake" in violations[0]

    def test_var_must_start_uppercase_letter(self, monkeypatch, tmp_path):
        """Lowercase-starting variable names must not match the regex."""
        self._patch_env(
            monkeypatch,
            "coder_MODEL=hallucinated-model\n",
            tmp_path,
        )
        # The regex requires uppercase first letter
        assert scan_env_example() == []

    def test_probe_timeout_not_scanned(self, monkeypatch, tmp_path):
        self._patch_env(
            monkeypatch,
            "MODEL_PROBE_TIMEOUT=3\n",
            tmp_path,
        )
        assert scan_env_example() == []

    def test_grok_model_allowlisted(self, monkeypatch, tmp_path):
        self._patch_env(
            monkeypatch,
            "REASONING_MODEL=grok-4-1-thinking\n",
            tmp_path,
        )
        assert scan_env_example() == []


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_ok_when_both_files_clean(self, monkeypatch, tmp_path, capsys):
        yml = tmp_path / "models.yml"
        yml.write_text("- name: qwen3.5-9b-mlx\n", encoding="utf-8")
        env = tmp_path / ".env.example"
        env.write_text("ORAMA_PLATFORM=mac\n", encoding="utf-8")
        monkeypatch.setattr(_mod, "MODEL_YML", yml)
        monkeypatch.setattr(_mod, "ENV_EXAMPLE", env)
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out

    def test_main_fails_when_yml_has_violation(self, monkeypatch, tmp_path, capsys):
        yml = tmp_path / "models.yml"
        yml.write_text("  api_model: hallucinated-llm\n", encoding="utf-8")
        env = tmp_path / ".env.example"
        env.write_text("", encoding="utf-8")
        monkeypatch.setattr(_mod, "MODEL_YML", yml)
        monkeypatch.setattr(_mod, "ENV_EXAMPLE", env)
        result = main()
        assert result == 1
        captured = capsys.readouterr()
        assert "hallucinated-llm" in captured.err

    def test_main_fails_when_env_has_violation(self, monkeypatch, tmp_path, capsys):
        yml = tmp_path / "models.yml"
        yml.write_text("", encoding="utf-8")
        env = tmp_path / ".env.example"
        env.write_text("CODER_MODEL=gpt-99-ultra\n", encoding="utf-8")
        monkeypatch.setattr(_mod, "MODEL_YML", yml)
        monkeypatch.setattr(_mod, "ENV_EXAMPLE", env)
        result = main()
        assert result == 1
        captured = capsys.readouterr()
        assert "gpt-99-ultra" in captured.err

    def test_main_fails_when_both_files_missing(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(_mod, "MODEL_YML", tmp_path / "missing.yml")
        monkeypatch.setattr(_mod, "ENV_EXAMPLE", tmp_path / "missing.env")
        result = main()
        assert result == 1
        captured = capsys.readouterr()
        assert "missing" in captured.err