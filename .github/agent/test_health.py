import sys,unittest
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).parent))
from health import evaluate_g,evaluate_news,g_session,inspect
TZ=ZoneInfo("Asia/Taipei");NOW=datetime(2026,10,21,11,20,tzinfo=TZ)

def latest(minutes=20):
    return {"asOfDate":"2026-10-21","publishedAt":(NOW-timedelta(minutes=minutes)).isoformat(),
      "quality":"intraday-provisional-allmarket","rows":[{"code":"2330"}],
      "coverage":{"valid":1700,"total":1983,
       "exchange":{"上市":{"valid":950,"total":1090},"上櫃":{"valid":750,"total":893}}}}
def runs(minutes=20,conclusion="success"):
    return [{"name":"test","created_at":(NOW-timedelta(minutes=minutes)).isoformat(),"status":"completed","conclusion":conclusion}]
def assess(data=None,status=None,dashboard=None,monitor=None,recovery=None,pages=None):
    return evaluate_g(NOW,data if data is not None else latest(),status or {},
          dashboard if dashboard is not None else runs(),monitor if monitor is not None else runs(),
          recovery if recovery is not None else runs(),pages)
def kinds(rows):return [r["kind"] for r in rows]
class HealthTests(unittest.TestCase):
    def test_healthy(self):
        self.assertEqual(assess(pages=latest()),[])
    def test_stale_yesterday(self):
        d=latest(1500);d["asOfDate"]="2026-10-20"
        self.assertIn("stale-g",kinds(assess(data=d)))
    def test_missing_primary(self):
        self.assertIn("missing-schedule",kinds(assess(dashboard=[])))
    def test_primary_continuous_failure(self):
        self.assertIn("missing-schedule",kinds(assess(dashboard=runs(conclusion="failure"))))
    def test_monitor_missing_and_recovery_missing(self):
        a=assess(monitor=[],recovery=[])
        self.assertEqual(kinds(a).count("monitor-failed"),2)
    def test_invalid_stock(self):
        d=latest();d["rows"]=[{"code":"XXXX"}]
        self.assertIn("stale-g",kinds(assess(data=d)))
    def test_future_timestamp(self):
        self.assertIn("stale-g",kinds(assess(data=latest(-1))))
    def test_coverage_threshold(self):
        d=latest();d["coverage"]["valid"]=999
        self.assertIn("data-quality",kinds(assess(data=d)))
    def test_otc_coverage(self):
        d=latest();d["coverage"]["exchange"]["上櫃"]["valid"]=300
        self.assertIn("data-quality",kinds(assess(data=d)))
    def test_unavailable_newer(self):
        s={"asOfDate":"2026-10-21","checkedAt":NOW.isoformat(),"status":"unavailable","message":"MIS timeout"}
        self.assertIn("new-unavailable",kinds(assess(status=s)))
    def test_pages_lag_only_after_grace(self):
        self.assertNotIn("pages-lag",kinds(assess(pages=latest(35))))
        self.assertIn("pages-lag",kinds(assess(data=latest(30),pages=latest(85))))
    def test_market_early_and_holiday_quiet(self):
        for t in [datetime(2026,10,21,9,30,tzinfo=TZ),datetime(2026,10,21,13,45,tzinfo=TZ),
                  datetime(2026,10,26,11,tzinfo=TZ),datetime(2026,10,24,11,tzinfo=TZ)]:
            self.assertFalse(g_session(t))
            self.assertEqual(evaluate_g(t,{}, {},[],[],[]),[])
    def test_news_stale(self):
        d={"generatedAt":(NOW-timedelta(hours=40)).isoformat(),"status":"ok","items":[]}
        self.assertIn("news-stale",kinds(evaluate_news(NOW,d,runs())))
    def test_news_empty_honest(self):
        d={"generatedAt":NOW.isoformat(),"status":"empty","items":[]}
        self.assertEqual(evaluate_news(NOW,d,runs()),[])
    def test_outside_session_does_not_fetch_g_at_all(self):
        at=datetime(2026,10,24,11,tzinfo=TZ)
        called=[]
        def file(path):
            called.append(path)
            return {"generatedAt":at.isoformat(),"status":"empty","items":[]}
        f={"file":file,"runs":lambda name:runs(),"json":lambda url:{}}
        output=inspect(at,f)
        self.assertFalse(output["gSession"])
        self.assertFalse(any("g_intraday" in p for p in called))
        self.assertEqual(output["scopes"],["news"])
if __name__=="__main__":unittest.main()
