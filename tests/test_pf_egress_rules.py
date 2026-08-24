"""Tests for Layer-3 macOS pf egress rules installer and verification scripts.

Tests idempotency, rule integrity, drift detection, and non-blocking verification logic.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "security" / "install-egress-pf-rules.sh"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "security" / "verify-egress-pf-rules.sh"

EXPECTED_RULES = [
    "block drop out quick to 169.254.0.0/16",
    "block drop out quick to 169.254.169.254",
    "block drop out quick to fd00:ec2::254",
    "block drop out quick to fe80::/10",
]


@pytest.fixture
def darwin_uname_env(tmp_path_factory):
    """Both scripts platform-guard on `uname -s` == "Darwin" and early-exit
    (before writing/checking anything) on any other host. This repo's real
    CI runners are Linux, so without stubbing uname the dynamic tests below
    never exercise the scripts' actual write/verify logic at all -- they'd
    pass or fail based solely on the platform guard, not the behavior being
    tested. Prepend a fake `uname` binary to PATH that always reports
    Darwin, so the scripts run their real logic under test; PFCTL_SKIP=1
    still separately bypasses the actual pfctl binary, which genuinely
    isn't installed here.

    Also defaults PF_CONF_FILE to a throwaway tmp path -- without this, the
    installer's real /etc/pf.conf anchor-attachment step (added alongside
    this fixture) writes to the actual system file. Caught this directly:
    an early test run without this override genuinely wrote a managed
    anchor block into this sandbox's real /etc/pf.conf.
    """
    stub_dir = tmp_path_factory.mktemp("uname-stub")
    fake_uname = stub_dir / "uname"
    fake_uname.write_text("#!/bin/bash\necho Darwin\n", encoding="utf-8")
    fake_uname.chmod(0o755)
    conf_dir = tmp_path_factory.mktemp("pf-conf")
    env = dict(os.environ)
    env["PATH"] = f"{stub_dir}:{env.get('PATH', '')}"
    env["PF_CONF_FILE"] = str(conf_dir / "pf.conf")
    return env


class TestPFEgressScripts:
    """Test suite for install-egress-pf-rules.sh and verify-egress-pf-rules.sh."""

    def test_scripts_exist_and_executable(self) -> None:
        assert INSTALL_SCRIPT.exists(), f"Missing {INSTALL_SCRIPT}"
        assert VERIFY_SCRIPT.exists(), f"Missing {VERIFY_SCRIPT}"
        assert os.access(INSTALL_SCRIPT, os.X_OK), "install script not executable"
        assert os.access(VERIFY_SCRIPT, os.X_OK), "verify script not executable"

    def test_installer_idempotency_and_content(self, darwin_uname_env) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_anchor = Path(tmpdir) / "com.perpetua-tools.egress-deny"
            env = {**darwin_uname_env, "PF_ANCHOR_FILE": str(fake_anchor), "PFCTL_SKIP": "1"}

            # Pass 1: Install should write rules
            res1 = subprocess.run(
                ["bash", str(INSTALL_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            assert res1.returncode == 0, f"Pass 1 failed: {res1.stderr}"
            assert fake_anchor.exists(), "Anchor file not created"
            content1 = fake_anchor.read_text()
            for rule in EXPECTED_RULES:
                assert rule in content1, f"Missing rule in anchor: {rule}"

            # Pass 2: Idempotent run should not duplicate or change content
            res2 = subprocess.run(
                ["bash", str(INSTALL_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            assert res2.returncode == 0, f"Pass 2 failed: {res2.stderr}"
            content2 = fake_anchor.read_text()
            assert content1 == content2, "Idempotency violated: content modified on second pass"

    def test_verify_script_detects_missing_and_drifted_anchor(self, darwin_uname_env) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_anchor = Path(tmpdir) / "com.perpetua-tools.egress-deny"
            env = {**darwin_uname_env, "PF_ANCHOR_FILE": str(fake_anchor), "PFCTL_SKIP": "1"}

            # Missing anchor -> non-zero exit
            res_missing = subprocess.run(
                ["bash", str(VERIFY_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            assert res_missing.returncode != 0, "Verify should fail when anchor is missing"

            # Corrupted / drifted anchor -> non-zero exit
            fake_anchor.write_text("pass out quick all\n")
            res_corrupt = subprocess.run(
                ["bash", str(VERIFY_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            assert res_corrupt.returncode != 0, "Verify should fail on drifted anchor"

            # Correct anchor installed -> exit 0 (in PFCTL_SKIP mode)
            subprocess.run(
                ["bash", str(INSTALL_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            res_valid = subprocess.run(
                ["bash", str(VERIFY_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            assert res_valid.returncode == 0, f"Verify should succeed with valid anchor: {res_valid.stderr}"

    def test_installed_rules_are_not_scoped_to_a_single_interface(self, darwin_uname_env) -> None:
        """Regression: `block drop out quick on en0 to <addr>` scopes enforcement
        to interface en0 only -- any outbound route via Wi-Fi, a Thunderbolt/
        USB-C Ethernet dongle, a VPN (utun*), or USB tethering silently bypasses
        every rule on hosts whose default route isn't en0. The installer must
        write interface-unscoped rules (`quick to <addr>`, no `on <iface>`)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_anchor = Path(tmpdir) / "com.perpetua-tools.egress-deny"
            env = {**darwin_uname_env, "PF_ANCHOR_FILE": str(fake_anchor), "PFCTL_SKIP": "1"}
            res = subprocess.run(
                ["bash", str(INSTALL_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            content = fake_anchor.read_text()
            assert "on en0" not in content, (
                f"installed rules are scoped to en0 only, bypassable via any other "
                f"outbound interface:\n{content}"
            )
            for rule in EXPECTED_RULES:
                assert rule in content, f"expected interface-unscoped rule missing: {rule}"

    def test_verifier_does_not_require_bash4_mapfile(self) -> None:
        """macOS ships /bin/bash 3.2; mapfile is bash 4+. install.sh invokes
        the verifier with plain `bash` on Darwin, so the script must not use
        bash-4-only builtins or verification always fails on the target host."""
        verifier_src = VERIFY_SCRIPT.read_text(encoding="utf-8")
        assert "mapfile -t" not in verifier_src, (
            "verify-egress-pf-rules.sh uses bash-4 mapfile, which crashes on "
            "macOS default /bin/bash 3.2"
        )

    def test_verifier_required_rules_match_installer_expected_rules(self) -> None:
        """The verifier's REQUIRED_RULES must be the exact same rule set the
        installer writes -- otherwise the verifier can report success while
        checking for rules the installer never actually installs (or vice
        versa), silently passing regardless of what's really enforced."""
        installer_src = INSTALL_SCRIPT.read_text(encoding="utf-8")
        verifier_src = VERIFY_SCRIPT.read_text(encoding="utf-8")
        for rule in EXPECTED_RULES:
            assert rule in installer_src, f"installer missing rule: {rule}"
            assert rule in verifier_src, f"verifier missing rule: {rule}"

    def test_installer_fails_when_pf_enablement_fails(self, darwin_uname_env, tmp_path) -> None:
        stub_dir = tmp_path / "pfctl-stub"
        stub_dir.mkdir()
        (stub_dir / "pfctl").write_text("#!/bin/bash\nif [[ $1 == -e ]]; then echo enable failed >&2; exit 1; fi\nexit 0\n", encoding="utf-8")
        (stub_dir / "pfctl").chmod(0o755)
        # CI is unprivileged, so the installer invokes sudo. Keep the test
        # hermetic by forwarding its command to the same fake pfctl.
        (stub_dir / "sudo").write_text("#!/bin/bash\nexec \"$@\"\n", encoding="utf-8")
        (stub_dir / "sudo").chmod(0o755)
        env = {
            **darwin_uname_env,
            "PATH": f"{stub_dir}:{darwin_uname_env['PATH']}",
            "PF_ANCHOR_FILE": str(tmp_path / "anchor"),
            "PF_CONF_FILE": str(tmp_path / "pf.conf"),
        }
        result = subprocess.run(["bash", str(INSTALL_SCRIPT)], capture_output=True, text=True, env=env, check=False)
        assert result.returncode != 0
        assert "failed to enable pf" in result.stderr

    def test_verifier_fails_when_pf_is_disabled(self, darwin_uname_env, tmp_path) -> None:
        stub_dir = tmp_path / "pfctl-stub-disabled"
        stub_dir.mkdir()
        fake_anchor = tmp_path / "anchor"
        fake_anchor.write_text("\n".join(EXPECTED_RULES) + "\n", encoding="utf-8")
        (stub_dir / "pfctl").write_text(
            "#!/bin/bash\n"
            "if [[ \"$*\" == *\"-s info\"* ]]; then echo 'Status: Disabled'; exit 0; fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        (stub_dir / "pfctl").chmod(0o755)
        env = {
            **darwin_uname_env,
            "PATH": f"{stub_dir}:{darwin_uname_env['PATH']}",
            "PF_ANCHOR_FILE": str(fake_anchor),
            "PFCTL_SKIP": "0",
        }
        res = subprocess.run(["bash", str(VERIFY_SCRIPT)], capture_output=True, text=True, env=env, check=False)
        assert res.returncode == 3
        assert "pf packet filtering is not enabled" in res.stderr

    def test_verifier_fails_when_loaded_anchor_rules_mismatch(self, darwin_uname_env, tmp_path) -> None:
        stub_dir = tmp_path / "pfctl-stub-mismatch"
        stub_dir.mkdir()
        fake_anchor = tmp_path / "anchor"
        fake_anchor.write_text("\n".join(EXPECTED_RULES) + "\n", encoding="utf-8")
        (stub_dir / "pfctl").write_text(
            "#!/bin/bash\n"
            "if [[ \"$*\" == *\"-s info\"* ]]; then echo 'Status: Enabled for 100 days'; exit 0; fi\n"
            "if [[ \"$*\" == *\"-s rules\"* ]]; then echo 'block drop out quick to 10.0.0.0/8'; exit 0; fi\n"
            "if [[ \"$*\" == *\"-sr\"* ]]; then echo 'anchor \"com.perpetua-tools.egress-deny\"'; exit 0; fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        (stub_dir / "pfctl").chmod(0o755)
        env = {
            **darwin_uname_env,
            "PATH": f"{stub_dir}:{darwin_uname_env['PATH']}",
            "PF_ANCHOR_FILE": str(fake_anchor),
            "PFCTL_SKIP": "0",
        }
        res = subprocess.run(["bash", str(VERIFY_SCRIPT)], capture_output=True, text=True, env=env, check=False)
        assert res.returncode == 3
        assert "loaded rules" in res.stderr

    def test_verifier_fails_when_pass_quick_from_any_precedes_anchor(self, darwin_uname_env, tmp_path) -> None:
        stub_dir = tmp_path / "pfctl-stub-ordering-from-any"
        stub_dir.mkdir()
        fake_anchor = tmp_path / "anchor"
        fake_anchor.write_text("\n".join(EXPECTED_RULES) + "\n", encoding="utf-8")
        loaded_rules = "\n".join(EXPECTED_RULES)
        (stub_dir / "pfctl").write_text(
            f"#!/bin/bash\n"
            f"if [[ \"$*\" == *\"-s info\"* ]]; then echo 'Status: Enabled'; exit 0; fi\n"
            f"if [[ \"$*\" == *\"-s rules\"* ]]; then cat <<'EOF'\n{loaded_rules}\nEOF\nexit 0; fi\n"
            f"if [[ \"$*\" == *\"-sr\"* ]]; then echo 'pass out quick from any to any keep state'; echo 'anchor \"com.perpetua-tools.egress-deny\"'; exit 0; fi\n"
            f"exit 0\n",
            encoding="utf-8",
        )
        (stub_dir / "pfctl").chmod(0o755)
        env = {
            **darwin_uname_env,
            "PATH": f"{stub_dir}:{darwin_uname_env['PATH']}",
            "PF_ANCHOR_FILE": str(fake_anchor),
            "PFCTL_SKIP": "0",
        }
        res = subprocess.run(["bash", str(VERIFY_SCRIPT)], capture_output=True, text=True, env=env, check=False)
        assert res.returncode == 5
        assert "contains broad pass rule before anchor" in res.stderr

    def test_verifier_fails_when_bare_pass_quick_precedes_anchor(self, darwin_uname_env, tmp_path) -> None:
        stub_dir = tmp_path / "pfctl-stub-ordering-bare-quick"
        stub_dir.mkdir()
        fake_anchor = tmp_path / "anchor"
        fake_anchor.write_text("\n".join(EXPECTED_RULES) + "\n", encoding="utf-8")
        loaded_rules = "\n".join(EXPECTED_RULES)
        (stub_dir / "pfctl").write_text(
            f"#!/bin/bash\n"
            f"if [[ \"$*\" == *\"-s info\"* ]]; then echo 'Status: Enabled'; exit 0; fi\n"
            f"if [[ \"$*\" == *\"-s rules\"* ]]; then cat <<'EOF'\n{loaded_rules}\nEOF\nexit 0; fi\n"
            f"if [[ \"$*\" == *\"-sr\"* ]]; then echo 'pass out quick'; echo 'anchor \"com.perpetua-tools.egress-deny\"'; exit 0; fi\n"
            f"exit 0\n",
            encoding="utf-8",
        )
        (stub_dir / "pfctl").chmod(0o755)
        env = {
            **darwin_uname_env,
            "PATH": f"{stub_dir}:{darwin_uname_env['PATH']}",
            "PF_ANCHOR_FILE": str(fake_anchor),
            "PFCTL_SKIP": "0",
        }
        res = subprocess.run(["bash", str(VERIFY_SCRIPT)], capture_output=True, text=True, env=env, check=False)
        assert res.returncode == 5
        assert "contains broad pass rule before anchor" in res.stderr

    def test_verifier_fails_when_broad_pass_rule_precedes_anchor(self, darwin_uname_env, tmp_path) -> None:
        stub_dir = tmp_path / "pfctl-stub-ordering"
        stub_dir.mkdir()
        fake_anchor = tmp_path / "anchor"
        fake_anchor.write_text("\n".join(EXPECTED_RULES) + "\n", encoding="utf-8")
        loaded_rules = "\n".join(EXPECTED_RULES)
        (stub_dir / "pfctl").write_text(
            f"#!/bin/bash\n"
            f"if [[ \"$*\" == *\"-s info\"* ]]; then echo 'Status: Enabled'; exit 0; fi\n"
            f"if [[ \"$*\" == *\"-s rules\"* ]]; then cat <<'EOF'\n{loaded_rules}\nEOF\nexit 0; fi\n"
            f"if [[ \"$*\" == *\"-sr\"* ]]; then echo 'pass out quick all'; echo 'anchor \"com.perpetua-tools.egress-deny\"'; exit 0; fi\n"
            f"exit 0\n",
            encoding="utf-8",
        )
        (stub_dir / "pfctl").chmod(0o755)
        env = {
            **darwin_uname_env,
            "PATH": f"{stub_dir}:{darwin_uname_env['PATH']}",
            "PF_ANCHOR_FILE": str(fake_anchor),
            "PFCTL_SKIP": "0",
        }
        res = subprocess.run(["bash", str(VERIFY_SCRIPT)], capture_output=True, text=True, env=env, check=False)
        assert res.returncode == 5
        assert "contains broad pass rule before anchor" in res.stderr

    def test_verifier_succeeds_when_pfctl_loaded_and_ordered_correctly(self, darwin_uname_env, tmp_path) -> None:
        stub_dir = tmp_path / "pfctl-stub-success"
        stub_dir.mkdir()
        fake_anchor = tmp_path / "anchor"
        fake_anchor.write_text("\n".join(EXPECTED_RULES) + "\n", encoding="utf-8")
        loaded_rules = "\n".join(EXPECTED_RULES)
        (stub_dir / "pfctl").write_text(
            f"#!/bin/bash\n"
            f"if [[ \"$*\" == *\"-s info\"* ]]; then echo 'Status: Enabled'; exit 0; fi\n"
            f"if [[ \"$*\" == *\"-s rules\"* ]]; then cat <<'EOF'\n{loaded_rules}\nEOF\nexit 0; fi\n"
            f"if [[ \"$*\" == *\"-sr\"* ]]; then echo 'anchor \"com.perpetua-tools.egress-deny\"'; echo 'pass out quick proto tcp to any port 443'; exit 0; fi\n"
            f"exit 0\n",
            encoding="utf-8",
        )
        (stub_dir / "pfctl").chmod(0o755)
        env = {
            **darwin_uname_env,
            "PATH": f"{stub_dir}:{darwin_uname_env['PATH']}",
            "PF_ANCHOR_FILE": str(fake_anchor),
            "PFCTL_SKIP": "0",
        }
        res = subprocess.run(["bash", str(VERIFY_SCRIPT), "--json"], capture_output=True, text=True, env=env, check=False)
        assert res.returncode == 0
        assert '"status":"ok"' in res.stdout
