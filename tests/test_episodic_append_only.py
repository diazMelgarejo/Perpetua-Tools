"""Behavioral Git-boundary tests for the episodic append-only checker."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKER = Path(__file__).resolve().parents[1] / "scripts/review/check_episodic_append_only.py"
LOG_PATH = ".agent/memory/episodic/AGENT_LEARNINGS.jsonl"


class EpisodicAppendOnlyTests(unittest.TestCase):
    """Use real Git blobs so semantic equality cannot conceal byte rewrites."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.hooksPath", "/dev/null")
        self.log = self.repo / LOG_PATH
        self.log.parent.mkdir(parents=True)
        self.original = '{"id":1,"text":"café"}\n{"id":2,"text":"unchanged"}\n'.encode()
        self.log.write_bytes(self.original)
        self.base = self.commit()

    def git(self, *args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(self.repo), *args], text=True, stderr=subprocess.PIPE
        ).strip()

    def commit(self) -> str:
        self.git("add", "--all")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def check(self, *, base: str | None = None, head: str | None = None) -> subprocess.CompletedProcess[str]:
        target = ["--worktree"] if head is None else ["--head", head]
        return subprocess.run(
            [sys.executable, str(CHECKER), "--repo", str(self.repo),
             f"--base={base or self.base}", *target],
            text=True, capture_output=True, check=False,
        )

    def assert_rejected(self, expected: str) -> None:
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(expected, result.stderr)

    def test_exact_append_passes_for_worktree_and_committed_head(self) -> None:
        self.log.write_bytes(self.original + '{"id":3,"text":"naïve"}\n'.encode())
        for result in (self.check(), self.check(head=self.commit())):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["appended_records"], 1)

    def test_unchanged_log_passes(self) -> None:
        result = self.check(head=self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["appended_records"], 0)

    def test_semantically_equal_unicode_reserialization_fails(self) -> None:
        rows = [json.loads(line) for line in self.original.splitlines()]
        changed = b"".join((json.dumps(row, ensure_ascii=True) + "\n").encode() for row in rows)
        self.assertEqual(rows, [json.loads(line) for line in changed.splitlines()])
        self.log.write_bytes(changed + b'{"id":3}\n')
        self.assert_rejected("prefix")

    def test_truncation_and_reordering_fail(self) -> None:
        rows = self.original.splitlines(keepends=True)
        for changed in (rows[0], b"".join(reversed(rows))):
            with self.subTest(changed=changed):
                self.log.write_bytes(changed)
                self.assert_rejected("prefix")

    def test_duplicate_historical_records_are_retained(self) -> None:
        self.log.write_bytes(self.original * 2)
        base = self.commit()
        self.log.write_bytes(self.original * 2 + b'{"id":3}\n')
        result = self.check(base=base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["base_records"], 4)

    def test_crlf_historical_bytes_must_survive(self) -> None:
        original = self.original.replace(b"\n", b"\r\n")
        self.log.write_bytes(original)
        base = self.commit()
        self.log.write_bytes(original + b'{"id":3}\n')
        self.assertEqual(self.check(base=base).returncode, 0)
        self.log.write_bytes(self.original + b'{"id":3}\n')
        self.assertEqual(self.check(base=base).returncode, 1)

    def test_invalid_suffixes_fail(self) -> None:
        for suffix in (b'{"id":3}', b"\n", b"\xff\n", b"[]\n",
                       b'{"id":3,"id":4}\n', b'{"score":NaN}\n', b"{broken}\n"):
            with self.subTest(suffix=suffix):
                self.log.write_bytes(self.original + suffix)
                self.assert_rejected("record")

    def test_deleted_file_fails(self) -> None:
        self.log.unlink()
        self.assert_rejected("missing")
        self.assertEqual(self.check(head=self.commit()).returncode, 1)

    def test_symlink_fails_even_when_target_bytes_match(self) -> None:
        target = self.repo / "target"
        target.write_bytes(self.original)
        self.log.unlink()
        self.log.symlink_to(target)
        self.assert_rejected("regular")
        self.assertEqual(self.check(head=self.commit()).returncode, 1)

    def test_executable_file_mode_fails(self) -> None:
        self.log.chmod(0o755)
        self.assert_rejected("mode")
        self.assertEqual(self.check(head=self.commit()).returncode, 1)

    def test_unknown_or_option_like_revision_fails_closed(self) -> None:
        for revision in ("missing-ref", "--help"):
            with self.subTest(revision=revision):
                result = self.check(base=revision)
                self.assertEqual(result.returncode, 1)
                self.assertIn("Git", result.stderr)

    def test_initial_log_is_allowed_only_with_valid_new_records(self) -> None:
        self.log.unlink()
        empty_base = self.commit()
        self.log.write_bytes(b'{"id":1}\n')
        self.assertEqual(self.check(base=empty_base).returncode, 0)
        self.log.write_bytes(b"broken\n")
        self.assertEqual(self.check(base=empty_base).returncode, 1)

    def test_git_head_does_not_silently_read_worktree(self) -> None:
        self.log.write_bytes(b"corrupted\n")
        self.assertEqual(self.check(head=self.base).returncode, 0)
        self.assert_rejected("prefix")


if __name__ == "__main__":
    unittest.main()
