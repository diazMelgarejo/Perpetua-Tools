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
        self.assertIn("superseded_by=lesson_cb52a6a3600d", legacy_line)

        original_jsonl, original_md = recall.LESSONS_JSONL, recall.LESSONS_MD
        self.addCleanup(setattr, recall, "LESSONS_JSONL", original_jsonl)
        self.addCleanup(setattr, recall, "LESSONS_MD", original_md)
        recall.LESSONS_JSONL = str(SEMANTIC / "lessons.jsonl")
        recall.LESSONS_MD = str(SEMANTIC / "LESSONS.md")
        recalled_ids = {row["id"] for row in recall._load_structured()}
        self.assertNotIn(OLD_ID, recalled_ids)

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
