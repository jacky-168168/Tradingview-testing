import unittest
from g_signal_context import build_context,peer_changes
DAY="2026-10-21"
TIME="2026-10-21T10:30:00+08:00"
def quote(price=105,source="last-trade"):
    return {"price":price,"previousClose":100,"volume":10000,"priceSource":source}
def quotes(market="上市",n=31):
    return {(market,str(1001+i)):quote(102+i/100) for i in range(n)}
def breadth():
    return {"total":{"sample":1200,"upPct":32},"exchange":{"上市":{"sample":1100,"upPct":31},"上櫃":{"sample":100,"upPct":44}}}
class SignalContextTests(unittest.TestCase):
    def test_trade_only_no_invented_peers(self):
        q=quotes()
        q[("上市","1999")]=quote(110,"bid-ask-midpoint")
        p=peer_changes(q)["上市"]
        self.assertEqual(p["sample"],31)
        self.assertAlmostEqual(p["equalWeightMeanPct"],2.15)
        self.assertIsNone(peer_changes({("上市","1001"):quote()})["上市"]["equalWeightMeanPct"])
    def test_previous_close_score_must_match_completed_date(self):
        base={"risk":{"date":"2026-10-20","score":55,"state":"偏空"}}
        rows=[{"market":"上市","code":"1001","name":"測試","currentPct":2}]
        c=build_context(DAY,TIME,"2026-10-20",base,quotes(),breadth(),rows,{"valid":1700})
        self.assertEqual(c["previousCloseRisk"]["score"],55)
        self.assertEqual(c["market"]["breadthBand"],"弱勢")
        self.assertAlmostEqual(c["top20"][0]["relativeToEqualWeightPeersPct"],-0.15)
        self.assertTrue(c["researchOnly"])
        base["risk"]["date"]="2026-10-21"
        self.assertIsNone(build_context(DAY,TIME,"2026-10-20",base,quotes(),breadth(),rows,{})["previousCloseRisk"]["score"])
    def test_no_proxy_relative_strength(self):
        q=quotes()
        q[("上市","1001")]=quote(102,"one-sided-high-bid")
        c=build_context(DAY,TIME,"2026-10-20",{},q,breadth(),
                        [{"market":"上市","code":"1001","currentPct":2}],{})
        self.assertIsNone(c["top20"][0]["intradayPct"])
        self.assertIsNone(c["top20"][0]["relativeToEqualWeightPeersPct"])
        self.assertEqual(c["top20"][0]["priceQuality"],"price-proxy-not-comparable")
    def test_no_fake_live_score_when_breadth_missing(self):
        c=build_context(DAY,TIME,"2026-10-20",{"risk":{"date":"2026-10-20","score":0}},
                        {},{"total":{"sample":10,"upPct":90}},[],{})
        self.assertEqual(c["previousCloseRisk"]["score"],0)
        self.assertIsNone(c["market"]["allMarketUpPct"])
        self.assertEqual(c["market"]["breadthBand"],"資料不足")
if __name__=="__main__":unittest.main()
