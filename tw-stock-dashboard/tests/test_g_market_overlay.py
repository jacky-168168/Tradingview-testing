import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from g_market_overlay import (sector_ranking,parse_twse_dispositions,
                              parse_tpex_dispositions,trade_restrictions,build_overlay)

DAY="2026-10-20"
NOW=datetime(2026,10,20,10,30,tzinfo=ZoneInfo("Asia/Taipei"))
def q(price,vol=100000,source="last-trade"):
    return {"price":price,"volume":vol,"previousClose":100.,"priceSource":source}
def universe():
    return [{"market":"上市","code":str(1001+i),"name":"S"+str(i),"industry":"半導體"} for i in range(5)]+[
            {"market":"上櫃","code":str(2001+i),"name":"M"+str(i),"industry":"光電"} for i in range(5)]
class FakeResponse:
    def __init__(self,body):self.body=body
    def raise_for_status(self):pass
    def json(self):return self.body
class Tests(unittest.TestCase):
    def test_trade_only_and_coverage(self):
        a=universe()
        quotes={("上市",str(1001+i)):q(103+i*.1) for i in range(5)}
        quotes.update({("上櫃",str(2001+i)):q(109,source="bid-ask-midpoint") for i in range(5)})
        result=sector_ranking(a,quotes,DAY)
        self.assertEqual(len(result["ranking"]),1)
        self.assertEqual(result["ranking"][0]["industry"],"半導體")
        self.assertEqual(result["ranking"][0]["breadthPct"],100.)
        self.assertTrue(result["notNetFlow"])
    def test_minimum_coverage_and_no_trade(self):
        a=universe()
        quotes={("上市","1001"):q(110),("上市","1002"):q(110),
                ("上市","1003"):q(110,source="no-trade-prevclose")}
        self.assertEqual(sector_ranking(a,quotes,DAY)["ranking"],[])
    def test_no_future_or_wrong_day_rank_movement(self):
        a=universe()
        quotes={("上市",str(1001+i)):q(103) for i in range(5)}
        old={"asOfDate":"2026-10-19","ranking":[{"industry":"半導體","rank":10}]}
        self.assertIsNone(sector_ranking(a,quotes,DAY,old)["ranking"][0]["rankMove"])
        old["asOfDate"]=DAY
        self.assertEqual(sector_ranking(a,quotes,DAY,old)["ranking"][0]["rankMove"],9)
    def test_trading_period_filters(self):
        tw={"fields":["證券代號","處置起迄時間"],
            "data":[["1234","115/10/19～115/10/22"],["5678","115/10/01～115/10/10"]]}
        tp=[{"SecuritiesCompanyCode":"2001","DispositionPeriod":"115/10/20～115/10/25"}]
        self.assertEqual(parse_twse_dispositions(tw,DAY),{"1234"})
        self.assertEqual(parse_tpex_dispositions(tp,DAY),{"2001"})
    def test_partial_api_failure_is_unverified_not_clean(self):
        def mock_get(url,**kwargs):
            if "tpex" in url:raise ValueError("bad JSON")
            return FakeResponse({"fields":["證券代號","處置起迄時間"],
                                 "data":[["1001","115/10/20～115/10/21"]]})
        x=trade_restrictions(DAY,NOW,get=mock_get)
        self.assertEqual(x["markets"]["上市"]["status"],"verified")
        self.assertEqual(x["markets"]["上櫃"]["status"],"unavailable")
        overlay=build_overlay(universe(),{},DAY,
                             [{"code":"1001","market":"上市"},{"code":"2001","market":"上櫃"}],
                             now=NOW,get=mock_get)
        self.assertEqual([r["status"] for r in overlay["topGRestrictions"]],["處置公告期間","待查證"])
    def test_missing_schema_refuses_false_clean(self):
        with self.assertRaises(ValueError):
            parse_twse_dispositions({"fields":[],"data":[]},DAY)
        with self.assertRaises(ValueError):
            parse_tpex_dispositions({},DAY)

if __name__=="__main__":unittest.main()
