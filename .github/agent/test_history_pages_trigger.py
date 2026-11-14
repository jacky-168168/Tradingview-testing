"""Regression: verified history retries must lead to a fresh Pages deployment.

Actions commits using GITHUB_TOKEN do not generate downstream push workflows.
Use a trusted workflow_run completion and retain the original deploy safety gate.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / ".github/workflows/tw-stock-pages.yml"
RETRY = ROOT / ".github/workflows/backfill-extended-market-retry.yml"
COLLECT = ROOT / ".github/workflows/collect-market-risk-history.yml"
CI = ROOT / ".github/workflows/tw-stock-ci.yml"


class HistoryPagesTriggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = PAGES.read_text(encoding="utf-8")
        cls.retry = RETRY.read_text(encoding="utf-8")
        cls.collect = COLLECT.read_text(encoding="utf-8")
        cls.ci = CI.read_text(encoding="utf-8")

    def test_daily_history_retry_completion_is_a_pages_trigger(self):
        completion = self.pages.split("  workflow_run:\n", 1)[1].split("  push:\n", 1)[0]
        self.assertIn("'Retry Date-Locked TWSE History with Throttling'", completion)
        self.assertIn("types: [completed]", completion)
        self.assertIn("branches: [main]", completion)
        self.assertIn("'TDCC Whale Shareholder Weekly'", completion)

    def test_deploy_only_after_successful_trusted_main_run(self):
        self.assertIn("github.event.workflow_run.conclusion == 'success'", self.pages)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", self.pages)
        self.assertIn("github.event.workflow_run.event != 'pull_request'", self.pages)
        self.assertIn("  workflow_dispatch:\n", self.pages)

    def test_direct_main_archive_updates_are_in_push_paths(self):
        self.assertIn("'tw-stock-dashboard/docs/data/research/g_regime_3y/**'", self.pages)
        self.assertIn("'tw-stock-dashboard/docs/data/research/market_history_extended/**'", self.pages)
        self.assertIn("    branches: [main]", self.pages)

    def test_retry_and_collector_publish_archive_without_fabrication(self):
        self.assertIn("name: Retry Date-Locked TWSE History with Throttling", self.retry)
        self.assertIn("git push origin HEAD:main", self.retry)
        self.assertIn("tw-stock-dashboard/docs/data/research/market_history_extended/summary.json", self.retry)
        self.assertIn("name: Collect Three-Year Official Market Risk History", self.collect)
        self.assertIn("tw-stock-dashboard/docs/data/research/g_regime_3y/coverage.json", self.collect)

    def test_regression_is_wired_into_independent_ci(self):
        self.assertIn("test_*pages_trigger.py", self.ci)
        self.assertIn("python -m unittest discover -s .github/agent", self.ci)


if __name__ == "__main__":
    unittest.main()
