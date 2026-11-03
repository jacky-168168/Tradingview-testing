import re
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_retail_survival_freshness import validate

TZ = ZoneInfo("Asia/Taipei")


class RetailFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 3, 19, 40, tzinfo=TZ)
        self.market = {"dataDate": "2026-11-03"}

    def record(self, day="2026-11-03", overall=170.6):
        return {"asOf": day, "rows": [{"date": day, "overall": overall}]}

    def test_same_day_data_passes(self):
        self.assertEqual(validate(self.record(), self.market, self.now), "2026-11-03")

    def test_yesterday_rejected_after_verified_market_close(self):
        with self.assertRaisesRegex(RuntimeError, "stale after close"):
            validate(self.record("2026-11-02"), self.market, self.now)

    def test_missing_overall_not_misreported_as_updated(self):
        with self.assertRaisesRegex(RuntimeError, "all-market margin ratio missing"):
            validate(self.record(overall=None), self.market, self.now)

    def test_before_cutoff_does_not_assume_source_is_ready(self):
        early = datetime(2026, 11, 3, 17, 35, tzinfo=TZ)
        self.assertEqual(validate(self.record("2026-11-02"), self.market, early), "2026-11-02")

    def test_holiday_or_no_verified_trading_date_does_not_false_alarm(self):
        later = datetime(2026, 11, 7, 21, 0, tzinfo=TZ)
        self.assertEqual(validate(self.record("2026-11-06"), {"dataDate": "2026-11-06"}, later), "2026-11-06")

    def test_future_or_inconsistent_date_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "future data date"):
            validate(self.record("2026-11-04"), self.market, self.now)
        with self.assertRaisesRegex(RuntimeError, "disagrees"):
            validate({"asOf": "2026-11-03", "rows": [{"date": "2026-11-02"}]}, self.market, self.now)

    def test_workflow_has_early_and_late_independent_retries(self):
        yml = (ROOT.parent / ".github/workflows/retail-survival-margin.yml").read_text("utf-8")
        slots = set()
        for cron in re.findall(r"- cron: ['\"]([^'\"]+)['\"]", yml):
            minute, hour, _, _, weekday = cron.split()
            if weekday != "1-5":
                continue
            for h in hour.split(","):
                for m in minute.split(","):
                    slots.add(f"{(int(h) + 8) % 24:02d}:{int(m):02d}")
        self.assertTrue({"17:35", "19:35", "21:35", "22:20", "23:20"}.issubset(slots), slots)
        self.assertIn("check_retail_survival_freshness.py", yml)


if __name__ == "__main__":
    unittest.main()
