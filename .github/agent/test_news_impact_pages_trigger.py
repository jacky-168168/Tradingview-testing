"""Prevent bot-originated news-impact snapshots silently missing Pages updates."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class NewsImpactPagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages=(ROOT/".github/workflows/tw-stock-pages.yml").read_text("utf-8")
        cls.ci=(ROOT/".github/workflows/tw-stock-ci.yml").read_text("utf-8")
        cls.news=(ROOT/".github/workflows/news-impact-intelligence.yml").read_text("utf-8")
    def test_news_completion_with_main_success_guard(self):
        section=self.pages.split("  workflow_run:\n",1)[1].split("  push:\n",1)[0]
        self.assertIn("'Global Market News Impact'",section)
        self.assertIn("types: [completed]",section)
        self.assertIn("branches: [main]",section)
        self.assertIn("github.event.workflow_run.conclusion == 'success'",self.pages)
        self.assertIn("github.event.workflow_run.head_branch == 'main'",self.pages)
        self.assertIn("github.event.workflow_run.event != 'pull_request'",self.pages)
    def test_news_archive_and_js_have_deploy_events_and_cdn_date_gate(self):
        self.assertIn("tw-stock-dashboard/docs/data/news_impact/**",self.pages)
        self.assertIn("tw-stock-dashboard/docs/news-impact.js",self.pages)
        self.assertIn("git add tw-stock-dashboard/docs/data/news_impact/history.json",self.news)
        self.assertIn("News Pages JSON behind artifact",self.pages)
        self.assertIn("News impact history Pages JSON stale",self.pages)
        self.assertIn("Official event study Pages JSON stale",self.pages)
    def test_pages_scripts_check_and_ci(self):
        self.assertIn('for js in tw-stock-dashboard/docs/*.js; do node --check "$js"; done',self.pages)
        self.assertIn("test_*pages_trigger.py",self.ci)
    def test_daily_fallback_not_high_frequency(self):
        schedule=self.pages.split("  schedule:\n",1)[1].split("  workflow_run:\n",1)[0]
        self.assertEqual(schedule.count("50 15 * * *"),1)
if __name__=="__main__":
    unittest.main()
