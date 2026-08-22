"""Unit tests for orchestrator/autoresearch_bridge.py.

Tests SwarmState parsing, GPU lock helpers, swarm_state.md initialisation,
the preflight convenience function, plugin install, and dry-run autoplan.
All SSH/scp/claude calls are mocked; no GPU runner required.
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import orchestrator.autoresearch_bridge as bridge
from orchestrator.autoresearch_bridge import (
    SyncResult,
    init_swarm_state,
    is_gpu_idle,
    read_swarm_state,
)


@pytest.fixture(autouse=True)
def patch_swarm_path(tmp_path, monkeypatch):
    """Redirect swarm_state.md to a temp directory so tests are isolated."""
    fake_local = tmp_path / "autoresearch"
    fake_local.mkdir()
    monkeypatch.setattr(bridge, "LOCAL_REPO_PATH", fake_local)
    monkeypatch.setattr(bridge, "SWARM_STATE_FILE", fake_local / "swarm_state.md")
    return fake_local


class TestModuleConstants:
    @pytest.fixture(autouse=True)
    def restore_bridge_module(self):
        import importlib
        importlib.reload(bridge)
        yield
        importlib.reload(bridge)

    def test_autoresearch_remote_contains_uditgoenka(self):
        assert "uditgoenka/autoresearch" in bridge.AUTORESEARCH_REMOTE

    def test_autoresearch_remote_not_karpathy(self):
        assert "karpathy" not in bridge.AUTORESEARCH_REMOTE

    def test_autoresearch_default_branch_matches_primary_upstream(self):
        assert bridge.AUTORESEARCH_DEFAULT_BRANCH == "master"

    def test_autoresearch_remote_env_override(self, monkeypatch):
        import importlib
        monkeypatch.setenv("AUTORESEARCH_REMOTE", "https://github.com/myorg/autoresearch.git")
        bridge_fresh = importlib.reload(bridge)
        assert "myorg/autoresearch" in bridge_fresh.AUTORESEARCH_REMOTE

    def test_autoresearch_branch_env_override(self, monkeypatch):
        import importlib
        monkeypatch.setenv("AUTORESEARCH_BRANCH", "dev")
        bridge_fresh = importlib.reload(bridge)
        assert bridge_fresh.AUTORESEARCH_DEFAULT_BRANCH == "dev"


class TestReadSwarmState:
    def test_returns_idle_when_file_absent(self):
        state = read_swarm_state()
        assert state.gpu_status == "IDLE"

    def test_parses_gpu_busy(self):
        content = textwrap.dedent("""\
            ## Status
            - GPU: BUSY
        """)
        bridge.SWARM_STATE_FILE.write_text(content, encoding="utf-8")
        assert read_swarm_state().gpu_status == "BUSY"

    def test_parses_gpu_idle(self):
        bridge.SWARM_STATE_FILE.write_text("- GPU: IDLE\n", encoding="utf-8")
        assert read_swarm_state().gpu_status == "IDLE"

    def test_parses_val_bpb(self):
        bridge.SWARM_STATE_FILE.write_text("val_bpb: 1.234\n", encoding="utf-8")
        assert read_swarm_state().baseline_val_bpb == pytest.approx(1.234)

    def test_parses_git_sha(self):
        bridge.SWARM_STATE_FILE.write_text("git_sha: abcdef1234567890\n", encoding="utf-8")
        assert read_swarm_state().baseline_sha == "abcdef1234567890"

    def test_invalid_val_bpb_ignored(self):
        bridge.SWARM_STATE_FILE.write_text("val_bpb: not_a_number\n", encoding="utf-8")
        assert read_swarm_state().baseline_val_bpb == 0.0


class TestIsGpuIdle:
    def test_idle_when_no_file(self):
        assert is_gpu_idle() is True

    def test_idle_when_status_idle(self):
        bridge.SWARM_STATE_FILE.write_text("- GPU: IDLE\n", encoding="utf-8")
        assert is_gpu_idle() is True

    def test_not_idle_when_busy(self):
        bridge.SWARM_STATE_FILE.write_text("- GPU: BUSY\n", encoding="utf-8")
        assert is_gpu_idle() is False

    def test_case_insensitive(self):
        bridge.SWARM_STATE_FILE.write_text("- GPU: idle\n", encoding="utf-8")
        assert is_gpu_idle() is True


class TestInitSwarmState:
    def test_creates_file(self):
        init_swarm_state("test-run")
        assert bridge.SWARM_STATE_FILE.exists()

    def test_file_contains_run_tag(self):
        init_swarm_state("mar22")
        assert "mar22" in bridge.SWARM_STATE_FILE.read_text(encoding="utf-8")

    def test_file_starts_with_idle_status(self):
        init_swarm_state("myrun")
        assert "GPU: IDLE" in bridge.SWARM_STATE_FILE.read_text(encoding="utf-8")

    def test_file_contains_managed_by_comment(self):
        init_swarm_state("anyrun")
        assert "autoresearch_bridge.py" in bridge.SWARM_STATE_FILE.read_text(encoding="utf-8")

    def test_file_contains_hardware_guard(self):
        init_swarm_state("guard-test")
        content = bridge.SWARM_STATE_FILE.read_text(encoding="utf-8")
        assert "HARDWARE GUARD" in content or "strictly sequential" in content.lower()


class TestSyncResult:
    def test_ok_result(self):
        result = SyncResult(ok=True, sha="abc123")
        assert result.ok is True
        assert result.sha == "abc123"
        assert result.error == ""

    def test_error_result(self):
        result = SyncResult(ok=False, error="SSH timeout")
        assert result.ok is False
        assert result.error == "SSH timeout"


class TestSyncAutoresearchIdempotent:
    @pytest.fixture(autouse=True)
    def force_ssh_preflight(self, monkeypatch):
        monkeypatch.setattr(bridge, "use_http_local_preflight", lambda: False)

    def test_uses_configured_default_branch(self):
        mock_result = MagicMock(returncode=0, stdout="HEAD sha\nabc123def", stderr="")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            bridge.sync_autoresearch_idempotent()
        ssh_cmd = " ".join(mock_run.call_args[0][0])
        assert bridge.AUTORESEARCH_DEFAULT_BRANCH in ssh_cmd
        assert f"origin/{bridge.AUTORESEARCH_DEFAULT_BRANCH}" in ssh_cmd

    def test_returns_sync_result_on_success(self):
        mock_result = MagicMock(returncode=0, stdout="HEAD sha\nabc123def", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = bridge.sync_autoresearch_idempotent()
        assert result.ok is True
        assert result.sha == "abc123def"

    def test_returns_error_on_nonzero_returncode(self):
        mock_result = MagicMock(returncode=1, stdout="", stderr="fatal: not a git repository")
        with patch("subprocess.run", return_value=mock_result):
            result = bridge.sync_autoresearch_idempotent()
        assert result.ok is False
        assert "not a git repository" in result.error

    def test_returns_error_on_timeout(self):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ssh", 90)):
            result = bridge.sync_autoresearch_idempotent()
        assert result.ok is False
        assert "timeout" in result.error.lower()


class TestHttpLocalPreflight:
    def test_use_http_local_when_gpu_box_is_loopback(self, monkeypatch):
        monkeypatch.setattr(bridge, "GPU_BOX", "WINUSER@127.0.0.1")
        monkeypatch.setattr(bridge, "AUTORESEARCH_PREFLIGHT_MODE", "auto")
        assert bridge.use_http_local_preflight() is True

    def test_sync_local_skips_ssh(self, monkeypatch, patch_swarm_path):
        repo = patch_swarm_path
        (repo / ".git").mkdir()
        monkeypatch.setattr(bridge, "use_http_local_preflight", lambda: True)
        mock_result = MagicMock(returncode=0, stdout="abc123def", stderr="")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = bridge.sync_autoresearch_idempotent()
        assert result.ok is True
        assert result.sha == "abc123def"
        for call_args in mock_run.call_args_list:
            cmd = call_args[0][0]
            assert cmd[0] == "git"
            assert "ssh" not in cmd

    def test_probe_lm_studio_http_success(self):
        # probe_lm_studio_http() opens through _NO_REDIRECT_OPENER (a custom
        # urllib opener that refuses redirects, see _NoRedirectHandler), not
        # the module-level urllib.request.urlopen -- patch the actual call
        # site, not a stale target the code no longer reaches.
        payload = json.dumps({"data": [{"id": "m1"}, {"id": "m2"}]})
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = payload.encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch.object(bridge._NO_REDIRECT_OPENER, "open", return_value=mock_resp):
            result = bridge.probe_lm_studio_http()
        assert result.ok is True
        assert result.sha == "2"

    def test_probe_lm_studio_http_refuses_redirect(self):
        """Regression test for the redirect-based bypass this opener closes:
        a compromised/MITM'd LM Studio instance redirecting the probe
        elsewhere must be refused, not silently followed."""
        import urllib.error

        with patch.object(
            bridge._NO_REDIRECT_OPENER,
            "open",
            side_effect=urllib.error.HTTPError(
                "http://localhost:1234/v1/models", 302, "redirect refused", {}, None
            ),
        ):
            result = bridge.probe_lm_studio_http()
        assert result.ok is False
        assert "302" in (result.error or "")

    def test_preflight_exposes_http_local_fields(self):
        with patch.object(bridge, "install_autoresearch_plugin", return_value=SyncResult(ok=True)), \
             patch.object(bridge, "bootstrap_autoresearch_on_runner", return_value=SyncResult(ok=True, sha="deadbeef")), \
             patch.object(bridge, "use_http_local_preflight", return_value=True), \
             patch.object(bridge, "probe_lm_studio_http", return_value=SyncResult(ok=True, sha="3")):
            result = bridge.preflight()
        assert result["gpu_local"] is True
        assert result["preflight_mode"] == "http-local"
        assert result["lm_studio_ok"] is True
        assert result["lm_studio_models"] == "3"


class TestInstallAutoresearchPlugin:
    """install_autoresearch_plugin() is a 3-tier fallback, no hard dependency:
    1. global skill/command install (filesystem-only)
    2. Claude Code plugin marketplace (best-effort subprocess)
    3. micro-implementation fallback (ok=True, sha="micro-fallback")

    Tests for tiers 2-3 patch _global_autoresearch_install_present to False so
    the plugin-marketplace path under test actually runs.
    """

    def test_skips_subprocess_when_global_install_present(self):
        with patch.object(bridge, "_global_autoresearch_install_present", return_value=True), \
             patch("subprocess.run") as mock_run:
            result = bridge.install_autoresearch_plugin()
        assert result.ok is True
        assert result.sha == "global-skill-install"
        mock_run.assert_not_called()

    def test_skips_if_already_installed(self):
        mock_list = MagicMock(returncode=0, stdout="uditgoenka/autoresearch  v1.0.0\n", stderr="")
        with patch.object(bridge, "_global_autoresearch_install_present", return_value=False), \
             patch("subprocess.run", return_value=mock_list) as mock_run:
            result = bridge.install_autoresearch_plugin()
        assert result.ok is True
        assert result.sha == "already-installed"
        assert mock_run.call_count == 1

    def test_runs_two_commands_when_not_installed(self):
        mock_list = MagicMock(returncode=0, stdout="other-plugin\n", stderr="")
        mock_add = MagicMock(returncode=0, stdout="", stderr="")
        mock_install = MagicMock(returncode=0, stdout="", stderr="")
        with patch.object(bridge, "_global_autoresearch_install_present", return_value=False), \
             patch("subprocess.run", side_effect=[mock_list, mock_add, mock_install]) as mock_run:
            result = bridge.install_autoresearch_plugin()
        assert result.ok is True
        commands = [" ".join(c[0][0]) for c in mock_run.call_args_list]
        assert any("marketplace" in c and "uditgoenka/autoresearch" in c for c in commands)
        assert any("plugin install" in c for c in commands)

    def test_falls_back_to_micro_implementation_if_marketplace_add_fails(self):
        mock_list = MagicMock(returncode=0, stdout="", stderr="")
        mock_add = MagicMock(returncode=1, stdout="", stderr="network error")
        with patch.object(bridge, "_global_autoresearch_install_present", return_value=False), \
             patch("subprocess.run", side_effect=[mock_list, mock_add]):
            result = bridge.install_autoresearch_plugin()
        assert result.ok is True
        assert result.sha == "micro-fallback"
        assert "marketplace add failed" in result.error

    def test_falls_back_to_micro_implementation_if_claude_cli_missing(self):
        with patch.object(bridge, "_global_autoresearch_install_present", return_value=False), \
             patch("subprocess.run", side_effect=FileNotFoundError("claude: command not found")):
            result = bridge.install_autoresearch_plugin()
        assert result.ok is True
        assert result.sha == "micro-fallback"
        assert "claude" in result.error.lower() or "not found" in result.error.lower()

    def test_falls_back_to_micro_implementation_if_plugin_install_fails(self):
        mock_list = MagicMock(returncode=0, stdout="", stderr="")
        mock_add = MagicMock(returncode=0, stdout="", stderr="")
        mock_install = MagicMock(returncode=1, stdout="", stderr="install failed")
        with patch.object(bridge, "_global_autoresearch_install_present", return_value=False), \
             patch("subprocess.run", side_effect=[mock_list, mock_add, mock_install]):
            result = bridge.install_autoresearch_plugin()
        assert result.ok is True
        assert result.sha == "micro-fallback"
        assert "plugin install failed" in result.error


class TestGlobalAutoresearchInstallPresent:
    def test_true_when_both_skill_dir_and_command_file_exist(self, tmp_path, monkeypatch):
        (tmp_path / "skills" / "autoresearch").mkdir(parents=True)
        (tmp_path / "commands").mkdir(parents=True)
        (tmp_path / "commands" / "autoresearch.md").write_text("stub")
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
        assert bridge._global_autoresearch_install_present() is True

    def test_false_when_only_skill_dir_exists(self, tmp_path, monkeypatch):
        (tmp_path / "skills" / "autoresearch").mkdir(parents=True)
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
        assert bridge._global_autoresearch_install_present() is False

    def test_false_when_neither_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
        assert bridge._global_autoresearch_install_present() is False


class TestAutoplanDryRun:
    def test_plan_classifies_hardening_goal(self):
        plan = bridge.plan_autoresearch_goal("harden gateway auth token handling")
        assert plan.archetype == "harden"
        assert plan.pipeline == ["security", "fix", "security"]
        assert plan.dry_run is True
        assert "security regression" in plan.predicate

    def test_plan_includes_primary_and_secondary_upstreams(self):
        plan = bridge.plan_autoresearch_goal("explore current docs")
        assert "uditgoenka/autoresearch" in plan.upstream_primary
        assert "9f51f726e513be4e899b6afeed9f9c55fc1f51f3" in plan.upstream_primary
        assert "karpathy/autoresearch" in plan.upstream_secondary
        assert "c92bee55ebc339e8b1501f6b5c9cfb54835a9de8" in plan.upstream_secondary

    def test_ml_experiment_plan_uses_metric_archetype_and_gpu_predicate(self):
        plan = bridge.plan_autoresearch_goal("improve val_bpb", task_type="ml-experiment")
        assert plan.archetype == "optimize-metric"
        assert "GPU: IDLE" in plan.predicate
        assert any("GPU verify substrate" in note for note in plan.notes)

    def test_preflight_dry_run_skips_plugin_sync_and_lm_probe(self):
        with patch.object(bridge, "install_autoresearch_plugin") as plugin, \
             patch.object(bridge, "bootstrap_autoresearch_on_runner") as bootstrap, \
             patch.object(bridge, "probe_lm_studio_http") as probe, \
             patch.object(bridge, "sync_autoresearch_idempotent") as sync, \
             patch.object(bridge, "deploy_train_py") as deploy, \
             patch.object(bridge, "run_experiment_on_gpu") as run:
            result = bridge.preflight(
                goal="ship autoresearch adoption safely",
                dry_run=True,
                use_orama=True,
                max_cycles=7,
            )
        assert result["dry_run"] is True
        assert result["preflight_mode"] == "dry-run"
        assert result["plan"]["archetype"] == "ship-ready"
        assert result["plan"]["max_cycles"] == 7
        assert result["plan"]["orama_methodology"] == "optional"
        assert result["plan"]["plugin_execution"] == "skipped in dry-run"
        assert result["plan"]["gpu_execution"] == "skipped in dry-run"
        plugin.assert_not_called()
        bootstrap.assert_not_called()
        probe.assert_not_called()
        sync.assert_not_called()
        deploy.assert_not_called()
        run.assert_not_called()


class TestPreflight:
    def test_preflight_initialises_swarm_state_when_absent(self):
        with patch.object(bridge, "install_autoresearch_plugin", return_value=SyncResult(ok=True)), \
             patch.object(bridge, "bootstrap_autoresearch_on_runner", return_value=SyncResult(ok=True, sha="abc")):
            result = bridge.preflight(run_tag="testrun")
        assert result["swarm_state_initialised"] is True
        assert bridge.SWARM_STATE_FILE.exists()

    def test_preflight_skips_init_when_file_exists(self):
        bridge.SWARM_STATE_FILE.write_text("existing content", encoding="utf-8")
        with patch.object(bridge, "install_autoresearch_plugin", return_value=SyncResult(ok=True)), \
             patch.object(bridge, "bootstrap_autoresearch_on_runner", return_value=SyncResult(ok=True, sha="abc")):
            result = bridge.preflight(run_tag="testrun")
        assert result["swarm_state_initialised"] is False

    def test_preflight_returns_sync_ok_on_success(self):
        with patch.object(bridge, "install_autoresearch_plugin", return_value=SyncResult(ok=True)), \
             patch.object(bridge, "bootstrap_autoresearch_on_runner", return_value=SyncResult(ok=True, sha="deadbeef")):
            result = bridge.preflight()
        assert result["sync_ok"] is True
        assert result["sha"] == "deadbeef"

    def test_preflight_propagates_sync_failure(self):
        with patch.object(bridge, "install_autoresearch_plugin", return_value=SyncResult(ok=True)), \
             patch.object(bridge, "bootstrap_autoresearch_on_runner", return_value=SyncResult(ok=False, error="SSH refused")):
            result = bridge.preflight()
        assert result["sync_ok"] is False
        assert result["error"] == "SSH refused"

    def test_preflight_exposes_plugin_ok(self):
        with patch.object(bridge, "install_autoresearch_plugin", return_value=SyncResult(ok=False, error="no claude CLI")), \
             patch.object(bridge, "bootstrap_autoresearch_on_runner", return_value=SyncResult(ok=True, sha="abc")):
            result = bridge.preflight()
        assert result["plugin_ok"] is False
        assert "no claude CLI" in result["plugin_error"]


def test_lm_studio_base_url_rejects_link_local_metadata_via_llama_server_env(monkeypatch):
    """Regression: _lm_studio_base_url()'s LLAMA_SERVER_BASE_URL branch had
    scheme-safety (avoids double-scheme construction) but no SSRF host
    classification. probe_lm_studio_http() calls urlopen() on this result
    with an Authorization: Bearer token attached -- an operator (or
    compromised env) setting LLAMA_SERVER_BASE_URL=169.254.169.254 would
    have this process probe cloud instance-metadata with the LM Studio
    token leaked in the request header."""
    monkeypatch.setenv("LLAMA_SERVER_BASE_URL", "http://169.254.169.254:8080")
    monkeypatch.delenv("LM_STUDIO_WIN_ENDPOINTS", raising=False)
    result = bridge._lm_studio_base_url()
    assert "169.254.169.254" not in result
    assert result == "http://localhost:1234"


def test_lm_studio_base_url_rejects_public_target_via_win_endpoints_env(monkeypatch):
    monkeypatch.delenv("LLAMA_SERVER_BASE_URL", raising=False)
    monkeypatch.setenv("LM_STUDIO_WIN_ENDPOINTS", "http://8.8.8.8:1234")
    result = bridge._lm_studio_base_url()
    assert "8.8.8.8" not in result
    assert result == "http://localhost:1234"


def test_lm_studio_base_url_still_accepts_lan_ip(monkeypatch):
    """Confirm the fix isn't over-broad -- a genuine RFC1918 target must
    still pass through unchanged."""
    monkeypatch.setenv("LLAMA_SERVER_BASE_URL", "http://192.168.1.99:8080")
    monkeypatch.delenv("LM_STUDIO_WIN_ENDPOINTS", raising=False)
    result = bridge._lm_studio_base_url()
    assert result == "http://192.168.1.99:8080"
