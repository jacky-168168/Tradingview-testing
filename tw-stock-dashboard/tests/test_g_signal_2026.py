import unittest
import pandas as pd
from backtest_signal_model import VARIANTS,rank_pct,score_row,pass_variant,H

class TestG2026(unittest.TestCase):
    def base(self):
        return {"capitalB":100.0,"close":100.0,"ret20P":80.0,"slopeP":90.0,"atrP":75.0,"range20P":85.0,"turnoverP":85.0,"breakoutPct":-5.0}
    def test_horizons(self):
        self.assertEqual(H,[1,3,5,10,20])
    def test_base_criteria(self):
        self.assertTrue(pass_variant(self.base(),VARIANTS["G_BASE"]))
        self.assertTrue(pass_variant(self.base(),VARIANTS["G_RELAXED"]))
        self.assertTrue(pass_variant(self.base(),VARIANTS["G_STRICT"]))
    def test_capital_price_guards(self):
        for field,bad in (("capitalB",500.0),("capitalB",0.0),("close",9.99)):
            x=self.base();x[field]=bad
            self.assertFalse(pass_variant(x,VARIANTS["G_BASE"]))
    def test_percentile_minimums(self):
        keys={"ret20P":74.99,"slopeP":84.99,"atrP":69.99,"range20P":79.99,"turnoverP":79.99,"breakoutPct":-18.01}
        for field,bad in keys.items():
            x=self.base();x[field]=bad
            self.assertFalse(pass_variant(x,VARIANTS["G_BASE"]),field)
    def test_relaxed_strict(self):
        x=self.base();x["slopeP"]=80
        self.assertTrue(pass_variant(x,VARIANTS["G_RELAXED"]))
        self.assertFalse(pass_variant(x,VARIANTS["G_BASE"]))
    def test_score_weighting_and_proximity(self):
        x=self.base()
        for field in ("ret20P","slopeP","atrP","range20P","turnoverP"):x[field]=100.0
        x["breakoutPct"]=0.0
        self.assertAlmostEqual(score_row(x),100.0)
        x["breakoutPct"]=-18.0
        self.assertAlmostEqual(score_row(x),95.0)
        x["breakoutPct"]=-9.0
        self.assertAlmostEqual(score_row(x),97.5)
    def test_universe_rank_includes_large_caps(self):
        p=rank_pct([10,20,30,40])
        self.assertEqual(p.tolist(),[25.0,50.0,75.0,100.0])
    def test_hard_filters_not_used_before_percentiles(self):
        low=self.base();low["capitalB"]=499.99
        high=self.base();high["capitalB"]=500.0
        self.assertTrue(pass_variant(low,VARIANTS["G_BASE"]))
        self.assertFalse(pass_variant(high,VARIANTS["G_BASE"]))

if __name__=="__main__":unittest.main()
