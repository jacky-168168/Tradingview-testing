"""N annualized CAGR/Sharpe, zero-drift 0050, and causal 2025 selection."""
from __future__ import annotations
import unittest
from unittest.mock import patch
import numpy as np,pandas as pd
from research_n_canslim_recursive import perf_stats,benchmark_0050,monthly_n_learn,FEATURE_NAMES
from research_g_compound_walkforward import PLANS
class NRecursiveTests(unittest.TestCase):
    def test_cagr_sharpe_daily_NAV(self):
        ds=[d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-01-02",periods=260)]
        nav=[];asset=500000
        for i in range(260):
            asset*=1.0014 if i%2 else 1.0004
            nav.append(asset)
        x=perf_stats(ds,nav)
        self.assertGreater(x["annualizedCAGRpct"],0)
        self.assertGreater(x["annualizedSharpeRf0"],0)
        self.assertAlmostEqual(x["maxDrawdownPct"],0,places=5)
    def test_drawdown_and_negative_sharpe(self):
        ds=[d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-01-02",periods=45)]
        nav=[500000*(1-i*.003) for i in range(45)]
        x=perf_stats(ds,nav)
        self.assertLess(x["maxDrawdownPct"],-10)
        self.assertLess(x["annualizedSharpeRf0"],0)
    def test_0050_never_uses_future_close_on_start(self):
        ds=["2025-01-02","2025-01-03","2025-01-06"]
        q=pd.DataFrame({"date":ds,"open":[100,100,100],"close":[100,105,105],
            "adjclose":[100,105,105]})
        nav,proof=benchmark_0050(ds,q)
        self.assertEqual(proof["firstBuyDate"],"2025-01-02")
        self.assertLess(nav[0],500000)
        self.assertGreater(nav[-1],nav[0])
    def test_monthly_trainer_never_reads_unfinished_outcome(self):
        first="2025-01-02";second="2025-02-03"
        ds=[first,second];features=[1.]*len(FEATURE_NAMES)
        pool={first:[{"sym":"2330.TW","code":"2330","name":"X","close":100,
              "sources":["N"],"metrics":{"epsAvailableFrom":"2024-05-22",
                "revAvailableFrom":"2024-12-16","epsYtdGrowthPct":50,
                "revenueYoYPct":40,"rsPercentile":90,"near52WeekHighPct":95},
              "features":features}],
          second:[{"sym":"2330.TW","code":"2330","name":"X","close":100,
              "sources":["N"],"metrics":{"epsAvailableFrom":"2024-11-22",
                "revAvailableFrom":"2025-01-16","epsYtdGrowthPct":50,
                "revenueYoYPct":40,"rsPercentile":90,"near52WeekHighPct":95},
              "features":features}]}
        old=[{"date":"2024-11-01","maturity":"2024-12-30","features":features,
              "pnl":.04 if i%2 else -.05} for i in range(80)]
        fresh={"date":"2025-01-08","maturity":"2025-01-30",
              "features":features,"pnl":.05}
        unknown={"date":"2025-01-08","maturity":"2025-02-14",
              "features":features,"pnl":.99}
        visited=[]
        def stub(kind,X,y):
            visited.append(len(y))
            return lambda x:np.ones(len(x))*.5
        with patch("research_n_canslim_recursive.trainer",side_effect=stub):
            picks,audit=monthly_n_learn(ds,pool,{"FAST":old+[fresh,unknown]},"Ridge","FAST","POSITIVE")
        self.assertEqual(visited,[80,81])
        self.assertEqual(audit[0]["latestUsedLabelExit"],"2024-12-30")
        self.assertEqual(audit[1]["latestUsedLabelExit"],"2025-01-30")
        self.assertEqual(picks[first][0]["code"],"2330")
        self.assertEqual(picks[second][0]["code"],"2330")
    def test_month_without_training_returns_no_buy(self):
        ds=["2025-01-02"]
        p,a=monthly_n_learn(ds,{},{"FAST":[]},"Ridge","FAST","POSITIVE")
        self.assertEqual(p[ds[0]],[])
        self.assertFalse(a[0]["trained"])
if __name__=="__main__":unittest.main()
