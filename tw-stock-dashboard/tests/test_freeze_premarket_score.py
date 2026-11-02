"""Immutable premarket snapshot tests: never pretend intraday or close scores are opening scores."""
import json,sys,tempfile,unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import freeze_premarket_score as m
TZ=ZoneInfo("Asia/Taipei")

class FixedPremarketScoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.p1=patch.object(m,"DATA",self.root)
        self.p2=patch.object(m,"OUTPUT",self.root/"market_premarket"/"latest.json")
        self.p1.start();self.p2.start()
    def tearDown(self):
        self.p2.stop();self.p1.stop();self.tmp.cleanup()
    def write(self,name,obj):
        path=self.root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj),encoding="utf-8")
    def previous(self,score=42,day="2026-11-02"):
        self.write("market_risk_close/latest.json",{"quality":"official-twse-close-risk-v1","asOfDate":day,"risk":{"date":day,"score":score}})
    def tx(self,report="2026-11-03",night=44900):
        self.write("futures/latest.json",{"quality":"paired-day-night","asOfDate":"2026-11-02","contract":"202611",
            "day":{"date":"20261102","contract":"202611","close":45000},
            "night":{"date":"20261102","contract":"202611","close":night,"reportQueryDate":report},
            "nightVsDayPct":(night/45000-1)*100})
    def test_premarket_base_without_tx(self):
        self.previous(42)
        snap=m.build(datetime(2026,11,3,8,45,tzinfo=TZ))
        self.assertEqual((snap["targetDate"],snap["score"],snap["baseDate"]),( "2026-11-03",42,"2026-11-02"))
        self.assertEqual(snap["adjustment"],0)
        self.assertIsNone(snap["txPct"])
    def test_matched_official_night_only(self):
        self.previous(42);self.tx(night=44750)
        snap=m.build(datetime(2026,11,3,8,45,tzinfo=TZ))
        self.assertEqual(snap["score"],34)
        self.assertEqual(snap["adjustment"],-8)
    def test_reject_wrong_day_night_and_do_not_guess(self):
        self.previous(42);self.tx(report="2026-11-04",night=44000)
        snap=m.build(datetime(2026,11,3,8,45,tzinfo=TZ))
        self.assertEqual(snap["score"],42)
    def test_frozen_score_immune_to_new_day_close(self):
        self.previous(42)
        t=datetime(2026,11,3,8,35,tzinfo=TZ)
        first=m.build(t)
        self.write("market_premarket/latest.json",first)
        self.previous(12,day="2026-11-03")
        self.assertEqual(m.build(datetime(2026,11,3,8,55,tzinfo=TZ))["score"],42)
    def test_not_created_after_cash_open_or_on_weekend(self):
        self.previous(42)
        self.assertIsNone(m.build(datetime(2026,11,3,9,0,tzinfo=TZ)))
        self.assertIsNone(m.build(datetime(2026,11,7,8,55,tzinfo=TZ)))
        self.assertIsNone(m.build(datetime(2026,11,3,20,0,tzinfo=TZ)))
    def test_stale_or_future_cash_rejected(self):
        self.previous(42,day="2026-10-20")
        with self.assertRaisesRegex(RuntimeError,"NO_RECENT"):
            m.build(datetime(2026,11,3,8,45,tzinfo=TZ))
        self.previous(42,day="2026-11-04")
        with self.assertRaisesRegex(RuntimeError,"NO_RECENT"):
            m.build(datetime(2026,11,3,8,45,tzinfo=TZ))
    def test_last_verified_official_close_wins(self):
        self.previous(12,day="2026-11-02")
        self.write("latest.json",{"dataDate":"2026-10-30","risk":{"date":"2026-10-30","score":49}})
        self.assertEqual(m.build(datetime(2026,11,3,8,45,tzinfo=TZ))["score"],12)

if __name__=="__main__":unittest.main()
