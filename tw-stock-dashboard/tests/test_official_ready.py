import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
from check_official_ready import ready_for_close,after_official_cutoff,exchange_closed,main
class OfficialPublicationReadinessTests(unittest.TestCase):
    def test_official_1730_local_cutoff(self):
        tz=ZoneInfo("Asia/Taipei")
        self.assertFalse(after_official_cutoff(datetime(2026,10,15,17,29,59,tzinfo=tz)))
        self.assertTrue(after_official_cutoff(datetime(2026,10,15,17,30,tzinfo=tz)))
        self.assertTrue(after_official_cutoff(datetime(2026,10,15,19,30,tzinfo=tz)))
        self.assertFalse(after_official_cutoff(datetime(2026,10,17,18,0,tzinfo=tz)))
    def test_matching_real_institution_record_allows_publish(self):
        def fetch(day,path,params):
            self.assertEqual(day,"2026-10-14")
            self.assertEqual(path,"fund/BFI82U")
            self.assertEqual(params["dayDate"],"20261014")
            return {"stat":"OK","date":"20261014","data":[["外資及陸資","100000000"]]}
        self.assertTrue(ready_for_close("2026-10-14",fetch))
    def test_empty_official_report_defers(self):
        self.assertFalse(ready_for_close("2026-10-14",lambda *a:{"stat":"OK","data":[]}))
    def test_unpublished_or_network_failure_never_publishes_zero(self):
        def missing(*args):raise RuntimeError("No matching dated BFI82U report")
        self.assertFalse(ready_for_close("2026-10-14",missing))
    def test_wrong_official_date_never_unlocks_publication(self):
        row=[["外資及陸資","100000000"]]
        self.assertFalse(ready_for_close("2026-10-14",lambda *a:{"date":"20261013","data":row}))
        self.assertFalse(ready_for_close("2026-10-14",lambda *a:{"data":row}))
        self.assertTrue(ready_for_close("2026-10-14",lambda *a:{"date":"115/10/14","data":row}))
    def test_unrelated_institution_row_is_not_sufficient(self):
        self.assertFalse(ready_for_close("2026-10-14",lambda *a:{"data":[["自營商","0"]]}))
    def _run_gate(self, when, ready_result=None):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"outputs.txt"
            summary=Path(tmp)/"summary.txt"
            with patch.dict(os.environ,{"GITHUB_OUTPUT":str(out),"GITHUB_STEP_SUMMARY":str(summary),"GITHUB_EVENT_NAME":"push"}):
                with patch("check_official_ready.ready_for_close",side_effect=AssertionError("holiday must not fetch")) if ready_result is None else patch("check_official_ready.ready_for_close",return_value=ready_result):
                    main(when)
            return out.read_text(encoding="utf-8"),summary.read_text(encoding="utf-8") if summary.exists() else ""
    def test_oct26_compensatory_holiday_does_not_fetch_or_publish(self):
        tz=ZoneInfo("Asia/Taipei")
        for hour in (17,22):
            with self.subTest(hour=hour):
                when=datetime(2026,10,26,hour,45,tzinfo=tz)
                self.assertTrue(exchange_closed(when))
                out,summary=self._run_gate(when)
                self.assertIn("ready=false",out)
                self.assertIn("official exchange holiday",summary)
    def test_other_confirmed_2026_closures_match_calendar(self):
        tz=ZoneInfo("Asia/Taipei")
        self.assertTrue(exchange_closed(datetime(2026,10,9,19,0,tzinfo=tz)))
        self.assertTrue(exchange_closed(datetime(2026,12,25,19,0,tzinfo=tz)))
        self.assertFalse(exchange_closed(datetime(2026,10,27,19,0,tzinfo=tz)))
        self.assertFalse(exchange_closed(datetime(2027,10,26,19,0,tzinfo=tz)))
    def test_regular_trading_day_missing_official_report_still_fails_closed(self):
        tz=ZoneInfo("Asia/Taipei")
        with self.assertRaisesRegex(SystemExit,"after 17:30"):
            self._run_gate(datetime(2026,10,27,19,0,tzinfo=tz),False)
    def test_regular_trading_day_valid_report_still_unlocks(self):
        tz=ZoneInfo("Asia/Taipei")
        out,_=self._run_gate(datetime(2026,10,27,19,0,tzinfo=tz),True)
        self.assertIn("ready=true",out)
    def test_pre_cutoff_regular_day_still_defers(self):
        tz=ZoneInfo("Asia/Taipei")
        out,_=self._run_gate(datetime(2026,10,27,17,29,tzinfo=tz))
        self.assertIn("ready=false",out)
if __name__=="__main__":unittest.main()
