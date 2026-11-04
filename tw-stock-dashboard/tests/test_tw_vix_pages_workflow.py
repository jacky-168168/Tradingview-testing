"""Regression: bot-written TAIFEX VIX JSON changes must reach Pages after Actions completes."""
from pathlib import Path
import re
import unittest
import json

ROOT=Path(__file__).resolve().parents[2]
WORKFLOW=ROOT/".github/workflows/tw-stock-pages.yml"
HOME=ROOT/"tw-stock-dashboard/docs/index.html"
JSON=ROOT/"tw-stock-dashboard/docs/data/research/tw_vix/latest.json"

class TaiwanVixPagesWorkflowTest(unittest.TestCase):
    def test_workflow_run_deploys_after_vix_source_completes(self):
        body=WORKFLOW.read_text(encoding="utf-8")
        self.assertRegex(body,r"(?m)^  workflow_run:\s*$")
        self.assertIn("'Taiwan VIXTWN Homepage Data'",body)
        self.assertIn("github.event.workflow_run.conclusion == 'success'",body)
        self.assertIn("github.event.workflow_run.head_branch == 'main'",body)
        self.assertIn("github.event.workflow_run.event != 'pull_request'",body)

    def test_live_smoke_checks_date_count_and_five_real_ranges(self):
        body=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Verify deployed Taiwan VIX 360-session dataset and selectable homepage chart",body)
        for n in (30,60,90,120,360):
            self.assertIn(f"for period in (30,60,90,120,360)",body)
        self.assertIn("assert len(remote['rows'])==len(local['rows']) and len(remote['rows'])>=360",body)
        self.assertIn("assert remote['asOfDate']==local['asOfDate']",body)
        self.assertIn("PASS LIVE TAIFEX VIX 360",body)
        self.assertIn("if attempt==12:raise",body)

    def test_committed_360_days_are_real_official_history(self):
        html=HOME.read_text(encoding="utf-8")
        for n in (30,60,90,120,360):
            self.assertIn(f'data-tw-vix-range="{n}"',html)
        obj=json.loads(JSON.read_text(encoding="utf-8"))
        self.assertEqual(obj["version"],"TW_VIX_TAIFEX_DAILY_V1")
        self.assertEqual(obj["quality"],"official-taifex-daily-close")
        self.assertGreaterEqual(len(obj["rows"]),360)
        dates=[r["date"] for r in obj["rows"]]
        self.assertEqual(dates,sorted(set(dates)))
        self.assertEqual(obj["asOfDate"],dates[-1])

if __name__=="__main__":
    unittest.main()
