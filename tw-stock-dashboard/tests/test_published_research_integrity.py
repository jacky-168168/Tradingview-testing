"""Fast, reproducible evidence checks for already published backtest artifacts.
Never interpret coverage as proof that a strategy is profitable or causal."""
import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"docs"/"data"
def read(path):return json.loads((ROOT/path).read_text(encoding="utf-8"))
class PublishedResearchIntegrity(unittest.TestCase):
    def test_official_daily_risk_archive_is_date_locked_and_complete(self):
        coverage=read("research/g_regime_3y/coverage.json")
        self.assertTrue(coverage["complete"]);self.assertEqual(coverage["missingDays"],0)
        self.assertEqual(coverage["riskScoredDays"],coverage["tradingDays"])
        self.assertEqual(coverage["officialValidDays"],coverage["tradingDays"])
        days=read("research/g_regime_3y/market_risk_daily.json")
        self.assertEqual(len(days),coverage["tradingDays"])
        keys=[x["date"] for x in days]
        self.assertEqual(len(keys),len(set(keys)));self.assertEqual(keys,sorted(keys))
        for day in days:
            self.assertGreaterEqual(day["score"],0)
            self.assertLessEqual(day["score"],100)
            self.assertGreater(day["index"],0)
            self.assertGreaterEqual(day["breadth"],0)
            self.assertLessEqual(day["breadth"],100)
            self.assertTrue(coverage["period"]["start"]<=day["date"]<=coverage["period"]["end"])
    def test_g_regime_summary_never_claims_night_futures_cover_when_missing(self):
        summary=read("research/g_regime_3y/summary.json")
        coverage=read("research/g_regime_3y/coverage.json")
        self.assertEqual(summary["riskCoverage"],coverage["riskScoredDays"])
        self.assertEqual(summary["signalSessions"],coverage["tradingDays"])
        self.assertEqual(len(summary["models"]),32)
        self.assertEqual(set(x["horizon"] for x in summary["models"]),{1,5,10,20})
        # Current archive has zero independently matched TX after-hours reports.
        # Any positive assertion would misrepresent an unverified futures filter.
        if summary["txNightCoverage"]==0:
            for model in summary["models"]:self.assertEqual(model["txNightDays"],0)
    def test_g_pro_models_have_distinct_expected_keys_and_capped_signal_counts(self):
        summary=read("research/g_pro_3y/summary.json")
        self.assertEqual(summary["riskScoredDays"],728)
        models=summary["models"]
        self.assertEqual(len(models),56)
        keys=[(x["model"],x["threshold"],x["horizon"]) for x in models]
        self.assertEqual(len(keys),len(set(keys)))
        self.assertEqual(set(x["model"] for x in models),{"G","G Pro"})
        for row in models:
            self.assertGreaterEqual(row["qualifiedSignalDays"],row["executedSignalDays"])
            self.assertGreaterEqual(row["executedSignalDays"],0)
            self.assertEqual(row["signalStats"]["n"],row["executedSignalDays"])
            self.assertIn("portfolio",row)
        self.assertLessEqual(summary["gProSignalDays"],summary["rawGSignalDays"])
    def test_walkforward_audit_explicitly_declares_partial_holdout_limitations(self):
        d=read("research/g_compound_walkforward_3y/summary.json")
        self.assertEqual(d["marketDays"],728)
        self.assertEqual(d["officialRiskDays"],728)
        self.assertTrue(d["GUnmodifiedParityVerified"])
        caveats=" ".join(map(str,d.get("limitations",[]))).lower()
        self.assertIn("survivorship",caveats)
        self.assertIn("2026",caveats)
if __name__=="__main__":unittest.main()
