"""U.S. election dates must be complete, law-backed and never misread as election results."""
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from us_election_calendar import election_day, election_events, CONGRESS_LAW, PRESIDENT_LAW
from collect_official_events import merge_events
from official_study import build_study

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)

class ElectionCalendarTests(unittest.TestCase):
    def test_known_calendar_dates_and_november_bounds(self):
        expected = {1940:"1940-11-05",1960:"1960-11-08",2000:"2000-11-07",
                    2016:"2016-11-08",2020:"2020-11-03",2022:"2022-11-08",
                    2024:"2024-11-05",2026:"2026-11-03"}
        for year, value in expected.items():
            self.assertEqual(election_day(year).isoformat(), value)
        for year in range(1940,2027,2):
            d=election_day(year)
            self.assertEqual(d.weekday(),1)
            self.assertTrue(2<=d.day<=8)
        with self.assertRaises(ValueError):
            election_day(2025)

    def test_all_election_days_presidential_and_midterms_are_separate(self):
        rows=election_events(NOW)
        self.assertEqual(len(rows),44)
        self.assertEqual(len({e["id"] for e in rows}),44)
        self.assertEqual(len([e for e in rows if e["subtype"]=="總統選舉"]),22)
        self.assertEqual(len([e for e in rows if e["subtype"]=="期中選舉"]),22)
        self.assertTrue(all(e["category"]=="美國選舉" for e in rows))
        self.assertTrue(all(e["timeAccuracy"]=="statutory_voting_day_only" for e in rows))
        self.assertTrue(all(e["resultTimeKnown"] is False for e in rows))
        self.assertTrue(all(e["marketSurpriseKnown"] is False for e in rows))
        self.assertEqual(rows[-1]["date"],"2026-11-03")
        self.assertEqual(rows[0]["date"],"1940-11-05")
        self.assertTrue(all(e["sourceUrl"] in (CONGRESS_LAW,PRESIDENT_LAW) for e in rows))

    def test_not_a_future_event_and_no_double_count_curated_originals(self):
        before=election_events(datetime(2026,1,1,tzinfo=timezone.utc))
        self.assertEqual(len(before),43)
        manually_curated=[
            {"id":"us-election-2024-11-05","category":"美國選舉","date":"2024-11-05","subtype":"總統選舉","title":"2024 general election","sourceUrl":PRESIDENT_LAW},
            {"id":"us-election-2026-11-03","category":"美國選舉","date":"2026-11-03","subtype":"期中選舉","title":"2026 midterms","sourceUrl":CONGRESS_LAW}
        ]
        merged=merge_events(manually_curated,[],election_events(NOW))
        self.assertEqual(len(merged),44)
        self.assertEqual(len([e for e in merged if e["date"]=="2024-11-05"]),1)
        self.assertEqual(len([e for e in merged if e["date"]=="2026-11-03"]),1)

    def test_study_groups_are_explicitly_presidential_and_midterm(self):
        # No historical market feed here. We are testing classification only,
        # never fabricating a share-price result.
        rows=election_events(NOW)
        study=build_study({"schema":1,"events":rows}, {}, {},NOW)
        keys={g["key"] for g in study["groups"]}
        self.assertIn("美國選舉", keys)
        self.assertIn("美國選舉:總統選舉", keys)
        self.assertIn("美國選舉:期中選舉", keys)
        self.assertEqual(study["eventCount"],44)
        self.assertEqual(study["eventsWithPriceData"],0)
        self.assertEqual(study["status"],"unavailable")

if __name__=="__main__":
    unittest.main()
