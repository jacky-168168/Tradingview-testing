import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from official_study import build_study, eligible_session, event_returns, summary_stats, validate_catalog


def event(**kwargs):
    base = {
        "id": "cpi-2024-02-13", "category": "CPI", "subtype": "公布日",
        "date": "2024-02-13", "timezone": "America/New_York", "localTime": "08:30",
        "title": "US CPI", "source": "BLS", "sourceUrl": "https://www.bls.gov",
    }
    return {**base, **kwargs}


def dates(*vals):
    return [(date.fromisoformat(d), float(v)) for d, v in vals]


class OfficialStudyTests(unittest.TestCase):
    def test_us_morning_release_counts_event_session_only_after_prior_close(self):
        e = event()
        bars = dates(("2024-02-12", 100), ("2024-02-13", 102),
                     ("2024-02-14", 101), ("2024-02-15", 99),
                     ("2024-02-16", 105), ("2024-02-20", 110))
        self.assertEqual(eligible_session(e, "美股S&P500", bars), 1)
        got = event_returns(e, "美股S&P500", bars)
        self.assertEqual(got["baselineDate"], "2024-02-12")
        self.assertEqual(got["firstEligibleDate"], "2024-02-13")
        self.assertEqual(got["results"]["1D"], 2)
        self.assertEqual(got["results"]["5D"], 10)
        self.assertNotIn("20D", got["results"])

    def test_us_morning_cpi_is_after_taiwan_close(self):
        e = event()
        bars = dates(("2024-02-13", 90), ("2024-02-14", 95), ("2024-02-15", 96))
        self.assertEqual(eligible_session(e, "台股", bars), 1)
        self.assertEqual(event_returns(e, "台股", bars)["results"]["1D"], 5.5556)

    def test_fomc_2pm_us_can_affect_same_day_close(self):
        e = event(id="fomc", category="FOMC", date="2024-09-18", localTime="14:00")
        bars = dates(("2024-09-17", 100), ("2024-09-18", 110), ("2024-09-19", 105))
        self.assertEqual(eligible_session(e, "NASDAQ", bars), 1)
        self.assertEqual(event_returns(e, "NASDAQ", bars)["results"]["1D"], 10)

    def test_no_look_ahead_partial_future_horizon(self):
        e = event()
        bars = dates(("2024-02-12", 100), ("2024-02-13", 110))
        got = event_returns(e, "NASDAQ", bars)
        self.assertEqual(got["results"], {"1D": 10.0})
        self.assertNotIn("5D", got["results"])

    def test_date_only_opec_uses_future_bar(self):
        e = event(category="OPEC", localTime=None)
        bars = dates(("2024-02-12", 100), ("2024-02-13", 105), ("2024-02-14", 108))
        self.assertEqual(eligible_session(e, "美股S&P500", bars), 2)

    def test_small_sample_not_called_significant(self):
        stats = summary_stats([1, -2, 3], [-1, 1])
        self.assertEqual(stats["status"], "small_sample")
        self.assertEqual(stats["n"], 3)
        self.assertAlmostEqual(stats["positivePct"], 66.7)

    def test_duplicate_and_missing_citations_fail_closed(self):
        e = event()
        with self.assertRaises(ValueError):
            validate_catalog({"schema": 1, "events": [e, e]})
        with self.assertRaises(ValueError):
            validate_catalog({"schema": 1, "events": [event(sourceUrl="http://example.com")]})

    def test_no_market_data_must_not_invent_stats(self):
        c = {"schema": 1, "events": [event()]}
        result = build_study(c, {}, {"NASDAQ": "provider outage"},
                             datetime(2024, 2, 16, tzinfo=timezone.utc))
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["catalogCount"], 1)
        self.assertTrue(all(s["n"] == 0 for s in result["stats"]))


    def test_rejects_release_decades_before_market_history(self):
        e = event(date="1950-01-10", localTime=None)
        bars = dates(("1990-01-02", 100), ("1990-01-03", 110),
                     ("1990-01-04", 120))
        self.assertIsNone(eligible_session(e, "美股S&P500", bars))
        self.assertIsNone(event_returns(e, "美股S&P500", bars))

    def test_fails_closed_for_long_gap_but_keeps_lunar_new_year(self):
        e = event(date="2024-01-20", localTime=None)
        bars = dates(("2024-01-15", 100), ("2024-02-10", 105),
                     ("2024-02-11", 106))
        self.assertIsNone(eligible_session(e, "台股", bars))
        short_bars = dates(("2024-01-15", 100),
                           ("2024-01-31", 110), ("2024-02-01", 111))
        self.assertEqual(eligible_session(e, "台股", short_bars), 1)



if __name__ == "__main__":
    unittest.main()
