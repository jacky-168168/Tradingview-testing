import unittest,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from qa_workflow_watchdog import due,hours_since,WORKFLOWS,eod_health,eod_watch,luna_expected_slot,luna_watch
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
class LunaScheduleWatchTests(unittest.TestCase):
    def test_expected_slots_follow_taipei_and_allow_cron_delay(self):
        tz=timezone(timedelta(hours=8))
        before=datetime(2026,10,26,21,32,tzinfo=tz)
        self.assertEqual(luna_expected_slot(before).astimezone(tz).hour,17)
        after=datetime(2026,10,26,22,0,tzinfo=tz)
        self.assertEqual(luna_expected_slot(after).astimezone(tz).strftime("%Y-%m-%d %H:%M"),"2026-10-26 21:10")
        overnight=datetime(2026,10,27,1,30,tzinfo=tz)
        self.assertEqual(luna_expected_slot(overnight).astimezone(tz).strftime("%Y-%m-%d %H:%M"),"2026-10-26 21:10")
    def test_missed_luna_schedule_dispatches_once_with_alert(self):
        from unittest.mock import patch
        now=datetime(2026,10,26,14,0,tzinfo=timezone.utc)
        calls=[];alerts=[]
        def fake_req(path,method="GET",body=None):
            if path.endswith("/runs?per_page=45"):return {"workflow_runs":[]}
            if path.endswith("/dispatches") and method=="POST":calls.append(body);return None
            raise AssertionError(path)
        with patch("qa_workflow_watchdog.req",side_effect=fake_req),patch("qa_workflow_watchdog.publish",side_effect=lambda *args:alerts.append(args)):
            luna_watch(now)
        self.assertEqual(calls,[{"ref":"main"}])
        self.assertEqual(alerts[0][0],"LUNA Public Social Sentiment")
        self.assertIn("21:10",alerts[0][1])
    def test_luna_recovery_respects_dispatch_cooldown(self):
        from unittest.mock import patch
        now=datetime(2026,10,26,14,0,tzinfo=timezone.utc)
        recent={"created_at":(now-timedelta(minutes=25)).isoformat(),"event":"workflow_dispatch","status":"completed","conclusion":"failure"}
        with patch("qa_workflow_watchdog.req",return_value={"workflow_runs":[recent]}) as req,patch("qa_workflow_watchdog.publish"):
            luna_watch(now)
        self.assertEqual(req.call_count,1)
    def test_luna_success_closes_stale_alert(self):
        from unittest.mock import patch
        now=datetime(2026,10,26,14,0,tzinfo=timezone.utc)
        success={"created_at":(now-timedelta(minutes=20)).isoformat(),"event":"schedule","status":"completed","conclusion":"success"}
        with patch("qa_workflow_watchdog.req",return_value={"workflow_runs":[success]}),patch("qa_workflow_watchdog.publish") as alert:
            luna_watch(now)
        alert.assert_called_once_with("LUNA Public Social Sentiment",None)
class EODHealthTests(unittest.TestCase):
    def snapshot(self):
        return {"dataDate":"2026-10-15","risk":{"date":"2026-10-15"},"gSelection":{"dataDate":"2026-10-15"},
                "models":{"A":[],"D":[],"F":[],"F2":[],"G":[]},"institutionQuality":{"status":"complete","date":"2026-10-15","listedRows":900,"otcRows":750,"marketCoverage":{"上市":.95,"上櫃":.92},"missingRanked":0}}
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
    def test_old_snapshot_without_quality_is_rejected(self):
        now=datetime(2026,10,15,13,tzinfo=timezone.utc)
        data=self.snapshot();data.pop("institutionQuality")
        self.assertIn("法人完整性",eod_health(now,data))
    def test_quality_missing_ranked_or_coverage_is_rejected(self):
        now=datetime(2026,10,15,13,tzinfo=timezone.utc)
        data=self.snapshot();data["institutionQuality"]["missingRanked"]=1
        self.assertIn("缺漏",eod_health(now,data))
        data=self.snapshot();data["institutionQuality"]["marketCoverage"]["上櫃"]=0.5
        self.assertIn("覆蓋率",eod_health(now,data))
    def test_closed_market_does_not_require_new_report(self):
        self.assertIsNone(eod_health(datetime(2026,10,26,13,tzinfo=timezone.utc),{}))
class EODWatchScheduleTests(unittest.TestCase):
    def test_before_evening_does_not_query_or_dispatch(self):
        from unittest.mock import patch
        with patch("qa_workflow_watchdog.req",side_effect=AssertionError("Should never dispatch")):
            with patch("qa_workflow_watchdog.load_official_snapshot",side_effect=AssertionError("Should not fetch")):
                eod_watch(datetime(2026,10,15,9,tzinfo=timezone.utc))
                eod_watch(datetime(2026,10,17,13,tzinfo=timezone.utc))
    def test_stale_eod_dispatches_when_no_recent_full_or_active_run(self):
        from unittest.mock import patch
        now=datetime(2026,10,15,13,15,tzinfo=timezone.utc)
        dispatched=[]
        def req(path,method="GET",body=None):
            if path.startswith("/actions/workflows/tw-stock-dashboard.yml/runs"):return {"workflow_runs":[]}
            if path.endswith("/dispatches") and method=="POST":dispatched.append(body);return None
            if path.startswith("/issues"):return []
            raise AssertionError(path)
        with patch("qa_workflow_watchdog.req",side_effect=req),patch("qa_workflow_watchdog.load_official_snapshot",return_value={"dataDate":"2026-10-14"}),patch("qa_workflow_watchdog.publish",return_value=None),patch("qa_workflow_watchdog.issue_for",return_value=None):
            eod_watch(now)
        self.assertEqual(dispatched,[{"ref":"main","inputs":{"mode":"full"}}])
    def test_recent_full_dispatch_blocks_duplicates(self):
        from unittest.mock import patch
        now=datetime(2026,10,15,13,15,tzinfo=timezone.utc);seen=[]
        def req(path,method="GET",body=None):
            if path.startswith("/actions/workflows/tw-stock-dashboard.yml/runs"):
                return {"workflow_runs":[{"created_at":(now-timedelta(minutes=5)).isoformat(),"event":"workflow_dispatch","status":"completed"}]}
            if path.endswith("/dispatches"):seen.append(body)
            return None
        with patch("qa_workflow_watchdog.req",side_effect=req),patch("qa_workflow_watchdog.load_official_snapshot",return_value={"dataDate":"2026-10-14"}),patch("qa_workflow_watchdog.publish",return_value=None),patch("qa_workflow_watchdog.issue_for",return_value=None):
            eod_watch(now)
        self.assertEqual(seen,[])
if __name__=="__main__":unittest.main()

