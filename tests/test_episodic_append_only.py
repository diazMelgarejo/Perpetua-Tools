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
        """Helper: setUp."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.hooksPath", "/dev/null")
        self.git("config", "core.autocrlf", "false")  # byte-exact blobs regardless of host defaults
        self.log = self.repo / LOG_PATH
        self.log.parent.mkdir(parents=True)
        self.original = '{"id":1,"text":"café"}\n{"id":2,"text":"unchanged"}\n'.encode()
        self.log.write_bytes(self.original)
        self.base = self.commit()

    def git(self, *args: str) -> str:
        """Helper: git."""
        return subprocess.check_output(
            ["git", "-C", str(self.repo), *args], text=True, stderr=subprocess.PIPE
        ).strip()

    def commit(self) -> str:
        """Helper: commit."""
        self.git("add", "--all")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def check(self, *, base: str | None = None, head: str | None = None) -> subprocess.CompletedProcess[str]:
        """Helper: check."""
        target = ["--worktree"] if head is None else ["--head", head]
        return subprocess.run(
            [sys.executable, str(CHECKER), "--repo", str(self.repo),
             f"--base={base or self.base}", *target],
            text=True, capture_output=True, check=False,
        )

    def assert_rejected(self, expected: str) -> None:
        """Helper: assert rejected."""
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(expected, result.stderr)

    def test_exact_append_passes_for_worktree_and_committed_head(self) -> None:
        """Check that exact append passes for worktree and committed head."""
        self.log.write_bytes(self.original + '{"id":3,"text":"naïve"}\n'.encode())
        for result in (self.check(), self.check(head=self.commit())):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["appended_records"], 1)

    def test_unchanged_log_passes(self) -> None:
        """Check that unchanged log passes."""
        result = self.check(head=self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["appended_records"], 0)

    def test_semantically_equal_unicode_reserialization_fails(self) -> None:
        """Check that semantically equal unicode reserialization fails."""
        rows = [json.loads(line) for line in self.original.splitlines()]
        changed = b"".join((json.dumps(row, ensure_ascii=True) + "\n").encode() for row in rows)
        self.assertEqual(rows, [json.loads(line) for line in changed.splitlines()])
        self.log.write_bytes(changed + b'{"id":3}\n')
        self.assert_rejected("prefix")

    def test_truncation_and_reordering_fail(self) -> None:
        """Check that truncation and reordering fail."""
        rows = self.original.splitlines(keepends=True)
        for changed in (rows[0], b"".join(reversed(rows))):
            with self.subTest(changed=changed):
                self.log.write_bytes(changed)
                self.assert_rejected("prefix")

    def test_duplicate_historical_records_are_retained(self) -> None:
        """Check that duplicate historical records are retained."""
        self.log.write_bytes(self.original * 2)
        base = self.commit()
        self.log.write_bytes(self.original * 2 + b'{"id":3}\n')
        result = self.check(base=base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["base_records"], 4)

    def test_crlf_historical_bytes_must_survive(self) -> None:
        """Check that crlf historical bytes must survive."""
        original = self.original.replace(b"\n", b"\r\n")
        self.log.write_bytes(original)
        base = self.commit()
        self.log.write_bytes(original + b'{"id":3}\n')
        self.assertEqual(self.check(base=base).returncode, 0)
        self.log.write_bytes(self.original + b'{"id":3}\n')
        self.assertEqual(self.check(base=base).returncode, 1)

    def test_invalid_suffixes_fail(self) -> None:
        """Check that invalid suffixes fail."""
        for suffix in (b'{"id":3}', b"\n", b"\xff\n", b"[]\n",
                       b'{"id":3,"id":4}\n', b'{"score":NaN}\n', b"{broken}\n"):
            with self.subTest(suffix=suffix):
                self.log.write_bytes(self.original + suffix)
                self.assert_rejected("record")

    def test_deleted_file_fails(self) -> None:
        """Check that deleted file fails."""
        self.log.unlink()
        self.assert_rejected("missing")
        self.assertEqual(self.check(head=self.commit()).returncode, 1)

    def test_symlink_fails_even_when_target_bytes_match(self) -> None:
        """Check that symlink fails even when target bytes match."""
        target = self.repo / "target"
        target.write_bytes(self.original)
        self.log.unlink()
        try:
            self.log.symlink_to(target)
        except OSError as exc:  # Windows without the symlink privilege
            self.skipTest(f"cannot create symlinks on this host: {exc}")
        self.assert_rejected("regular")
        self.assertEqual(self.check(head=self.commit()).returncode, 1)

    @unittest.skipIf(sys.platform == "win32", "NTFS has no POSIX exec bit to set via chmod")
    def test_executable_file_mode_fails(self) -> None:
        """Check that executable file mode fails."""
        self.log.chmod(0o755)
        self.assert_rejected("mode")
        self.assertEqual(self.check(head=self.commit()).returncode, 1)

    def test_unknown_or_option_like_revision_fails_closed(self) -> None:
        """Check that unknown or option like revision fails closed."""
        for revision in ("missing-ref", "--help"):
            with self.subTest(revision=revision):
                result = self.check(base=revision)
                self.assertEqual(result.returncode, 1)
                self.assertIn("Git", result.stderr)

    def test_initial_log_is_allowed_only_with_valid_new_records(self) -> None:
        """Check that initial log is allowed only with valid new records."""
        self.log.unlink()
        empty_base = self.commit()
        self.log.write_bytes(b'{"id":1}\n')
        self.assertEqual(self.check(base=empty_base).returncode, 0)
        self.log.write_bytes(b"broken\n")
        self.assertEqual(self.check(base=empty_base).returncode, 1)

    def test_git_head_does_not_silently_read_worktree(self) -> None:
        """Check that git head does not silently read worktree."""
        self.log.write_bytes(b"corrupted\n")
        self.assertEqual(self.check(head=self.base).returncode, 0)
        self.assert_rejected("prefix")


if __name__ == "__main__":
    unittest.main()
