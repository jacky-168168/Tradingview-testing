import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from issue_reporter import fingerprint,reconcile
class ReporterTests(unittest.TestCase):
 def test_age_changes_do_not_spam(self):
  a=[{"kind":"stale-g","detail":"old","ageMinutes":70}]
  b=[{"kind":"stale-g","detail":"old","ageMinutes":125}]
  self.assertEqual(fingerprint(a),fingerprint(b))
 def test_weekend_no_g_issue(self):
  calls=[]
  def api(path,method="GET",data=None):
   calls.append((path,method));return [] if method=="GET" else {}
  reconcile({"checkedAt":"2026-10-24T12:00:00+08:00","scopes":["news"],"incidents":[{"kind":"stale-g","detail":"old"}]},api)
  self.assertEqual([x for x in calls if x[1]!="GET"],[])
 def test_dedup_persistent_issue(self):
  rows=[{"kind":"news-stale","detail":"old","ageMinutes":2000}]
  fp=fingerprint(rows)
  issue={"title":"[LOOP-HEALTH] 重大新聞服務","number":10,"state":"open","body":f"<!-- loop-health:news:{fp} -->"}
  calls=[]
  def api(path,method="GET",data=None):
   calls.append((path,method));return [issue] if method=="GET" else {}
  reconcile({"checkedAt":"2026-10-24T11:00:00+08:00","scopes":["news"],"incidents":rows},api)
  self.assertEqual(len(calls),1)
if __name__=="__main__":unittest.main()
