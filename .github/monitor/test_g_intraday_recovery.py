"""Tests for the independent G half-hour fallback."""
import unittest,sys
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).parent))
from g_intraday_recovery import trade_window,is_good_snapshot,recovery_decision
TZ=ZoneInfo("Asia/Taipei")
NOW=datetime(2026,10,21,10,12,tzinfo=TZ)

def snapshot(age=10):
    return {"asOfDate":"2026-10-21","quality":"intraday-provisional-allmarket",
       "publishedAt":(NOW-timedelta(minutes=age)).isoformat(),
       "rows":[{"code":"2330"}],
       "coverage":{"valid":1700,"total":1983,
         "exchange":{"上市":{"valid":990,"total":1090},
                     "上櫃":{"valid":710,"total":893}}}}

def run(age,status="completed",conclusion="success"):
    return {"name":"TW Stock Dashboard","created_at":(NOW-timedelta(minutes=age)).isoformat(),
            "status":status,"conclusion":conclusion}

class RecoveryTests(unittest.TestCase):
    def test_live_fresh_skips(self):
        self.assertEqual(recovery_decision(NOW,snapshot(),{},[]),(False,"fresh-validated-today"))
    def test_previous_day_recovers(self):
        data=snapshot();data["asOfDate"]="2026-10-20"
        self.assertTrue(recovery_decision(NOW,data,{},[])[0])
    def test_overdue_recovers(self):
        self.assertTrue(recovery_decision(NOW,snapshot(34),{},[])[0])
    def test_bad_quality_recovers(self):
        data=snapshot();data["quality"]="closed"
        self.assertTrue(recovery_decision(NOW,data,{},[])[0])
    def test_low_coverage_recovers(self):
        data=snapshot();data["coverage"]["exchange"]["上櫃"]["valid"]=200
        self.assertTrue(recovery_decision(NOW,data,{},[])[0])
    def test_empty_rows_recovers(self):
        data=snapshot();data["rows"]=[]
        self.assertTrue(recovery_decision(NOW,data,{},[])[0])
    def test_future_snapshot_recovers(self):
        self.assertFalse(is_good_snapshot(snapshot(-1),NOW))
    def test_new_failure_after_latest_recovers(self):
        status={"asOfDate":"2026-10-21","checkedAt":NOW.isoformat(),
                "status":"unavailable","message":"MIS low coverage"}
        self.assertTrue(recovery_decision(NOW,snapshot(10),status,[])[0])
    def test_recent_run_prevents_duplicate(self):
        self.assertFalse(recovery_decision(NOW,snapshot(40),{},[run(8)])[0])
    def test_active_run_prevents_duplicate(self):
        self.assertFalse(recovery_decision(NOW,snapshot(40),{},[run(35,"in_progress",None)])[0])
    def test_expired_failure_retries(self):
        self.assertTrue(recovery_decision(NOW,snapshot(40),{},[run(24,"completed","failure")])[0])
    def test_closed_market_never_runs(self):
        for day in [datetime(2026,10,26,11,tzinfo=TZ),datetime(2026,10,25,11,tzinfo=TZ),
                    datetime(2026,10,21,9,0,tzinfo=TZ),datetime(2026,10,21,13,42,tzinfo=TZ)]:
            self.assertFalse(trade_window(day))
            self.assertFalse(recovery_decision(day,{}, {},[])[0])
    def test_open_market_runs(self):
        self.assertTrue(trade_window(NOW))
if __name__=="__main__":unittest.main()
