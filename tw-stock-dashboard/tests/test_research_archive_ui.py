"""Ensure the visible backtest page contains all permanently archived 2026 studies."""
from __future__ import annotations
import json,re,unittest
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"docs"
FILES=ROOT/"data/research_archive"
IDS={"researchArchive","raModel","raStyle","raHorizon","raSort","raCount","raBest",
     "raBestNet","raMatrixBody","raMatrixNote","raPeriod","raStatus","raHHistory","raH5Table",
     "raGStatus","raGCompare","raGRepeat","raTradeModel","raTradeHorizon","raTradeStyle",
     "raTradeSearch","raTradeStatus","raTradeBody","raPrev","raNext","raAnnualNote","raReload"}
class Reader(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if "id" in d:self.ids.append(d["id"])
class ArchiveUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page=(ROOT/"backtest.html").read_text(encoding="utf-8")
        cls.index=(ROOT/"index.html").read_text(encoding="utf-8")
        cls.meta=json.loads((FILES/"index.json").read_text(encoding="utf-8"))
        cls.matrix=json.loads((FILES/cls.meta["files"]["matrix"]).read_text(encoding="utf-8"))
    def test_still_has_original_backtest(self):
        self.assertIn('id="modelTabs"',self.page)
        self.assertIn('id="gView"',self.page)
        self.assertIn('id="legacyView"',self.page)
        self.assertIn('id="researchArchive"',self.page)
        self.assertIn('src="./backtest-g-panel.js"',self.page)
        self.assertIn('src="./backtest-research.js"',self.page)
        self.assertIn('backtest.html#researchArchive',self.index)
    def test_unique_elements_and_all_controls(self):
        h=Reader();h.feed(self.page)
        self.assertEqual(len(h.ids),len(set(h.ids)),"duplicate DOM IDs")
        self.assertTrue(IDS<=set(h.ids),IDS-set(h.ids))
        js=(ROOT/"backtest-research.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML=matrix",js)
        self.assertIn("escape(",js)
    def test_every_archive_is_a_permanent_file(self):
        for kind,file in self.meta["files"].items():
            path=FILES/file
            with self.subTest(kind=kind):
                self.assertTrue(path.exists(),str(path))
                self.assertGreater(path.stat().st_size,100)
                json.loads(path.read_text(encoding="utf-8"))
    def test_sixty_six_frozen_comparisons(self):
        self.assertEqual(len(self.matrix["results"]),11)
        cells=[(model,int(h),m,s) for model,days in self.matrix["results"].items() for h,styles in days.items() for m,s in styles.items()]
        self.assertEqual(len(cells),66)
        for model,h,m,s in cells:
            with self.subTest(model=model,h=h,method=m):
                self.assertIn(h,(5,10,20))
                self.assertIn(m,("ladder","ma"))
                self.assertLessEqual(s["filled"],s["signalEvents"])
                self.assertGreaterEqual(s["avgTranches"] if s["filled"] else 0,0)
                self.assertTrue("perEligibleSignalAvgNetOnReservedPct" in s)
    def test_complete_trades_covered_by_matrix(self):
        alltrades=json.loads((FILES/self.meta["files"]["matrixTrades"]).read_text(encoding="utf-8"))
        for model,periods in self.matrix["results"].items():
            for h,methods in periods.items():
                for m,stat in methods.items():
                    with self.subTest(model=model,h=h,mode=m):
                        rows=alltrades[model][h][m]
                        self.assertEqual(len(rows),stat["signalEvents"])
    def test_research_values_match_published_run(self):
        results=self.matrix["results"]
        self.assertAlmostEqual(results["H5_FRESH_BREAK"]["10"]["ladder"]["perEligibleSignalAvgNetOnReservedPct"],1.058)
        self.assertAlmostEqual(results["G_BROAD"]["10"]["ma"]["perEligibleSignalAvgNetOnReservedPct"],.435)
        self.assertAlmostEqual(results["G_DOUBLE_PERSIST"]["10"]["ladder"]["perEligibleSignalAvgNetOnReservedPct"],-.015)
    def test_legacy_yearly_backtest_data_still_present(self):
        for year in (2023,2024,2025,2026):
            self.assertTrue(any((ROOT/"data/backtest").glob(f"{year}-*_*.json")))
if __name__=="__main__":unittest.main()
