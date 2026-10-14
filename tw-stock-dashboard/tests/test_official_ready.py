import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from check_official_ready import ready_for_close,after_official_cutoff
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
if __name__=="__main__":unittest.main()
