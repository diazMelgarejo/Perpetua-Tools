"""Commit-check: Cursor bootstrap shell scripts stay git mode 100755."""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "hooks" / "check_tracked_script_mode.py"


class TrackedScriptModeTests(unittest.TestCase):
    def test_cloud_bootstrap_invokes_seeder_by_file_presence(self) -> None:
        text = (ROOT / "scripts" / "cursor" / "cloud-bootstrap.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "-f scripts/cursor/ci-bootstrap-private-attribution.sh",
            text,
        )
        self.assertNotIn("-x scripts/cursor/", text)

    def test_pre_commit_dispatches_script_mode_gate(self) -> None:
        text = (ROOT / ".githooks" / "pre-commit").read_text(encoding="utf-8")
        self.assertIn("script-mode", text)
        dispatcher = (ROOT / "scripts" / "hooks" / "run_gates.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("check_tracked_script_mode.py", dispatcher)

    def test_seeder_and_sync_are_git_mode_100755(self) -> None:
        for path in (
            "scripts/cursor/ci-bootstrap-private-attribution.sh",
            "scripts/cursor/sync-private-attribution-from-home.sh",
        ):
            with self.subTest(path=path):
                line = subprocess.check_output(
                    ["git", "-C", str(ROOT), "ls-files", "-s", "--", path],
                    text=True,
                ).strip()
                self.assertTrue(line, f"{path} is not in the index")
                self.assertTrue(
                    line.startswith("100755 "),
                    f"{path} git mode is {line.split()[0]}, need 100755",
                )

    def test_checker_passes_on_this_index(self) -> None:
        result = subprocess.run(
            ["python3", str(CHECKER)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
