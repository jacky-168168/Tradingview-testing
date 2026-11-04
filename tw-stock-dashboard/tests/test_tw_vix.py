"""VIXTWN reporting: all market and freshness checks use explicit fixture time."""
from __future__ import annotations
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from tw_vix import parse_wantgoo,update,validate_rows,TZ

NOW=datetime(2026,11,4,13,0,tzinfo=TZ)
HTML="""<html><title>臺指選擇權波動率指數 - WantGoo</title>
<div>臺指選擇權波動率指數</div><p>VIXTWN 2026-11-04 12:48
成交量僅含一般交易、盤後定價交易自選股登入免費用</p>
<h1>39.92</h1><strong>3.09</strong><span>8.39%</span>
<script>VIXTWN 2026-01-01 15:22 0.01 0.01 0.01%</script></html>"""


class TwVixRegression(unittest.TestCase):
    def test_real_observed_values(self):
        self.assertEqual(parse_wantgoo(HTML,NOW),{
            "date":"2026-11-04","time":"12:48","value":39.92,"change":3.09,"changePct":8.39})

    def test_explicit_future_rejected(self):
        with self.assertRaisesRegex(ValueError,"未來"):
            parse_wantgoo(HTML,datetime(2026,11,4,12,40,tzinfo=TZ))

    def test_no_price_or_placeholder_rejected(self):
        with self.assertRaisesRegex(ValueError,"報價"):
            parse_wantgoo(HTML.replace("39.92","--"))

    def test_missing_quote_date_rejected(self):
        with self.assertRaisesRegex(ValueError,"日期"):
            parse_wantgoo(HTML.replace("2026-11-04 12:48","今日即時"))

    def test_inconsistent_quote_rejected(self):
        with self.assertRaisesRegex(ValueError,"不一致"):
            parse_wantgoo(HTML.replace("8.39%","20.00%"),NOW)

    def test_old_source_not_reinterpreted_as_today(self):
        old=HTML.replace("2026-11-04 12:48","2026-10-14 12:48")
        with self.assertRaisesRegex(ValueError,"過期"):
            parse_wantgoo(old,NOW)

    def test_latest_day_updates_not_append_intraday_as_historical_days(self):
        original=parse_wantgoo(HTML,NOW)
        old=update({},original,NOW)
        newer={**original,"time":"12:55","value":39.93,"change":3.10,"changePct":8.42}
        refreshed=update(old,newer,NOW)
        self.assertEqual(len(refreshed["rows"]),1)
        self.assertEqual(refreshed["rows"][-1]["value"],39.93)
        self.assertEqual(refreshed["sourceObservationAt"],"2026-11-04T12:55:00+08:00")

    def test_older_time_cannot_overwrite_same_day(self):
        data=update({},parse_wantgoo(HTML,NOW),NOW)
        with self.assertRaisesRegex(ValueError,"時間倒退"):
            update(data,{**data["rows"][0],"time":"10:00"},NOW)

    def test_history_date_regression_rejected(self):
        data=update({},parse_wantgoo(HTML,NOW),NOW)
        with self.assertRaisesRegex(ValueError,"日期倒退"):
            update(data,{**data["rows"][0],"date":"2026-11-03"},NOW)

    def test_only_original_index_source_is_accepted(self):
        data=update({},parse_wantgoo(HTML,NOW),NOW)
        data["version"]="CBOE_VIX_DAILY_V1"
        with self.assertRaisesRegex(ValueError,"其他波動指數"):
            update(data,parse_wantgoo(HTML,NOW),NOW)

    def test_committed_observation_has_provenance_and_valid_change(self):
        record=json.loads((ROOT/"docs/data/research/tw_vix/latest.json").read_text("utf-8"))
        rows=validate_rows(record["rows"])
        self.assertEqual(record["sourceUrl"],"https://www.wantgoo.com/index/vixtwn")
        self.assertEqual(rows[-1]["date"],"2026-11-04")
        self.assertAlmostEqual(rows[-1]["value"],39.92)
        self.assertAlmostEqual(rows[-1]["changePct"],8.39)
        self.assertIn("非期交所正式收盤",record["sourceName"])


if __name__=="__main__":
    unittest.main()
