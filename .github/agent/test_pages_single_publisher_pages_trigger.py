"""Regression: specialized data collectors must not race GitHub Pages deployments."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
class SinglePagesPublisher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wf=ROOT/".github/workflows"
        cls.pages=(wf/"tw-stock-pages.yml").read_text("utf-8")
        cls.etf=(wf/"etf-10ma-compare.yml").read_text("utf-8")
        cls.upstream=(wf/"upstream-industry-map.yml").read_text("utf-8")
    def test_both_sources_notify_central_deployment(self):
        hook=self.pages.split("  workflow_run:\n",1)[1].split("  push:\n",1)[0]
        self.assertIn("'ETF 00631L 00685L 10MA Comparison'",hook)
        self.assertIn("'TPEx Upstream Industry Chain Stock Map'",hook)
        self.assertIn("github.event.workflow_run.conclusion == 'success'",self.pages)
        self.assertIn("github.event.workflow_run.head_branch == 'main'",self.pages)
        self.assertIn("github.event.workflow_run.event != 'pull_request'",self.pages)
    def test_source_jobs_do_not_deploy_pages_concurrently(self):
        for workflow in (self.etf,self.upstream):
            self.assertNotIn("actions/deploy-pages@",workflow)
            self.assertNotIn("actions/upload-pages-artifact@",workflow)
            self.assertIn("deploy via trusted workflow_run TW Stock Pages",workflow)
            self.assertIn("github.ref == 'refs/heads/main'",workflow)
    def test_source_files_remain_published_with_provenance(self):
        self.assertIn("git add tw-stock-dashboard/docs/data/research/etf_10ma_comparison/latest.json",self.etf)
        self.assertIn("git add tw-stock-dashboard/docs/data/industry_upstream/latest.json",self.upstream)
        self.assertIn("ETF Pages data stale",self.pages)
        self.assertIn("Upstream Pages data stale",self.pages)
if __name__=="__main__":
    unittest.main()
