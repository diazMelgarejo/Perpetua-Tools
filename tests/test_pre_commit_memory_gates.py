"""Contract tests for the three PR #391 pre-commit hook gaps.

These gates live in scripts/hooks and .githooks/pre-commit. The episodic
checker already has behavioral coverage in test_episodic_append_only.py;
this module pins the hook wiring and the graduated/rejected reviewer rule.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_check_memory_records():
    path = ROOT / "scripts" / "hooks" / "check_memory_records.py"
    spec = importlib.util.spec_from_file_location("check_memory_records", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate(claim: str, **extra) -> dict:
    derived = hashlib.sha256(claim.encode("utf-8")).hexdigest()[:12]
    record = {
        "id": derived,
        "key": "test-key",
        "name": "test-name",
        "claim": claim,
        "status": extra.pop("status", "graduated"),
        "decisions": extra.pop("decisions", []),
    }
    record.update(extra)
    return record


class PreCommitMemoryGateTests(unittest.TestCase):
    def test_provisional_graduation_keeps_the_terminal_reviewer_requirement(self) -> None:
        """Tool-generated provisional status is valid only with a graduation review."""
        checker = _load_check_memory_records()
        for reviewed in (True, False):
            with self.subTest(reviewed=reviewed), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "candidates" / "graduated" / "record.json"
                path.parent.mkdir(parents=True)
                decision = {"action": "graduated" if reviewed else "staged",
                            "reviewer": "reviewer-id", "provisional": True}
                record = _candidate("Provisional graduation preserves review evidence.",
                                    status="provisional", decisions=[decision])
                path.write_text(json.dumps(record), encoding="utf-8")
                problems: list[str] = []
                checker.validate_candidate(path, problems, {}, set())
                if reviewed:
                    self.assertEqual(problems, [])
                else:
                    self.assertTrue(any("reviewer" in item for item in problems))

    def test_run_gates_repo_hygiene_uses_first_arg_after_shift(self) -> None:
        text = (ROOT / "scripts" / "hooks" / "run_gates.sh").read_text(encoding="utf-8")
        self.assertIn('"${1:-$ROOT}"', text)
        self.assertNotIn('"${2:-$ROOT}"', text)

    def test_pre_commit_episodic_gate_uses_worktree_not_committed_head(self) -> None:
        text = (ROOT / ".githooks" / "pre-commit").read_text(encoding="utf-8")
        self.assertIn("--worktree", text)
        self.assertNotIn("--head HEAD", text)

    def test_graduated_candidate_without_terminal_reviewer_is_rejected(self) -> None:
        checker = _load_check_memory_records()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidates" / "graduated" / "record.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    _candidate(
                        "Graduation requires a reviewer.",
                        decisions=[{"action": "staged", "reviewer": "author"}],
                    )
                ),
                encoding="utf-8",
            )
            problems: list[str] = []
            checker.validate_candidate(path, problems, {}, set())
            self.assertTrue(problems)
            self.assertTrue(any("reviewer" in item for item in problems))

    def test_graduated_candidate_with_terminal_reviewer_passes(self) -> None:
        checker = _load_check_memory_records()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidates" / "graduated" / "record.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    _candidate(
                        "Graduation requires a reviewer.",
                        decisions=[{"action": "graduated", "reviewer": "reviewer-id"}],
                    )
                ),
                encoding="utf-8",
            )
            problems: list[str] = []
            checker.validate_candidate(path, problems, {}, set())
            self.assertEqual(problems, [])

    def test_rejected_candidate_requires_nonempty_reviewer(self) -> None:
        checker = _load_check_memory_records()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidates" / "rejected" / "record.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    _candidate(
                        "Rejection also needs a reviewer.",
                        status="rejected",
                        decisions=[{"action": "rejected", "reviewer": "   "}],
                    )
                ),
                encoding="utf-8",
            )
            problems: list[str] = []
            checker.validate_candidate(path, problems, {}, set())
            self.assertTrue(any("reviewer" in item for item in problems))

    def test_staged_lane_does_not_require_terminal_reviewer(self) -> None:
        checker = _load_check_memory_records()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidates" / "staged" / "record.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    _candidate(
                        "Staged records may wait for review.",
                        status="staged",
                        decisions=[],
                    )
                ),
                encoding="utf-8",
            )
            problems: list[str] = []
            checker.validate_candidate(path, problems, {}, set())
            self.assertEqual(problems, [])

    def test_learn_py_pattern_id_is_accepted(self) -> None:
        checker = _load_check_memory_records()
        claim = "Learn.py mints pattern ids from claim and conditions."
        record = _candidate(
            claim,
            status="staged",
            decisions=[],
            conditions=["learn.py", "pattern_id"],
        )
        record["id"] = checker.pattern_id(claim, record["conditions"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidates" / "staged" / "record.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(record), encoding="utf-8")
            problems: list[str] = []
            checker.validate_candidate(path, problems, {}, set())
            self.assertEqual(problems, [])

    def test_invented_candidate_id_is_rejected(self) -> None:
        checker = _load_check_memory_records()
        record = _candidate(
            "Invented ids must still fail the hook.",
            status="staged",
            decisions=[],
        )
        record["id"] = "deadbeefdead"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidates" / "staged" / "record.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(record), encoding="utf-8")
            problems: list[str] = []
            checker.validate_candidate(path, problems, {}, set())
            self.assertTrue(any("deadbeefdead" in item for item in problems))


if __name__ == "__main__":
    unittest.main()


class LegacyIdAllowlistTests(unittest.TestCase):
    ORIGINAL = "Original claim text before a later correction."

    def _write(self, tmp: str, record: dict) -> Path:
        path = Path(tmp) / "candidates" / "graduated" / "record.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(record), encoding="utf-8")
        return path

    def _graduated(self, claim: str, rec_id: str) -> dict:
        record = _candidate(claim, decisions=[{"action": "graduated", "reviewer": "r"}])
        record["id"] = rec_id
        return record

    def test_corrected_claim_passes_with_provable_allowlist_entry(self) -> None:
        checker = _load_check_memory_records()
        minted = hashlib.sha256(self.ORIGINAL.encode("utf-8")).hexdigest()[:12]
        allow = {"entries": [{"id": minted, "original_claim": self.ORIGINAL}]}
        with tempfile.TemporaryDirectory() as tmp:
            allow_path = Path(tmp) / "allow.json"
            allow_path.write_text(json.dumps(allow), encoding="utf-8")
            path = self._write(tmp, self._graduated("Corrected claim text.", minted))
            problems: list[str] = []
            checker.validate_candidate(path, problems, {}, set(), checker.load_id_allowlist(allow_path))
            self.assertEqual(problems, [])

    def test_corrected_claim_without_allowlist_entry_still_fails(self) -> None:
        checker = _load_check_memory_records()
        minted = hashlib.sha256(self.ORIGINAL.encode("utf-8")).hexdigest()[:12]
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, self._graduated("Corrected claim text.", minted))
            problems: list[str] = []
            checker.validate_candidate(path, problems, {}, set(), {})
            self.assertTrue(any("memory-tooling derivation" in p for p in problems))

    def test_fabricated_id_cannot_be_laundered_through_allowlist(self) -> None:
        checker = _load_check_memory_records()
        fake = "deadbeef0000"
        allow = {"entries": [{"id": fake, "original_claim": self.ORIGINAL}]}
        with tempfile.TemporaryDirectory() as tmp:
            allow_path = Path(tmp) / "allow.json"
            allow_path.write_text(json.dumps(allow), encoding="utf-8")
            loaded = checker.load_id_allowlist(allow_path)
            self.assertEqual(loaded, {})
            path = self._write(tmp, self._graduated("Corrected claim text.", fake))
            problems: list[str] = []
            checker.validate_candidate(path, problems, {}, set(), loaded)
            self.assertTrue(any("memory-tooling derivation" in p for p in problems))

    def test_shipped_allowlist_covers_94cbd6e80ee2(self) -> None:
        checker = _load_check_memory_records()
        self.assertIn("94cbd6e80ee2", checker.load_id_allowlist())
