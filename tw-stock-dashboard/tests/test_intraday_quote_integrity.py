import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
import pandas as pd
from g_intraday import parse_mis,make_intraday_frame
from g_live import select

DAY="2026-10-14"
NOW=datetime(2026,10,14,9,35,tzinfo=ZoneInfo("Asia/Taipei"))
class TestIntradayQuoteIntegrity(unittest.TestCase):
    def test_verified_zero_trade_uses_reference_close_without_fake_trade(self):
        row={"c":"1234","ex":"otc","d":"20261014","t":"09:30:00","y":"100","z":"-","pz":"-","o":"-","h":"-","l":"-","v":"-"}
        quotes=parse_mis({"msgArray":[row]},DAY,NOW)
        q=quotes[("上櫃","1234")]
        self.assertEqual(q["priceSource"],"no-trade-prevclose")
        self.assertEqual((q["price"],q["volume"],q["open"],q["high"],q["low"]),(100.,0,100.,100.,100.))
        prior=pd.DataFrame({"date":pd.bdate_range(end="2026-10-13",periods=60).strftime("%Y-%m-%d"),"open":[100.]*60,"high":[101.]*60,"low":[99.]*60,"close":[100.]*60,"volume":[100000.]*60})
        intraday=make_intraday_frame(prior,q,DAY)
        self.assertEqual(len(intraday),61)
        self.assertEqual(intraday.volume.iloc[-1],0)
    def test_stale_no_trade_is_not_carried_forward(self):
        row={"c":"1234","ex":"otc","d":"20261013","t":"13:30:00","y":"100","o":"-","h":"-","l":"-","v":"-"}
        self.assertEqual(parse_mis({"msgArray":[row]},DAY,NOW),{})
    def test_lagging_trade_falls_back_to_verified_book_midpoint(self):
        row={"c":"1234","ex":"otc","d":"20261014","t":"09:30:00","y":"100","z":"107","pz":"95","o":"101","h":"103","l":"100","v":"100","b":"102_10","a":"102.2_20"}
        q=parse_mis({"msgArray":[row]},DAY,NOW)[("上櫃","1234")]
        self.assertEqual(q["priceSource"],"bid-ask-midpoint")
        self.assertAlmostEqual(q["price"],102.1)
    def test_invalid_or_stale_trade_without_book_cannot_enter_market(self):
        row={"c":"1234","ex":"otc","d":"20261014","t":"09:30:00","y":"100","z":"107","pz":"95","o":"101","h":"103","l":"100","v":"100"}
        self.assertEqual(parse_mis({"msgArray":[row]},DAY,NOW),{})
    def test_actually_traded_quote_retains_volume(self):
        row={"c":"1234","ex":"tse","d":"20261014","t":"09:30:00","y":"100","z":"102","o":"101","h":"103","l":"100","v":"135"}
        q=parse_mis({"msgArray":[row]},DAY,NOW)[("上市","1234")]
        self.assertEqual(q["priceSource"],"last-trade")
        self.assertEqual(q["volume"],135000)
    def test_no_trade_peer_changes_percentiles_but_cannot_become_signal(self):
        days=pd.bdate_range("2026-07-01",periods=73).strftime("%Y-%m-%d").tolist()
        day=days[-1]
        universe=[{"code":"1000","market":"上市","name":"Traded","industry":"其他","capitalB":50},
                  {"code":"1001","market":"上市","name":"No trade","industry":"其他","capitalB":50}]
        histories={}
        metrics={}
        for i,s in enumerate(universe):
            v=0. if i else 10000000.
            histories[s["code"]+".TW"]=pd.DataFrame({"date":days,"open":[100.]*len(days),"high":[105.]*len(days),"low":[95.]*len(days),"close":[101.]*len(days),"volume":[10000000.]*(len(days)-1)+[v]})
            metrics[s["code"]+".TW"]={"close":101.,"volume":v,"ret20":12.,"ret5":6.,"ma20Slope":4.,"atrPct":3.,"breakoutPct":2.,"rvol":2.,"rvol10":2.,"mom10Pct":7.,"dayRet":1.,"volD":10.}
        f={"break3":True,"break18":True,"eng3":False,"eng18":False,"bull3":True,"bull18":True}
        with patch("g_live.g_eligible",return_value=True),patch("g_live.latest_structure",return_value=f):
            top,_,meta=select(universe,histories,days,day,known_metrics=metrics,intraday=True)
        self.assertEqual(meta["percentileUniverse"],2)
        self.assertEqual([r["code"] for r in top],["1000"])

if __name__=="__main__":unittest.main()
