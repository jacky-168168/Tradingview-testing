"""Regression: an independent data publisher must trigger Pages + expose real JSON."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PAGES=ROOT/".github/workflows/tw-stock-pages.yml"
ASTRO=ROOT/".github/workflows/financial-astrology.yml"
DETAIL=ROOT/"tw-stock-dashboard/docs/financial-astrology.html"
DATA=ROOT/"tw-stock-dashboard/docs/data/financial_astrology/report.json"

class FinancialAstrologyPublishingTests(unittest.TestCase):
    def test_pages_listens_to_independent_astro_success(self):
        pages=PAGES.read_text(encoding="utf-8")
        self.assertIn("'Financial Astrology Research V1'",pages)
        self.assertIn("github.event.workflow_run.conclusion == 'success'",pages)
        self.assertIn("name: Verify live financial astrology data",pages)
        self.assertIn("Pages research data stale",pages)
        self.assertIn("financial-astrology.html",pages)
    def test_pages_deploy_uses_unique_artifact_and_never_cancels_other_deploys(self):
        pages=PAGES.read_text(encoding="utf-8")
        self.assertIn("group: tw-stock-pages",pages)
        self.assertIn("cancel-in-progress: false",pages)
        self.assertIn("name: github-pages-",pages)
        self.assertIn("artifact_name: github-pages-",pages)
        self.assertIn("github.run_id",pages)
        self.assertIn("github.run_attempt",pages)
        self.assertIn("name: Wait briefly for preceding Pages deployment to settle",pages)
    def test_research_json_is_never_published_from_pr_preview(self):
        workflow=ASTRO.read_text(encoding="utf-8")
        self.assertIn("if: github.event_name == 'pull_request'",workflow)
        self.assertIn("permissions:\n      contents: read",workflow)
        self.assertIn("if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch' || github.event_name == 'push'",workflow)
        self.assertIn("tw-stock-dashboard/docs/data/financial_astrology/event_catalog.json",workflow)
        self.assertIn("--catalog=",workflow)
        self.assertIn("financial-astrology-real-data-preview",workflow)
    def test_unavailable_report_cannot_fabricate_market_wins(self):
        if not DATA.exists():self.skipTest("Prelaunch data will be generated from real closes")
        payload=json.loads(DATA.read_text(encoding="utf-8"))
        self.assertIs(payload.get("researchOnly"),True)
        self.assertIs(payload.get("strategySignal"),False)
        for market,result in payload.get("reports",{}).items():
            if result.get("status")!="ok":
                for h in result.get("horizons",[]):
                    self.assertFalse(h.get("sampleSize",0)>0,market)
        detail=DETAIL.read_text(encoding="utf-8")
        for node in ("astroCredibility","astroObservedN","astroMarketDirection"):
            self.assertIn('id="'+node+'"',detail)

if __name__=="__main__":unittest.main()
