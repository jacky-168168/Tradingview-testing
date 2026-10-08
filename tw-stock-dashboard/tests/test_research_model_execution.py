import unittest
from research_model_execution import INCLUDE, signal_sources, summarize_slices
class TestSelectorComparison(unittest.TestCase):
    def test_published_models_exist_with_historical_top3(self):
        a=signal_sources()
        for model in INCLUDE:
            if model=="H5_FRESH_BREAK":continue
            self.assertIn(model,a)
            self.assertGreater(len(a[model]),0)
            self.assertTrue(all(x["rank"] in(1,2,3) for x in a[model]))
            self.assertTrue(all(x["signalDate"].startswith("2026-") for x in a[model]))
    def test_period_splitting(self):
        rows=[{"date":"2026-02-02","code":"1","status":"filled","tp":True,"netOnReservedPct":2},
              {"date":"2026-06-30","code":"2","status":"filled","tp":False,"netOnReservedPct":-4},
              {"date":"2026-08-10","code":"3","status":"unfilled"}]
        x=summarize_slices(rows)
        self.assertEqual(x["early"]["tpPct"],100)
        self.assertEqual(x["middle"]["avgNetReservedPct"],-4)
        self.assertIsNone(x["late"]["tpPct"])
if __name__=="__main__":unittest.main()
