"""Offline regression: Fugle market quote time, cumulative average and 09:15 bar boundary."""
import sys,unittest
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
from private_fugle_vwap import TZ,quote_analysis,opening_range,interpret,sym_list,timestamp,run
NOW=datetime(2026,10,12,9,35,tzinfo=TZ)
def fixture(symbol="0050",now=NOW,price=106,avg=104):
    micro=int((now-timedelta(seconds=15)).timestamp()*1000000)
    return {"date":now.date().isoformat(),"symbol":symbol,"avgPrice":avg,
        "lastTrade":{"price":price,"time":micro},"total":{"tradeVolume":25000}}
def rows(count=15,now=NOW):
    return {"date":now.date().isoformat(),"symbol":"0050","data":[
        {"date":datetime(2026,10,12,9,i,tzinfo=TZ).isoformat(),"high":105,"low":100,"volume":100} for i in range(count)]}
class PrivateVWAP(unittest.TestCase):
    def test_microsecond_epoch(self):
        q=fixture();t=timestamp(q["lastTrade"]["time"])
        self.assertEqual(t.date(),NOW.date())
        self.assertLess((NOW-t).total_seconds(),30)
    def test_g_top3_frozen(self):
        f={"dataDate":"2026-10-08","gSelection":{"dataDate":"2026-10-08","variant":"G_DOUBLE_PERSIST"},
           "models":{"G":[{"code":"3624"},{"code":"2340"},{"code":"6672"},{"code":"2241"}]}}
        self.assertEqual(sym_list(f)[0],["0050","3624","2340","6672"])
        f["gSelection"]["dataDate"]="2026-10-07"
        with self.assertRaises(ValueError):sym_list(f)
    def test_quote_uses_actual_trade_not_trial(self):
        q=fixture();q["lastPrice"]=999
        r=quote_analysis(q,"0050",NOW)
        self.assertTrue(r["valid"])
        self.assertTrue(r["aboveCumulativeAverage"])
        self.assertAlmostEqual(r["tradeVsSessionAveragePct"],1.9231,places=3)
        q["isTrial"]=True
        self.assertFalse(quote_analysis(q,"0050",NOW)["valid"])
    def test_stale_date_future_bad_avg_rejected(self):
        q=fixture();q["lastTrade"]["time"]=int((NOW-timedelta(minutes=9)).timestamp()*1e6)
        self.assertFalse(quote_analysis(q,"0050",NOW)["valid"])
        q=fixture();q["lastTrade"]["time"]=int((NOW+timedelta(seconds=30)).timestamp()*1e6)
        self.assertFalse(quote_analysis(q,"0050",NOW)["valid"])
        q=fixture();q["date"]="2026-10-08"
        self.assertFalse(quote_analysis(q,"0050",NOW)["valid"])
        q=fixture(avg=0)
        self.assertFalse(quote_analysis(q,"0050",NOW)["valid"])
    def test_opening_range_only_completed_15_minutes(self):
        self.assertFalse(opening_range(rows(14),"0050",NOW)["valid"])
        v=opening_range(rows(),"0050",NOW)
        self.assertTrue(v["valid"])
        self.assertEqual(v["rangeHigh"],105)
        self.assertEqual(v["rangeLow"],100)
        self.assertFalse(opening_range(rows(),"0050",datetime(2026,10,12,9,14,tzinfo=TZ))["valid"])
    def test_research_flag_not_execution(self):
        observations=[quote_analysis(fixture(s,price=106 if s=="0050" else 105,avg=104),s,NOW)
            for s in ("0050","3624","2340","6672")]
        o=interpret({"symbols":observations},opening_range(rows(),"0050",NOW))
        self.assertEqual(o["state"],"FOLLOW_THROUGH_15M")
        self.assertFalse(o["claimBuyPermission"])
        observations[0]["tradePricePrivate"]=104
        o=interpret({"symbols":observations},opening_range(rows(),"0050",NOW))
        self.assertNotEqual(o["state"],"FOLLOW_THROUGH_15M")
        self.assertFalse(o["claimBuyPermission"])
    def test_outside_cash_session_avoids_api(self):
        t=datetime(2026,10,11,9,35,tzinfo=TZ)
        self.assertEqual(run(t,key=None)["status"],"outside_cash_session")
    def test_no_private_key_in_source_files(self):
        src=Path(__file__).resolve().parents[1]/"research"/"private_fugle_vwap.py"
        t=src.read_text(encoding="utf-8")
        self.assertNotIn('FUGLE_API_KEY="',t)
        self.assertNotIn('FUGLE_API_KEY=',t)
if __name__=="__main__":unittest.main()
