"""Date-locked market-score contrarian research regression tests."""
import unittest,pandas as pd
from research_g_regime_contrarian import entry_ok,exit_orders,run_cash
class MarketContrarianTests(unittest.TestCase):
    def test_entry_rules_and_prior_day_rebound(self):
        lo={"score":35,"mode":"BOTTOM","dayRet":-2}
        high={"score":43,"mode":"NORMAL","dayRet":1.2}
        self.assertTrue(entry_ok("LTE40",lo))
        self.assertTrue(entry_ok("LTE40_BOTTOM",lo))
        self.assertFalse(entry_ok("LTE40_BOTTOM",{"score":35,"mode":"NORMAL"}))
        self.assertFalse(entry_ok("LOW40_REBOUND",lo))
        self.assertTrue(entry_ok("LOW40_REBOUND",high,lo))
        self.assertFalse(entry_ok("LOW40_REBOUND",high,{"score":41}))
    def test_exit_watch_and_scale(self):
        m={"score":75,"mode":"NORMAL"}
        self.assertEqual(exit_orders("HOLD20",m,False),0)
        self.assertEqual(exit_orders("GTE70_ALL",m,False),1)
        self.assertEqual(exit_orders("GTE80_ALL",m,False),0)
        self.assertEqual(exit_orders("GTE70_HALF_80_ALL",m,False),.5)
        self.assertEqual(exit_orders("GTE70_HALF_80_ALL",m,True),0)
        self.assertEqual(exit_orders("GTE70_HALF_80_ALL",{"score":81,"mode":"NORMAL"},True),1)
        self.assertEqual(exit_orders("TOP_ALL",{"score":32,"mode":"TOP"},False),1)
    def test_no_same_day_future_info_and_half_exit_fees(self):
        days=["2026-01-05","2026-01-06","2026-01-07","2026-01-08","2026-01-09","2026-01-12"]
        highs=[100,100,100,100,100,100]
        prices={"1111.TW":pd.DataFrame({"date":days,"adjOpen":highs,"adjClose":highs}).set_index("date",drop=False)}
        picks={d:[{"sym":"1111.TW","code":"1111"}] for d in days}
        risk={days[0]:{"score":35,"mode":"BOTTOM"},days[1]:{"score":75,"mode":"NORMAL"},
              days[2]:{"score":82,"mode":"NORMAL"}}
        risk.update({d:{"score":82,"mode":"NORMAL"} for d in days[3:]})
        result,trades,curve=run_cash(days,picks,prices,risk,"LTE40","GTE70_HALF_80_ALL")
        self.assertEqual(result["openedBaskets"],1)
        self.assertEqual(result["closedBaskets"],1)
        self.assertEqual(result["scaledBaskets"],1)
        self.assertEqual(trades[0]["entry"],days[1])
        self.assertEqual(trades[0]["exit"],days[3])
        self.assertLess(result["netReturnPct"],0)
        self.assertEqual(len(curve),len(days))
if __name__=="__main__":unittest.main()
