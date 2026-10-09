"""Regression tests: no rolling latest-market API data may enter a prior date's risk score."""
from __future__ import annotations
import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import risk
class DummyResponse:
    def __init__(self,data):self.data=data
    def raise_for_status(self):pass
    def json(self):return self.data
class TestPinnedDates(unittest.TestCase):
    def test_breadth_pinned_to_exact_date(self):
        payload={"stat":"OK","date":"115年10月08日",
            "tables":[{"title":"漲跌證券數合計","fields":["類型","整體市場","股票"],
                "data":[["上漲(漲停)","5,285(78)","425(14)"],["下跌(跌停)","9,634(83)","540(2)"]]}]}
        with patch.object(risk.requests,"get",return_value=DummyResponse(payload)) as get:
            self.assertEqual(risk.breadth("2026-10-08"),(425,540))
            args,kwargs=get.call_args
            self.assertEqual(kwargs["params"]["date"],"20261008")
    def test_foreign_pinned_to_exact_date(self):
        payload={"stat":"OK","date":"115年10月08日",
            "data":[["外資及陸資(不含外資自營商)","0","0","-75,852,293,490"],["外資自營商","0","0","0"]]}
        with patch.object(risk.requests,"get",return_value=DummyResponse(payload)) as get:
            self.assertAlmostEqual(risk.foreign_market_net("2026-10-08"),-758.5229349)
            self.assertEqual(get.call_args.kwargs["params"]["dayDate"],"20261008")
    def test_mismatched_date_fails(self):
        payload={"stat":"OK","date":"115年10月07日","tables":[]}
        with patch.object(risk.requests,"get",return_value=DummyResponse(payload)):
            with self.assertRaisesRegex(RuntimeError,"date mismatch"):
                risk.breadth("2026-10-08")
    def test_missing_report_fails_instead_of_zero_score(self):
        with patch.object(risk.requests,"get",return_value=DummyResponse({"stat":"很抱歉，沒有符合條件的資料!"})):
            with self.assertRaisesRegex(RuntimeError,"not ready"):
                risk.breadth("2026-10-09")
    def test_zero_fallback_never_used(self):
        with patch.object(risk.requests,"get",side_effect=TimeoutError("TWSE unavailable")):
            with self.assertRaises(TimeoutError):
                risk.foreign_market_net("2026-10-08")
if __name__=="__main__":unittest.main()
