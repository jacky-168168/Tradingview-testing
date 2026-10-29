"""Regression: a bot-dispatched LUNA data commit must have a daily Pages fallback.

A successful LUNA workflow_dispatch may be followed by no Pages workflow_run.
This verifies a low-frequency fallback, not actual GitHub cron delivery or CDN freshness.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / ".github/workflows/tw-stock-pages.yml"
LUNA = ROOT / ".github/workflows/luna-social-sentiment.yml"


class LunaPagesFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = PAGES.read_text(encoding="utf-8")
        cls.luna = LUNA.read_text(encoding="utf-8")

    def test_luna_success_remains_a_pages_completion_trigger(self):
        self.assertIn("  workflow_run:\n", self.pages)
        section = self.pages.split("  workflow_run:\n", 1)[1].split("  push:\n", 1)[0]
        self.assertIn("'LUNA Public Social Sentiment'", section)
        self.assertIn("types: [completed]", section)
        self.assertIn("branches: [main]", section)

    def test_daily_fallback_is_after_last_planned_luna_run(self):
        schedule = self.pages.split("  schedule:\n", 1)[1].split("  workflow_run:\n", 1)[0]
        self.assertIn("- cron: '50 15 * * *'", schedule)
        self.assertEqual(schedule.count("50 15 * * *"), 1)
        self.assertIn("- cron: '30 3 * * 0'", schedule)
        self.assertIn("10 1,3,5,9,13 * * *", self.luna)

    def test_trusted_completion_guard_and_source_publish_preserved(self):
        self.assertIn("github.event.workflow_run.conclusion == 'success'", self.pages)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", self.pages)
        self.assertIn("github.event.workflow_run.event != 'pull_request'", self.pages)
        self.assertIn("tw-stock-dashboard/docs/data/social_sentiment/**", self.pages)
        self.assertIn("git add -A tw-stock-dashboard/docs/data/social_sentiment/", self.luna)
        self.assertIn("  workflow_dispatch:\n", self.pages)
        self.assertIn("  cancel-in-progress: true", self.pages)


if __name__ == "__main__":
    unittest.main()
