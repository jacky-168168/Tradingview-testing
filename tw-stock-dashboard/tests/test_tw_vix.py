"""Offline regression tests for source-verified TAIFEX Taiwan VIX daily closes."""
import json
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tw_vix import parse_month, parse_portal, reconcile_portal_to_months, daily_rows, month_keys, validate, TZ, VERSION, SOURCE

NOW = datetime(2026, 11, 4, 14, 10, tzinfo=TZ)
NOV = ("""交易日期\t時間\t臺指選擇權波動率指數\t最後一分鐘平均
--------\t-------------------\t--------------------\t-------------------
20261102\t13450000\t\t\t31.30\t\t31.28
20261103\t13450000\t\t\t36.83\t\t36.83
""").encode("big5")
OCT = ("""交易日期\t時間\t臺指選擇權波動率指數\t最後一分鐘平均
20261030\t13450000\t\t\t35.40\t\t35.38
""").encode("big5")


class TaifexDailyVixTest(unittest.TestCase):
    def test_recent_months_use_four_real_official_files_only(self):
        keys=month_keys(date(2026,11,4))
        self.assertEqual(keys,["202611","202610","202609","202608"])
        self.assertEqual(len(set(keys)),len(keys))

    def test_real_2026_11_file_values(self):
        rows=parse_month(NOV,"202611",NOW)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["value"],31.30)
        self.assertEqual(rows[1]["value"],36.83)
        self.assertEqual(rows[1]["closeMinuteAverage"],36.83)

    def test_different_month_rejected(self):
        with self.assertRaisesRegex(ValueError,"日期不符"):
            parse_month(NOV,"202610",NOW)

    def test_future_session_rejected(self):
        with self.assertRaisesRegex(ValueError,"未來"):
            parse_month(NOV, "202611",datetime(2026,11,2,14,0,tzinfo=TZ))

    def test_unexpected_time_rejected(self):
        with self.assertRaisesRegex(ValueError,"收盤時間"):
            parse_month(NOV.replace(b"13450000",b"10300000"),"202611",NOW)

    def test_incomplete_row_rejected(self):
        with self.assertRaisesRegex(ValueError,"格式異常"):
            parse_month(NOV.replace(b"36.83\t\t36.83",b"36.83"),"202611",NOW)

    def test_missing_month_observations_rejected(self):
        with self.assertRaisesRegex(ValueError,"未取得"):
            parse_month(b"----\n", "202611", NOW)

    def test_duplicate_date_rejected(self):
        row=b"20261103\t13450000\t\t\t36.83\t\t36.83\n"
        with self.assertRaisesRegex(ValueError,"重複"):
            parse_month(NOV+row,"202611",NOW)

    def test_daily_change_calculated_from_adjacent_official_closes(self):
        rows=daily_rows([parse_month(OCT,"202610",NOW),parse_month(NOV,"202611",NOW)])
        self.assertEqual([r["date"] for r in rows],["2026-10-30","2026-11-02","2026-11-03"])
        self.assertIsNone(rows[0]["change"])
        self.assertEqual(rows[-1]["change"],5.53)
        self.assertEqual(rows[-1]["changePct"],17.67)

    def test_not_duplicate_daily_records(self):
        rows=daily_rows([parse_month(NOV,"202611",NOW),parse_month(NOV,"202611",NOW)])
        self.assertEqual(len(rows),2)

    def test_360_session_history_is_kept_without_260_truncation(self):
        from datetime import timedelta
        records=[]
        start=date(2025,2,1)
        for i in range(420):
            day=(start+timedelta(days=i)).isoformat()
            records.append({"date":day,"time":"13:45","value":20+i*.01,
                            "closeMinuteAverage":20+i*.01})
        rows=daily_rows([records])
        self.assertEqual(len(rows),400)
        self.assertIsNone(rows[0]["change"])
        self.assertEqual(rows[-1]["date"],records[-1]["date"])
        self.assertEqual(rows[-1]["change"],.01)

    def test_portal_3year_series_crosschecked_by_official_monthly_file(self):
        days=[]
        current=date(2025,3,3)
        while len(days)<420:
            if current.weekday()<5:
                days.append(current)
            current+=timedelta(days=1)
        payload={"d":json.dumps({"TrendData":[{"Time":day.strftime("%Y%m%d"),"Price":round(18+i/100,2)}
                                 for i,day in enumerate(days)]})}
        portal=parse_portal(json.dumps(payload).encode("utf-8"),NOW)
        self.assertEqual(len(portal),420)
        monthly=[{**r,"closeMinuteAverage":r["value"]} for r in portal[-45:]]
        verified=reconcile_portal_to_months(portal,[monthly])
        self.assertEqual(len(verified),420)
        self.assertIsNone(verified[0]["closeMinuteAverage"])
        self.assertEqual(verified[-1]["closeMinuteAverage"],verified[-1]["value"])
        self.assertEqual(len(daily_rows([verified])),400)

    def test_one_portal_disagreement_is_corrected_to_monthly_close_with_provenance(self):
        days=[]
        current=date(2025,3,3)
        while len(days)<400:
            if current.weekday()<5:days.append(current)
            current+=timedelta(days=1)
        payload={"d":json.dumps({"TrendData":[{"Time":day.strftime("%Y%m%d"),"Price":25.01}
                                 for day in days]})}
        portal=parse_portal(json.dumps(payload).encode("utf-8"),NOW)
        monthly=[{**r,"closeMinuteAverage":25.01} for r in portal[-45:]]
        monthly[0]["value"]=29.0
        corrected=reconcile_portal_to_months(portal,[monthly])
        row=next(r for r in corrected if r["date"]==monthly[0]["date"])
        self.assertEqual(row["value"],29.0)
        self.assertEqual(row["indexPortalValue"],25.01)
        self.assertEqual(row["reconciliation"],"official-monthly-close-overrides-index-portal")

        for index in (1,2):
            monthly[index]["value"]=29.0
        with self.assertRaisesRegex(ValueError,"超過核對容許數"):
            reconcile_portal_to_months(portal,[monthly])

    def test_committed_daily_official_seed(self):
        d=json.loads((ROOT/"docs/data/research/tw_vix/latest.json").read_text("utf-8"))
        self.assertEqual(d["version"],VERSION)
        self.assertEqual(d["sourceUrl"],SOURCE)
        self.assertEqual(d["quality"],"official-taifex-daily-close")
        self.assertGreaterEqual(d["asOfDate"],"2026-11-03")
        self.assertGreaterEqual(len(validate(d)),62)
        fixed=next((r for r in d["rows"] if r["date"]=="2026-11-03"),None)
        if fixed:
            self.assertEqual(fixed["value"],36.83)
            self.assertEqual(fixed["changePct"],17.67)

    def test_cannot_forge_daily_pct(self):
        d=json.loads((ROOT/"docs/data/research/tw_vix/latest.json").read_text("utf-8"))
        d["rows"][-1]["changePct"]=88
        with self.assertRaisesRegex(ValueError,"漲跌"):
            validate(d)


if __name__ == "__main__":
    unittest.main()
