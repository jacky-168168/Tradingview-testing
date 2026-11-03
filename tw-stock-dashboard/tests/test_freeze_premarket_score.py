"""Prevent missing cron ticks, stale close reuse or night-mode overwrites."""
import json,sys,tempfile,unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import freeze_premarket_score as m
TZ=ZoneInfo("Asia/Taipei")

class FixedPremarketTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.p1=patch.object(m,"DATA",self.root)
        self.p2=patch.object(m,"OUTPUT",self.root/"market_premarket"/"latest.json")
        self.p1.start();self.p2.start()
    def tearDown(self):
        self.p2.stop();self.p1.stop();self.temp.cleanup()
    def put(self,name,value):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value),encoding="utf-8")
    def cash(self,score=12,day="2026-11-02"):
        self.put("market_risk_close/latest.json",{
            "quality":"official-twse-close-risk-v1","asOfDate":day,
            "risk":{"date":day,"score":score}})
    def tx(self,night=44750,target="2026-11-03"):
        self.put("futures/latest.json",{
            "quality":"paired-day-night","asOfDate":"2026-11-02","contract":"202611",
            "day":{"date":"20261102","contract":"202611","close":45000},
            "night":{"date":"20261102","contract":"202611","close":night,"reportQueryDate":target},
            "nightVsDayPct":(night/45000-1)*100})
    def test_after_close_prebuild_without_night(self):
        self.cash()
        result=m.build(datetime(2026,11,2,20,15,tzinfo=TZ))
        self.assertEqual((result["targetDate"],result["score"],result["baseDate"]),
                         ("2026-11-03",12,"2026-11-02"))
        self.assertEqual(result["calculationMode"],"after-close-prebuild")
        self.assertIsNone(result["txPct"])
    def test_validated_tx_adjustment_is_optional(self):
        self.cash(42);self.tx()
        result=m.build(datetime(2026,11,3,8,45,tzinfo=TZ))
        self.assertEqual((result["score"],result["adjustment"]),(34,-8))
    def test_reject_wrong_date_tx(self):
        self.cash(42);self.tx(target="2026-11-04")
        self.assertEqual(m.build(datetime(2026,11,3,8,45,tzinfo=TZ))["score"],42)
    def test_github_cron_missing_recovers_at_1030(self):
        self.cash()
        x=m.build(datetime(2026,11,3,10,30,tzinfo=TZ))
        self.assertEqual((x["score"],x["calculationMode"]),(12,"late-recovery"))
        self.assertEqual(x["targetDate"],"2026-11-03")
    def test_archive_remains_fixed_when_new_close_arrives(self):
        self.cash()
        prev=m.build(datetime(2026,11,2,21,0,tzinfo=TZ))
        self.put("market_premarket/2026-11-03.json",prev)
        self.put("market_premarket/latest.json",prev)
        self.cash(75,day="2026-11-03")
        self.assertEqual(m.build(datetime(2026,11,3,8,55,tzinfo=TZ))["score"],12)
        nxt=m.build(datetime(2026,11,3,19,0,tzinfo=TZ))
        self.assertEqual(nxt["targetDate"],"2026-11-04")
        self.assertEqual(nxt["score"],75)
        self.assertEqual(json.loads((self.root/"market_premarket/2026-11-03.json").read_text())["score"],12)
    def test_no_prebuild_when_today_official_missing(self):
        self.cash()
        with self.assertRaisesRegex(RuntimeError,"OFFICIAL_TODAY_NOT_READY"):
            m.build(datetime(2026,11,3,19,0,tzinfo=TZ))
    def test_previous_friday_used_for_monday(self):
        self.cash(41,day="2026-10-30")
        result=m.build(datetime(2026,10,30,19,0,tzinfo=TZ))
        self.assertEqual(result["targetDate"],"2026-11-02")
        self.assertEqual(result["score"],41)
    def test_stale_date_rejected(self):
        self.cash(0,day="2026-10-20")
        with self.assertRaisesRegex(RuntimeError,"NO_RECENT"):
            m.build(datetime(2026,11,3,10,30,tzinfo=TZ))
    def test_verified_prior_cash_over_old_full(self):
        self.cash()
        self.put("latest.json",{"dataDate":"2026-10-30",
             "risk":{"date":"2026-10-30","score":49}})
        self.assertEqual(m.build(datetime(2026,11,3,10,30,tzinfo=TZ))["score"],12)
if __name__=="__main__":unittest.main()
