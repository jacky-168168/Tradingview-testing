import unittest,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from qa_workflow_watchdog import due,hours_since,WORKFLOWS,eod_health
class WorkflowHealthTests(unittest.TestCase):
    def test_tracks_critical_flows(self):
        self.assertTrue({"TW Stock Python CI","Full Website Browser Audit","TW Stock Dashboard"}.issubset(WORKFLOWS))
    def test_daily_ci_missing_is_detected(self):
        now=datetime(2026,10,15,13,tzinfo=timezone.utc)
        old=(now-timedelta(hours=27)).isoformat()
        self.assertIn("超過",due("TW Stock Python CI",{"created_at":old},now))
    def test_recent_ci_is_healthy(self):
        now=datetime(2026,10,15,13,tzinfo=timezone.utc)
        recent=(now-timedelta(hours=3)).isoformat()
        self.assertIsNone(due("TW Stock Python CI",{"created_at":recent},now))
    def test_weekly_browser_lag(self):
        now=datetime(2026,10,15,13,tzinfo=timezone.utc)
        self.assertIn("超過",due("Full Website Browser Audit",{"created_at":(now-timedelta(days=9)).isoformat()},now))
    def test_missing_or_invalid_date(self):
        now=datetime(2026,10,15,13,tzinfo=timezone.utc)
        self.assertIsNone(hours_since("bad-date",now))
        self.assertIn("找不到",due("TW Stock Python CI",None,now))
    def test_untracked_flow_cannot_trigger_daily_alert(self):
        self.assertIsNone(due("TW Stock Pages",None,datetime.now(timezone.utc)))
class EODHealthTests(unittest.TestCase):
    def snapshot(self):
        return {"dataDate":"2026-10-15","risk":{"date":"2026-10-15"},"gSelection":{"dataDate":"2026-10-15"},
                "models":{"A":[],"D":[],"F":[],"F2":[],"G":[]}}
    def test_complete_current_eod_is_valid(self):
        now=datetime(2026,10,15,13,tzinfo=timezone.utc)
        self.assertIsNone(eod_health(now,self.snapshot()))
    def test_stale_eod_is_flagged(self):
        now=datetime(2026,10,15,13,tzinfo=timezone.utc)
        d=self.snapshot();d["dataDate"]="2026-10-14"
        self.assertIn("尚未發布",eod_health(now,d))
    def test_risk_date_and_g_date_cannot_mismatch(self):
        now=datetime(2026,10,15,13,tzinfo=timezone.utc)
        d=self.snapshot();d["risk"]["date"]="2026-10-14"
        self.assertIn("Risk Score",eod_health(now,d))
        d=self.snapshot();d["gSelection"]["dataDate"]="2026-10-14"
        self.assertIn("G 正式",eod_health(now,d))
    def test_closed_market_does_not_require_new_report(self):
        self.assertIsNone(eod_health(datetime(2026,10,26,13,tzinfo=timezone.utc),{}))
if __name__=="__main__":unittest.main()
