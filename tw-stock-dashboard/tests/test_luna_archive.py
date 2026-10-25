import datetime as dt
import importlib.util
import unittest
from pathlib import Path
NOW=dt.datetime(2026,10,25,2,0,tzinfo=dt.timezone.utc)
SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"archive_luna_history.py"
spec=importlib.util.spec_from_file_location("luna_history",SCRIPT)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def latest(time="2026-10-25T02:00:00Z"):
    return {"schema":1,"generatedAt":time,
     "sources":{"PTT":{"status":"error"},"Bluesky":{"status":"ok"}},
     "social":{"rawSample":2,"sample":1},
     "semantic":{"status":"verified"},
     "items":[
      {"platform":"Bluesky","title":"台股台積電看多投資","url":"https://bsky.app/profile/a/post/1",
       "publishedAt":"2026-10-24T23:00:00Z","investmentEligible":True,"contentType":"投資討論",
       "semantic":{"model":"gemini-3.5-flash-lite","intent":"投資意見","stance":"偏多",
                   "emotion":"理性分析","confidence":"中","evidence":"台股台積電"}},
      {"platform":"PTT","title":"[新聞] 員工運動會","url":"https://www.ptt.cc/bbs/Stock/M.123.html",
       "publishedAt":"2026-10-24T23:00:00Z","investmentEligible":False,"contentType":"新聞轉載"}
     ]}
class ArchiveTest(unittest.TestCase):
    def test_new_daily_archive_deduplicates_observed_links(self):
        one=mod.archive(latest(),now=NOW)
        again=mod.archive(latest("2026-10-25T02:15:00Z"),older=one,
                          now=NOW+dt.timedelta(minutes=15))
        self.assertEqual(one["day"],"2026-10-25")
        self.assertEqual(len(again["records"]),2)
        self.assertEqual(len(again["runs"]),2)
        self.assertEqual(again["records"][0]["firstObservedAt"],"2026-10-25T02:00:00Z")
        self.assertEqual(again["records"][0]["lastObservedAt"],"2026-10-25T02:15:00Z")
        self.assertNotIn("email",str(again))
    def test_summary_exposes_read_only_audited_model_counts(self):
        a=mod.daily_summary(mod.archive(latest(),now=NOW))
        self.assertEqual(a["uniquePostsObserved"],2)
        self.assertEqual(a["modelInterpreted"],1)
        self.assertEqual(a["bull"],1)
        self.assertEqual(a["bear"],0)
        self.assertEqual(a["semanticStatus"],"verified")
        self.assertEqual(a["sourceStatus"]["PTT"],"error")
    def test_reject_stale_or_future_archive(self):
        with self.assertRaises(ValueError):
            mod.archive(latest("2026-10-22T02:00:00Z"),now=NOW)
        with self.assertRaises(ValueError):
            mod.archive(latest("2026-10-25T05:00:00Z"),now=NOW)
    def test_schema_guard(self):
        x=latest();x["schema"]=0
        with self.assertRaises(ValueError):
            mod.archive(x,now=NOW)
if __name__=="__main__":unittest.main()
