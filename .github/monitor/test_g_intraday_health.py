import unittest,sys
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).parent))
from g_intraday_health import assess,session
TZ=ZoneInfo("Asia/Taipei");now=datetime(2026,10,15,11,20,tzinfo=TZ)
def live(delta=0,listed=900,otc=700):
    t=now-timedelta(minutes=delta)
    return {"asOfDate":t.date().isoformat(),"publishedAt":t.isoformat(),"quality":"intraday-provisional-allmarket",
    "rows":[{"code":"6834"}],"coverage":{"valid":listed+otc,"total":1982,
    "exchange":{"上市":{"valid":listed,"total":1089},"上櫃":{"valid":otc,"total":893}}}}
def runs():
    return [{"name":"TW Stock Dashboard","created_at":now.isoformat(),"status":"completed","conclusion":"success"}]
class TestWatchdog(unittest.TestCase):
    def test_healthy(self):self.assertTrue(assess(now,live(),{},runs())["ok"])
    def test_stale(self):self.assertFalse(assess(now,live(66),{},runs())["ok"])
    def test_future_published_at(self):self.assertFalse(assess(now,live(-1),{},runs())["ok"])
    def test_missing_today(self):self.assertFalse(assess(now,live(1440),{},runs())["ok"])
    def test_missing_job(self):self.assertTrue(any("工作紀錄" in x for x in assess(now,live(),{},[])["errors"]))
    def test_low_otc(self):self.assertTrue(any("上櫃" in x for x in assess(now,live(0,1000,360),{},runs())["errors"]))
    def test_empty(self):
        d=live();d["rows"]=[]
        self.assertFalse(assess(now,d,{},runs())["ok"])
    def test_failed_latest(self):
        d=live(20);s={"asOfDate":"2026-10-15","status":"unavailable","checkedAt":now.isoformat(),"message":"MIS"}
        self.assertTrue(any("重選失敗" in x for x in assess(now,d,s,runs())["errors"]))
    def test_pages_stale(self):
        self.assertTrue(any("Pages" in x for x in assess(now,live(30),{},runs(),live(80))["errors"]))
    def test_holiday_and_out_of_hours(self):
        self.assertFalse(session(datetime(2026,10,26,11,0,tzinfo=TZ)))
        self.assertFalse(session(datetime(2026,10,17,11,0,tzinfo=TZ)))
        self.assertFalse(session(datetime(2026,10,15,9,30,tzinfo=TZ)))
        self.assertTrue(session(now))
if __name__=="__main__":unittest.main()
