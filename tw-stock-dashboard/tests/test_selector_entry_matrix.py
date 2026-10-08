import unittest
from backtest_selector_entry_matrix import source_signals,MODELS,HORIZONS,MODES,risk_stats
class SelectorMatrix(unittest.TestCase):
    def test_all_sources_recover_without_reranking(self):
        models,meta=source_signals()
        self.assertEqual(set(MODELS),set(models))
        self.assertEqual(len(models["G_DOUBLE_PERSIST"]),490)
        self.assertEqual(len(models["H5_FRESH_BREAK"]),319)
        for name,rows in models.items():
            self.assertGreater(len(rows),0,name)
            self.assertTrue(all(x["code"] and 1<=int(x["rank"])<=3 for x in rows),name)
            self.assertTrue(all(x["signalDate"].startswith("2026") for x in rows),name)
    def test_parameter_grid_fixed(self):
        self.assertEqual(HORIZONS,(5,10,20))
        self.assertEqual(MODES,("ladder","ma"))
    def test_capital_denominator_uses_unfilled_zero(self):
        rows=[{"status":"filled","mode":"ladder","netOnReservedPct":2,"netOnDeployedPct":4,"tp":True,"date":"2026-02-02","tranches":3},
              {"status":"unfilled","mode":"ladder"}]
        x=risk_stats(rows)
        self.assertEqual(x["filledNetOnReservedMedianPct"],2)
        self.assertEqual(x["perEligibleSignalAvgNetOnReservedPct"],1)
        self.assertEqual(x["fillPct"],50)
if __name__=="__main__":unittest.main()
