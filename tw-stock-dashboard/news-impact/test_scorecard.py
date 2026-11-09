import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scorecard import before_baseline, build, stats, wilson_bounds

def record(frozen="2026-11-09T03:00:00Z"):
    return {"id":"a","group":"g","publishedAt":"2026-11-09T08:00:00+08:00","frozenAt":frozen,
            "signals":[{"asset":"美股S&P500","direction":1,"ruleIds":["oil-cut"]}]}
def archive(ret):
    return {"schema":1,"events":[{"id":"a","baseline":{"美股S&P500":"2026-11-10"},
             "realized":{"美股S&P500":ret}}]}
class FrozenScorecardTests(unittest.TestCase):
    def test_wilson_interval(self):
        self.assertIsNone(wilson_bounds(0,0))
        low,high=wilson_bounds(24,6)
        self.assertTrue(low<80<high)
    def test_timestamp_must_precede_baseline(self):
        self.assertTrue(before_baseline(record(),"美股S&P500","2026-11-10"))
        self.assertFalse(before_baseline(record("2026-11-10T02:00:00-05:00"),"美股S&P500","2026-11-10"))
    def test_not_matured_not_counted(self):
        d=build({"schema":1,"records":[record()]},{"schema":1,"events":[]})
        self.assertEqual(d["audit"]["maturedObservationCount"],0)
        self.assertEqual(d["audit"]["pendingHorizonCount"],3)
        self.assertIsNone(d["byAsset"][0]["winRatePct"])
    def test_only_completed_horizons_count(self):
        d=build({"schema":1,"records":[record()]},archive({"1D":2}))
        self.assertEqual(d["audit"]["maturedObservationCount"],1)
        self.assertEqual(d["audit"]["pendingHorizonCount"],2)
        self.assertEqual(d["byAsset"][0]["wins"],1)
    def test_late_predictions_excluded(self):
        d=build({"schema":1,"records":[record("2026-11-11T00:00:00Z")]},archive({"1D":3,"5D":-1}))
        self.assertEqual(d["audit"]["maturedObservationCount"],0)
        self.assertEqual(d["audit"]["excludedLateHorizonCount"],3)
    def test_dedup_and_minimum_independent_dates(self):
        rows=[{"group":"same","asset":"美股S&P500","horizon":"1D","publishedAt":"2026-11-09",
               "outcome":1,"realizedPct":2} for _ in range(3)]
        self.assertEqual(stats(rows)["n"],1)
        rows=[{"group":str(i),"asset":"美股S&P500","horizon":"1D",
               "publishedAt":"2026-11-09","outcome":1 if i<24 else -1,"realizedPct":2}
              for i in range(30)]
        self.assertIsNone(stats(rows)["winRatePct"])
        from datetime import date,timedelta
        for i,r in enumerate(rows):
            r["publishedAt"]=str(date(2026,9,1)+timedelta(days=i))
        self.assertEqual(stats(rows)["winRatePct"],80)
if __name__=="__main__":
    unittest.main()
