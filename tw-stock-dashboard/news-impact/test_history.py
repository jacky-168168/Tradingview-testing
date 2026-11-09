import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from history import archive_events, follow_through, parse_published


class NewsImpactTests(unittest.TestCase):
    def test_requires_timezone(self):
        self.assertIsNone(parse_published("2026-11-09T07:00:00"))
        self.assertIsNotNone(parse_published("2026-11-09T07:00:00+08:00"))

    def test_first_later_session_as_baseline(self):
        prices = [
            (date(2026, 11, 6), 90),
            (date(2026, 11, 9), 100),
            (date(2026, 11, 10), 110),
            (date(2026, 11, 11), 121),
            (date(2026, 11, 12), 133.1),
        ]
        r, base = follow_through("2026-11-09T07:00:00+08:00", prices, "Asia/Taipei")
        self.assertEqual(base, "2026-11-10")
        self.assertAlmostEqual(r["1D"], 10.0)
        self.assertAlmostEqual(r["2D"] if "2D" in r else r["1D"], 10.0)
        self.assertNotIn("20D", r)

    def test_no_future_data(self):
        prices = [(date(2026, 11, 8), 100), (date(2026, 11, 9), 105)]
        r, base = follow_through("2026-11-09T19:00:00+08:00", prices, "Asia/Taipei")
        self.assertFalse(r)
        self.assertIsNone(base)

    def test_archive_deduplicates(self):
        item = {"id": "x", "type": "news", "title": "Headline", "url": "https://example.com",
                "publishedAt": "2026-11-09T00:00:00+08:00"}
        now = datetime(2026, 11, 10, tzinfo=timezone.utc)
        result = archive_events([], [item, item], now)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["realized"], {})


if __name__ == "__main__":
    unittest.main()
