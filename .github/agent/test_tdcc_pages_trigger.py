"""Regression: verified TDCC weekly data must trigger Pages after the collector finishes.

The collector commits with GITHUB_TOKEN; those commits do not start ordinary
push-triggered workflows. The independent workflow_run completion is required.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / ".github/workflows/tw-stock-pages.yml"
TDCC = ROOT / ".github/workflows/tdcc-whale-weekly.yml"


class TDCCPagesTriggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = PAGES.read_text(encoding="utf-8")
        cls.tdcc = TDCC.read_text(encoding="utf-8")

    def test_tdcc_completion_is_an_explicit_pages_trigger(self):
        self.assertIn("  workflow_run:\n", self.pages)
        completion = self.pages.split("  workflow_run:\n", 1)[1].split("  push:\n", 1)[0]
        self.assertIn("'TDCC Whale Shareholder Weekly'", completion)
        self.assertIn("types: [completed]", completion)
        self.assertIn("branches: [main]", completion)

    def test_only_successful_trusted_main_collector_may_deploy(self):
        self.assertIn("github.event.workflow_run.conclusion == 'success'", self.pages)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", self.pages)
        self.assertIn("github.event.workflow_run.event != 'pull_request'", self.pages)
        self.assertIn("tw-stock-dashboard/docs/data/research/tdcc_whales/**", self.pages)

    def test_collector_publishes_snapshot_before_completion(self):
        self.assertIn("name: TDCC Whale Shareholder Weekly", self.tdcc)
        self.assertIn("if: github.ref == 'refs/heads/main'", self.tdcc)
        self.assertIn("git add tw-stock-dashboard/docs/data/research/tdcc_whales", self.tdcc)
        self.assertIn('git push origin HEAD:"$GITHUB_REF_NAME"', self.tdcc)
        self.assertIn("  workflow_dispatch:\n", self.pages)
        # Sunday fallback is not enough if the collector is manually rerun later.
        self.assertIn("30 3 * * 0", self.pages)


if __name__ == "__main__":
    unittest.main()
