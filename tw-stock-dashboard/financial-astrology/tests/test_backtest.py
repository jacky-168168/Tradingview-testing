import sys
import unittest
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import clean_prices, event_to_session_index, returns_for_events, build_report, MARKETS
from evidence import evidence_for_horizon
from backtest import download_fred
from unittest.mock import patch
import io

class FinancialAstrologyBacktestTest(unittest.TestCase):
    """Synthetic price fixtures ONLY inside tests. Never published as actual performance."""

    def setUp(self):
        start=date(2020,1,1)
        dates=[start+timedelta(days=i) for i in range(900)]
        self.prices=[(d,100+(i*0.01)) for i,d in enumerate(x for x in dates if x.weekday()<5)]
        self.events=[{"exactUtc":"2020-01-03T18:00:00.000Z"},
                     {"exactUtc":"2020-07-04T14:00:00.000Z"}]

    def test_first_session_strictly_after_event_day_and_correct_horizon(self):
        days=[x[0] for x in self.prices]
        idx=event_to_session_index(self.events[0],days,"America/New_York")
        self.assertGreater(days[idx],date(2020,1,3))
        samples,censored=returns_for_events(self.events,self.prices,"America/New_York",20)
        self.assertEqual(len(samples),2)
        self.assertEqual(samples[0]["entryDate"],"2020-01-06")
        self.assertGreater(samples[0]["return"],0)
        self.assertEqual(samples[0]["exitDate"],self.prices[idx+20][0].isoformat())

    def test_reproducible_exploratory_results_with_explicit_n(self):
        result=build_report(self.events,"NASDAQ",self.prices,self.prices[-1][0])
        twenty=next(x for x in result["horizons"] if x["horizonSessions"]==20)
        self.assertEqual(twenty["sampleSize"],2)
        self.assertEqual(twenty["status"],"exploratory")
        self.assertIsNone(twenty["pValue"])
        self.assertIsNone(twenty["holdout"])
        self.assertFalse(twenty["significanceClaim"])
        self.assertEqual(twenty["evidence"]["level"],"very_low")
        self.assertEqual(twenty["evidence"]["direction"],"無法判定")
        self.assertEqual(result["priceSampleCount"],len(self.prices))

    def test_reject_future_prices_and_invalid_quotes(self):
        with self.assertRaises(ValueError):
            build_report(self.events,"NASDAQ",self.prices,date(2019,1,1))
        with self.assertRaises(ValueError):
            clean_prices([(date(2020,1,2),-1.0)])
        with self.assertRaises(ValueError):
            clean_prices([(date(2020,1,2),101.0),(date(2020,1,2),102.0)])

    def test_statistical_evidence_requires_sample_size_and_oos(self):
        base={"sampleSize":7,"excessReturn":0.04,"fdrQValue":0.001,
              "excessConfidence95":[0.01,0.05],"holdout":{"holdoutCount":14,"holdoutMean":0.04}}
        self.assertEqual(evidence_for_horizon(base)["level"],"very_low")
        base["sampleSize"]=16
        self.assertEqual(evidence_for_horizon(base)["level"],"low")
        base["sampleSize"]=33
        self.assertEqual(evidence_for_horizon(base)["level"],"preliminary")
        self.assertEqual(evidence_for_horizon(base)["direction"],"無法判定")
        base["fdrQValue"]=0.9
        self.assertEqual(evidence_for_horizon(base)["level"],"unconfirmed")
        self.assertEqual(evidence_for_horizon({"sampleSize":0})["level"],"unavailable")

    def test_outdated_close_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"stale"):
            build_report(self.events,"NASDAQ",self.prices,date(2026,11,16))

    def test_fred_csv_parsing_with_real_source_schema_without_network(self):
        raw=b"DATE,NASDAQCOM\n2026-11-12,26000.5\n2026-11-13,26030.0\n2026-11-16,.\n"
        with patch('backtest.urlopen',return_value=io.BytesIO(raw)):
            rows=download_fred("NASDAQCOM",date(2026,11,16))
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[-1][0],date(2026,11,13))
        self.assertEqual(rows[-1][1],26030.0)
        with self.assertRaises(ValueError):
            download_fred("UNAPPROVED",date(2026,11,16))
if __name__=="__main__": unittest.main()
