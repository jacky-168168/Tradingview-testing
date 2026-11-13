"""Regression: ETF comparison must never push to main or deploy Pages from PR branches."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class ETFSafePublisher(unittest.TestCase):
    def test_main_only_and_double_guard(self):
        wf=(ROOT/".github/workflows/etf-10ma-compare.yml").read_text("utf-8")
        push=wf.split("  push:\n",1)[1].split("permissions:",1)[0]
        self.assertIn("    branches: [main]",push)
        job=wf.split("jobs:\n  backtest:\n",1)[1].split("    steps:\n",1)[0]
        self.assertIn("github.ref == 'refs/heads/main'",job)
        self.assertIn("github.event_name != 'pull_request'",job)
    def test_independent_ci_checks_branch_gate(self):
        ci=(ROOT/".github/workflows/tw-stock-ci.yml").read_text("utf-8")
        self.assertIn("test_etf_publish_branch_gate.py",ci)
if __name__=="__main__":
    unittest.main()
