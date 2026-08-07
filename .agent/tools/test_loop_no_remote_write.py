"""Regression guard for pr-babysitter's no-remote-write contract.

approval.before_first_mutating_run / before_external_write only gate WHEN a
human is asked to approve -- they do not deny anything by themselves. The
actual hard block is that pr-babysitter's executor profile ("reporter", in
.agent/loops/harnesses.json) carries an empty capabilities list, so
harness_manager/loops/runner.py's own gate (`"external_write" in
maker["capabilities"]`) can never be satisfied regardless of approval.

That gate lives in the vendored harness_manager, which is not blended into
.agent/ and must not be hand-edited here (see scripts/git/agentic-stack-vendor.md
"union-merge doctrine"). This test guards the one thing PT does own: the
"reporter" profile in .agent/loops/harnesses.json must keep capabilities
empty, so a future edit can't silently grant pr-babysitter (or any other
reporter-executor loop) the ability to request external writes.
"""

import json
import unittest
from pathlib import Path

LOOPS_DIR = Path(__file__).resolve().parents[1] / "loops"


class NoRemoteWriteTest(unittest.TestCase):
    def setUp(self):
        self.harnesses = json.loads((LOOPS_DIR / "harnesses.json").read_text(encoding="utf-8"))
        self.pr_babysitter = json.loads((LOOPS_DIR / "pr-babysitter.json").read_text(encoding="utf-8"))

    def test_reporter_profile_has_no_external_write_capability(self):
        reporter = self.harnesses["profiles"]["reporter"]
        self.assertNotIn("external_write", reporter["capabilities"])
        self.assertEqual(reporter["capabilities"], [])

    def test_checker_profile_has_no_external_write_capability(self):
        checker = self.harnesses["profiles"]["checker"]
        self.assertNotIn("external_write", checker["capabilities"])

    def test_pr_babysitter_executor_is_the_capability_less_reporter_profile(self):
        self.assertEqual(self.pr_babysitter["executor"], "reporter")
        executor_capabilities = self.harnesses["profiles"][self.pr_babysitter["executor"]]["capabilities"]
        self.assertNotIn("external_write", executor_capabilities)

    def test_pr_babysitter_does_not_mutate_the_workspace(self):
        reporter = self.harnesses["profiles"][self.pr_babysitter["executor"]]
        self.assertFalse(reporter["mutates_workspace"])


if __name__ == "__main__":
    unittest.main()
