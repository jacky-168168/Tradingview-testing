import sys
import unittest
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import clean_prices, event_to_session_index, returns_for_events, build_report, MARKETS

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
        result=build_report(self.events,"NASDAQ",self.prices,date(2022,12,31))
        twenty=next(x for x in result["horizons"] if x["horizonSessions"]==20)
        self.assertEqual(twenty["sampleSize"],2)
        self.assertEqual(twenty["status"],"exploratory")
        self.assertIsNone(twenty["pValue"])
        self.assertIsNone(twenty["holdout"])
        self.assertFalse(twenty["significanceClaim"])

    def test_reject_future_prices_and_invalid_quotes(self):
        with self.assertRaises(ValueError):
            build_report(self.events,"NASDAQ",self.prices,date(2019,1,1))
        with self.assertRaises(ValueError):
            clean_prices([(date(2020,1,2),-1.0)])
        with self.assertRaises(ValueError):
            clean_prices([(date(2020,1,2),101.0),(date(2020,1,2),102.0)])

if __name__=="__main__": unittest.main()
