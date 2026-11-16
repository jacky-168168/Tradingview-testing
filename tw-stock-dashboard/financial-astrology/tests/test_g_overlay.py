import json
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from sys import path
path.insert(0,str(Path(__file__).resolve().parents[1]))
from g_overlay_research import compute_g_overlay

class ExistingGTradeArchiveOverlayTests(unittest.TestCase):
    def test_overlay_is_readonly_and_small_event_samples_are_not_made_into_strategy(self):
        with tempfile.TemporaryDirectory() as folder:
            trades=Path(folder)/"trades.json"; executive=Path(folder)/"executive.json"
            trades.write_text(json.dumps({"version":"G_TEST_CLOSED_CASH_LEDGER",
                "auditedModels":{"G_FIXED":{"all":{"trades":[
                  {"buyDate":"2026-02-09","netPct":2.0,"signalDate":"2026-02-06"},
                  {"buyDate":"2026-02-12","netPct":-1.0,"signalDate":"2026-02-11"},
                  {"buyDate":"2026-03-03","netPct":3.0,"signalDate":"2026-03-02"}
                ]}}}}))
            executive.write_text(json.dumps({"selectedModel":{"id":"G_FIXED"}}))
            start=date(2026,2,2)
            daylist=[start+timedelta(days=i) for i in range(110)]
            prices=[(d,100.0) for d in daylist if d.weekday()<5]
            cat={"studyFamilies":{"new_moon":{"events":[{"exactUtc":"2026-02-07T12:00:00Z"}]}}}
            before=trades.read_bytes()
            report=compute_g_overlay(cat,prices,trades,executive,20)
            self.assertEqual(report["status"],"observational_only")
            self.assertTrue(report["modelNotModified"])
            self.assertEqual(report["sourceModel"],"G_FIXED")
            item=report["families"]["new_moon"]
            self.assertEqual(item["status"],"insufficient")
            self.assertIsNone(item["meanGTradeNetPctInside"])
            self.assertEqual(trades.read_bytes(),before)
            self.assertIn("No re-execution",item["sampleWarning"])
    def test_no_model_is_flagged_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            trades=Path(folder)/"trades.json"; executive=Path(folder)/"executive.json"
            trades.write_text(json.dumps({"auditedModels":{}}))
            executive.write_text(json.dumps({"selectedModel":{"id":"NONEXISTENT"}}))
            result=compute_g_overlay({},[(date(2026,2,2),100)],trades,executive)
            self.assertEqual(result["status"],"unavailable")
if __name__=="__main__":unittest.main()
