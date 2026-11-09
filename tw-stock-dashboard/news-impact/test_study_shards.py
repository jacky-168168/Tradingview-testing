"""Long-history output must remain cheap to load on mobile and noncausal."""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from official_study import generate


class StudyOutputTests(unittest.TestCase):
    def test_summary_is_lightweight_and_shards_only_selected_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "events.json"
            destination = root / "official_study.json"
            catalog.write_text(json.dumps({
                "schema": 1,
                "count": 1, "status": "ok",
                "countsByCategory": {"CPI資料更新": 1},
                "events": [{
                    "id": "alfred-10-2024-02-13",
                    "category": "CPI資料更新",
                    "subtype": "歷史資料發布／修訂日期（未辨認首次公告）",
                    "date": "2024-02-13",
                    "timezone": "America/New_York",
                    "localTime": None,
                    "title": "ALFRED CPI date",
                    "source": "ALFRED",
                    "sourceUrl": "https://alfred.stlouisfed.org/release/downloaddates?ff=txt&rid=10",
                    "primaryReleaseVerified": False,
                    "calendarKind": "alfred_historical_vintage"
                }]
            }), encoding="utf8")
            bars = [(date(2024, 2, 13), 100), (date(2024, 2, 14), 101),
                    (date(2024, 2, 15), 102), (date(2024, 2, 16), 103)]
            with patch("official_study.fetch_prices", return_value=({"美股S&P500": bars}, {})):
                generate(catalog, destination)
            overview = json.loads(destination.read_text(encoding="utf8"))
            self.assertNotIn("events", overview)
            self.assertEqual(overview["eventCount"], 1)
            self.assertEqual(overview["eventsWithPriceData"], 1)
            self.assertEqual(overview["detailFileCount"], 9)
            self.assertEqual(overview["minSample"], 20)
            shard_uri = overview["detailFiles"]["CPI資料更新"]["美股S&P500"]
            self.assertTrue(shard_uri.startswith("./data/news_impact/official_details/"))
            shard = json.loads((destination.parent / "official_details" /
                               Path(shard_uri).name).read_text(encoding="utf8"))
            self.assertEqual(shard["category"], "CPI資料更新")
            self.assertEqual(shard["eventCount"], 1)
            self.assertEqual(len(shard["events"]), 1)
            self.assertIn("美股S&P500", shard["events"][0]["outcomes"])
            self.assertFalse(shard["events"][0]["primaryReleaseVerified"])
            self.assertNotIn("NASDAQ", shard["events"][0]["outcomes"])
            self.assertLess(destination.stat().st_size, 20000)


if __name__ == "__main__":
    unittest.main()
