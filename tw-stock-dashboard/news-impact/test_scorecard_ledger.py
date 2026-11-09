import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scorecard import build, merge_immutable_observations, read_ledger, write_ledger

def observation(return_pct=2.0, outcome=1):
    return {
        "id":"old-record", "group":"old-news-story",
        "asset":"美股S&P500","horizon":"1D",
        "publishedAt":"2026-11-09T08:00:00+08:00",
        "frozenAt":"2026-11-09T00:15:00Z",
        "realizedPct":return_pct,"outcome":outcome,
        "ruleIds":["rate-dove"]
    }

class ImmutableScorecardLedgerTests(unittest.TestCase):
    def test_first_outcome_is_immutable_even_if_later_yahoo_price_revised(self):
        old=observation()
        new=observation(return_pct=-9.9,outcome=-1)
        rows=merge_immutable_observations([old],[new])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["outcome"],1)
        self.assertEqual(rows[0]["realizedPct"],2.0)

    def test_old_matured_result_survives_rolling_archive_truncation(self):
        predictions={"schema":1,"records":[],"classifierVersionCurrent":"v1.3"}
        archived={"schema":1,"events":[]}
        result=build(predictions,archived,ledger=[observation()])
        self.assertEqual(result["audit"]["maturedObservationCount"],1)
        self.assertEqual(result["audit"]["retainedOlderObservationCount"],1)
        self.assertEqual(result["byAsset"][0]["wins"],1)
        self.assertIsNone(result["byAsset"][0]["winRatePct"])

    def test_idempotent_year_partition_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            row=observation()
            write_ledger([row,row],folder)
            rows=read_ledger(folder)
            self.assertEqual(len(rows),1)
            self.assertTrue((folder/"2026.json").exists())
            write_ledger(rows,folder)
            self.assertEqual(read_ledger(folder),rows)

    def test_reject_invalid_or_incomplete_records(self):
        row=observation()
        invalid=[{**row,"outcome":6},{**row,"realizedPct":float("nan")},
                 {**row,"asset":"imaginary commodity"},{**row,"horizon":"300D"}]
        self.assertEqual(merge_immutable_observations(invalid,[]),[])

if __name__ == "__main__":
    unittest.main()
