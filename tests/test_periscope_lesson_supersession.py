"""Regression coverage for the Periscope lesson supersession repair."""

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".agent" / "memory"))
sys.path.insert(0, str(REPO_ROOT / ".agent" / "tools"))

import recall  # noqa: E402
from render_lessons import render_lessons_as_text  # noqa: E402


SEMANTIC = REPO_ROOT / ".agent" / "memory" / "semantic"
OLD_ID = "lesson_757476abb44e"
AUTHORIZATION_ID = "lesson_fad3af10b7cd"
LEGACY_ID = "lesson_legacy_98de53b747ff"
AGGREGATE_ID = "lesson_cb52a6a3600d"
SCOPE_RULE_ID = "lesson_7bc8852a44b6"
FOCUSED_IDS = {
    "lesson_8c228d4bfa25",
    "lesson_b85d462f63ae",
    "lesson_d1d4be1ab678",
}
SCOPE_CANDIDATE = REPO_ROOT / ".agent" / "memory" / "candidates" / "graduated" / "7bc8852a44b6.json"


def _latest_lessons_by_id():
    latest = {}
    for line in (SEMANTIC / "lessons.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[row["id"]] = row
    return latest


class PeriscopeLessonSupersessionTests(unittest.TestCase):
    """Do not let a prose-only supersession retire unrelated recall guidance."""
    def test_authorization_lesson_structurally_supersedes_bundle(self):
        lessons = _latest_lessons_by_id()

        self.assertEqual(lessons[AUTHORIZATION_ID]["supersedes"], OLD_ID)
        self.assertEqual(lessons[LEGACY_ID]["status"], "legacy")

        rendered = render_lessons_as_text(str(SEMANTIC))
        old_line = next(line for line in rendered.splitlines() if f"id={OLD_ID}" in line)
        self.assertTrue(old_line.startswith("- ~~"))
        self.assertIn(f"superseded_by={AUTHORIZATION_ID}", old_line)
        legacy_line = next(line for line in rendered.splitlines() if f"id={LEGACY_ID}" in line)
        self.assertTrue(legacy_line.startswith("- ~~"))
        self.assertIn(f"superseded_by={AGGREGATE_ID}", legacy_line)
        aggregate_line = next(line for line in rendered.splitlines() if f"id={AGGREGATE_ID}" in line)
        self.assertTrue(aggregate_line.startswith("- ~~"))
        self.assertIn(f"superseded_by={SCOPE_RULE_ID}", aggregate_line)
        self.assertEqual(lessons[SCOPE_RULE_ID]["supersedes"], AGGREGATE_ID)
        candidate = json.loads(SCOPE_CANDIDATE.read_text(encoding="utf-8"))
        self.assertEqual(
            set(candidate["related_lesson_ids"]),
            {AGGREGATE_ID, *FOCUSED_IDS},
        )

        original_jsonl, original_md = recall.LESSONS_JSONL, recall.LESSONS_MD
        self.addCleanup(setattr, recall, "LESSONS_JSONL", original_jsonl)
        self.addCleanup(setattr, recall, "LESSONS_MD", original_md)
        recall.LESSONS_JSONL = str(SEMANTIC / "lessons.jsonl")
        recall.LESSONS_MD = str(SEMANTIC / "LESSONS.md")
        recalled_ids = {row["id"] for row in recall._load_structured()}
        self.assertNotIn(OLD_ID, recalled_ids)
        self.assertNotIn(AGGREGATE_ID, recalled_ids)
        self.assertIn(SCOPE_RULE_ID, recalled_ids)
        self.assertTrue(FOCUSED_IDS <= recalled_ids)

        retained_claims = [
            "already invalidated watch",
            "Never label a CI failure flaky",
            "Treat discovery, publication, review, and merge",
        ]
        accepted_claims = [
            row["claim"] for row in lessons.values() if row.get("status") == "accepted"
        ]
        for claim in retained_claims:
            self.assertTrue(any(claim in accepted for accepted in accepted_claims))

    def test_bullet_rendering_never_emits_unpaired_strikethrough(self):
        """A status row whose stored claim already carries a fossilized,
        unpaired ~~ (a relic of the original bug's own broken output being
        re-ingested by a prior migration pass) must not propagate that
        fossil into rendered output, regardless of status or supersession.
        """
        from render_lessons import _bullet_for

        fossil = {
            "id": "lesson_legacy_test_fossil",
            "claim": "~~A fossilized leading delimiter with no matching close.",
            "status": "legacy",
        }
        bullet = _bullet_for(fossil, superseded_by={})
        self.assertEqual(bullet.count("~~") % 2, 0, bullet)
        self.assertNotIn("~~~~", bullet)

        rendered = render_lessons_as_text(str(SEMANTIC))
        self.assertEqual(rendered.count("~~") % 2, 0)

    def test_every_accepted_graduated_candidate_is_present_in_lessons_jsonl(self):
        """Regression for the actual failure this suite exists to catch: a
        commit (294f5ec9, 2026-09-09) intended to add one new lesson instead
        net-deleted 34 lines from lessons.jsonl, silently dropping 31
        previously-accepted records with no error, no test failure at the
        time, and no indication anything was wrong until this file's own
        supersession test happened to reference one of the dropped IDs.
        Runs against the real repository's real candidate/lessons files,
        not a synthetic fixture -- lesson_99bda2060ce7 (itself one of the
        records this exact bug dropped) states precisely why: isolated
        fixtures can all pass while the real tracked content silently
        diverges, because concurrent edits accumulate content no fixture
        modeled.
        """
        graduated_dir = REPO_ROOT / ".agent" / "memory" / "candidates" / "graduated"
        lessons = _latest_lessons_by_id()

        missing = []
        for path in sorted(graduated_dir.glob("*.json")):
            candidate = json.loads(path.read_text(encoding="utf-8"))
            if candidate.get("status") != "accepted":
                continue
            expected_id = f"lesson_{candidate['id']}"
            if expected_id not in lessons:
                missing.append(expected_id)

        self.assertEqual(
            missing, [],
            f"{len(missing)} accepted graduated candidate(s) are missing "
            f"from lessons.jsonl -- the exact failure mode this test exists "
            f"to catch: {missing}",
        )

    def test_every_supersedes_field_is_hashable(self):
        """superseded_by_map() uses each row's supersedes value as a dict
        key -- a list there (found during this same repair, in a candidate
        whose claim genuinely referenced two other lessons but whose
        supersedes field was never narrowed to the single schema-conforming
        target) crashes rendering with an unhashable-type TypeError. Catch
        this shape error directly, against the real file, before it can
        reach render_lessons() and break every future regeneration."""
        lessons = _latest_lessons_by_id()
        bad = {
            lid: row["supersedes"]
            for lid, row in lessons.items()
            if row.get("supersedes") is not None
            and not isinstance(row["supersedes"], str)
        }
        self.assertEqual(bad, {}, f"non-string supersedes field(s): {bad}")

