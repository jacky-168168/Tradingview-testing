"""ALFRED vintages must remain distinct from verified primary announcements."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_alfred import RELEASES, parse_alfred_dates
from collect_official_events import merge_events

FIXTURE = """
-------------------------------------------------------------------------
Release: Consumer Price Index
Archival Federal Reserve Economic Data, Federal Reserve Bank of St. Louis
1949-03-24 2026-10-14
Release Dates Notes: this list can include revised release series
Release Dates:
----------
1949-03-24
1977-10-22
2024-02-13
2024-02-13
2026-10-14
2027-01-20
"""


class AlfredDataTests(unittest.TestCase):
    def test_date_section_dedup_future_filter_and_source_provenance(self):
        now = datetime(2026, 11, 9, tzinfo=timezone.utc)
        rows = parse_alfred_dates(FIXTURE, 10, now)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["date"], "1949-03-24")
        self.assertEqual(rows[-1]["date"], "2026-10-14")
        self.assertTrue(all(e["calendarKind"] == "alfred_historical_vintage" for e in rows))
        self.assertTrue(all(e["localTime"] is None for e in rows))
        self.assertTrue(all(e["primaryReleaseVerified"] is False for e in rows))
        self.assertTrue(all(e["sourceUrl"].startswith("https://alfred.stlouisfed.org/") for e in rows))

    def test_alternate_date_set_is_not_counted_as_primary_cpi_release(self):
        now = datetime(2026, 11, 9, tzinfo=timezone.utc)
        secondary = parse_alfred_dates(FIXTURE, 10, now)
        primary = [{
            "id": "bls-cpi-2024-02-13", "category": "CPI", "date": "2024-02-13",
            "subtype": "官方經濟數據公布", "title": "CPI primary",
            "source": "BLS", "sourceUrl": "https://www.bls.gov/news.release/archives/cpi_02132024.htm"
        }]
        merged = merge_events(primary, [], secondary)
        self.assertEqual(len(merged), 5)  # Different categories, no fake overwrite
        self.assertEqual(len([x for x in merged if x["category"] == "CPI"]), 1)
        self.assertEqual(len([x for x in merged if x["category"] == "CPI資料更新"]), 4)

    def test_reject_html_redesign_and_unsupported_release_id(self):
        with self.assertRaises(ValueError):
            parse_alfred_dates("<html>homepage</html>", 10)
        with self.assertRaises(ValueError):
            parse_alfred_dates(FIXTURE, 999999)

    def test_curated_secondary_categories_are_broad_but_finite(self):
        self.assertEqual(len(RELEASES), 8)


if __name__ == "__main__":
    unittest.main()
