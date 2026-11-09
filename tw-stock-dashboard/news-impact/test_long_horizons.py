"""Long-horizon historical study must not leak future sessions into results."""
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from history import HORIZONS
from official_study import STUDY_HORIZONS, build_study, event_returns, rolling_controls

def sessions(n):
    """Generated weekday closes for testing bar-based horizons, not calendar offsets."""
    rows=[]
    day=date(2024, 1, 5)  # prior close is Friday, first event session Monday
    while len(rows) < n:
        if day.weekday() < 5:
            rows.append((day, float(100 + len(rows))))
        day += timedelta(days=1)
    return rows

def event():
    return {
        "id": "cpi-2024-01-08",
        "category": "CPI",
        "subtype": "公布",
        "date": "2024-01-08",
        "timezone": "America/New_York",
        "localTime": "08:30",
        "title": "Fixture CPI release",
        "source": "BLS",
        "sourceUrl": "https://www.bls.gov/news.release/",
    }

class LongHorizonTests(unittest.TestCase):
    def test_long_horizons_are_strictly_event_study_only(self):
        self.assertEqual(HORIZONS, (1, 5, 20))
        self.assertEqual(STUDY_HORIZONS, (1, 5, 20, 180, 360))

    def test_180_and_360_trade_sessions_not_calendar_days(self):
        bars=sessions(361)
        out=event_returns(event(), "美股S&P500", bars)
        self.assertEqual(out["firstEligibleDate"], "2024-01-08")
        self.assertEqual(out["baselineDate"], "2024-01-05")
        self.assertEqual(out["results"]["1D"], 1.0)
        self.assertEqual(out["results"]["5D"], 5.0)
        self.assertEqual(out["results"]["20D"], 20.0)
        self.assertEqual(out["results"]["180D"], 180.0)
        self.assertEqual(out["results"]["360D"], 360.0)
        self.assertGreater((bars[360][0]-bars[1][0]).days, 360)

    def test_unfinished_360_day_window_is_never_filled(self):
        bars=sessions(190)
        out=event_returns(event(), "美股S&P500", bars)
        self.assertIn("180D", out["results"])
        self.assertNotIn("360D", out["results"])

    def test_incomplete_180_and_360_day_windows_zero_count(self):
        bars=sessions(25)
        out=event_returns(event(), "美股S&P500", bars)
        self.assertEqual(list(out["results"]), ["1D", "5D", "20D"])
        catalog={"schema":1,"events":[event()]}
        study=build_study(catalog, {"美股S&P500":bars}, {},
                          datetime(2026, 11, 9, tzinfo=timezone.utc))
        by_h={s["horizon"]:s for s in study["stats"]
              if s["group"]=="CPI" and s["asset"]=="美股S&P500"}
        self.assertEqual(list(by_h), ["1D","5D","20D","180D","360D"])
        self.assertEqual(by_h["20D"]["n"],1)
        self.assertEqual(by_h["180D"]["n"],0)
        self.assertEqual(by_h["360D"]["n"],0)
        self.assertEqual(study["horizonsTradingDays"],[1,5,20,180,360])

    def test_unconditional_benchmark_uses_same_horizon_and_no_future(self):
        bars=sessions(361)
        self.assertEqual(len(rolling_controls(bars, 180, bars[0][0])),181)
        self.assertEqual(len(rolling_controls(bars, 360, bars[0][0])),1)
        self.assertEqual(len(rolling_controls(bars, 362, bars[0][0])),0)

if __name__=="__main__":
    unittest.main()
