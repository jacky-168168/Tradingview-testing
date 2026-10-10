"""Offline fixtures: date pinning, old/new breadth format, partial-day resume and no fake scores."""
import sys,unittest,tempfile,json
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import collect_market_risk_history as c

class Response:
    status_code=200
    def __init__(self,payload):self.payload=payload
    def raise_for_status(self):pass
    def json(self):return self.payload

BREADTH={"stat":"OK","date":"113年10月08日","tables":[
    {"title":"113年10月08日 漲跌證券數合計","fields":["類型","整體市場","股票"],
     "data":[["上漲(漲停)","3,201(10)","425(14)"],["下跌(跌停)","4,201(40)","540(2)"]]}]}
FOREIGN={"stat":"OK","date":"113年10月08日","data":[
    ["外資及陸資(不含外資自營商)","0","0","-75,852,293,490"],
    ["外資自營商","0","0","0"]]}

class CollectorTests(unittest.TestCase):
    def test_roc_and_gregorian(self):
        self.assertEqual(c.iso_from_text("113年10月08日 漲跌證券數合計"),"2024-10-08")
        self.assertEqual(c.iso_from_text("20241008"),"2024-10-08")
        self.assertEqual(c.iso_from_text("2024/10/08"),"2024-10-08")
    def test_source_date_must_match(self):
        s=Mock();s.get.return_value=Response(BREADTH)
        j,url=c.fetch_json(s,"afterTrading/MI_INDEX","2024-10-08",{"date":"20241008","type":"ALL"})
        self.assertEqual(c.parse_breadth(j),(425,540))
        with patch.object(c,"HOSTS",("https://www.twse.com.tw",)):
            with self.assertRaisesRegex(c.ArchiveError,"DATE_MISMATCH"):
                c.fetch_json(s,"afterTrading/MI_INDEX","2024-10-07",{"date":"20241007"})
    def test_foreign_units(self):
        self.assertAlmostEqual(c.parse_foreign(FOREIGN),-758.5229349)
    def test_no_unverified_date(self):
        with self.assertRaisesRegex(c.ArchiveError,"REPORT_DATE_UNVERIFIED"):
            c.verify_report_date({"stat":"OK","data":[["x","0"]]},"2024-10-08")
    def test_partial_success_resume(self):
        session=Mock()
        session.get.side_effect=[Response(BREADTH),Response({"stat":"很抱歉，沒有符合條件的資料!"}),
            Response({"stat":"很抱歉，沒有符合條件的資料!"})]
        with patch.object(c,"HOSTS",("https://www.twse.com.tw","https://wwwc.twse.com.tw")):
            day=c.update_day(session,"2024-10-08",{},timeout=2)
        self.assertEqual(day["up"],425)
        self.assertFalse(day["ok"])
        self.assertNotIn("foreign",day)
        with patch.object(c,"fetch_breadth",side_effect=AssertionError("do not refetch breadth")):
            with patch.object(c,"fetch_foreign",return_value={"foreign":-758.52,"foreignSource":"fixture"}):
                finished=c.update_day(None,"2024-10-08",day,timeout=2)
        self.assertTrue(c.valid_saved(finished))
        self.assertNotIn("error",finished)
    def test_atomic_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"risk_inputs.json"
            c.atomic_json(path,{"2024-10-08":{"ok":True,"up":425,"down":540,"foreign":-758.5}})
            self.assertEqual(json.loads(path.read_text())["2024-10-08"]["up"],425)
            self.assertFalse(path.with_name(path.name+".tmp").exists())

if __name__=="__main__":unittest.main()
