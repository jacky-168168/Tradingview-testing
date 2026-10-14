import unittest
from check_official_ready import ready_for_close
class OfficialPublicationReadinessTests(unittest.TestCase):
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
    def test_unrelated_institution_row_is_not_sufficient(self):
        self.assertFalse(ready_for_close("2026-10-14",lambda *a:{"data":[["自營商","0"]]}))
if __name__=="__main__":unittest.main()
