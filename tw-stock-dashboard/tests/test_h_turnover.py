import unittest,pandas as pd
from h_turnover import turnover_proxy_pct,score_h,exit_trade
class TestHTurnover(unittest.TestCase):
    def example(self):
        return {"volume":20000000,"rvol10":2.5,"ret5":8,"ret20":20,"ema20Slope5":2.0,"close":80,"ema20":70,
                "closePosition":85,"breakoutPct":1.5,"atrPct":6,"mom10Pct":13,"dayRet":3.1}
    def test_turnover_proxy_is_shares_over_paid_capital(self):
        self.assertAlmostEqual(turnover_proxy_pct(20_000_000,50),4.0)
        self.assertAlmostEqual(turnover_proxy_pct(20_000_000,20),10.0)
        self.assertIsNone(turnover_proxy_pct(20_000_000,0))
    def test_high_turnover_momentum_gate(self):
        m=self.example();score=score_h(m,15,20,2.0)
        self.assertIsNotNone(score);self.assertEqual(score["turnoverProxyPct"],10.0)
        self.assertIsNone(score_h(m,15,100,2.0),"Low turnover fails")
        self.assertIsNone(score_h(m,-2,20,2.0),"Weak vs index fails")
        m["ema20Slope5"]=-1;self.assertIsNone(score_h(m,15,20,2.0))
    def frame(self,rows):
        return pd.DataFrame(rows).set_index("date",drop=False)
    def day(self,date,o,h,l,c):
        return {"date":date,"open":o,"high":h,"low":l,"close":c,"adjclose":c}
    def test_tp7_and_fees(self):
        bars=self.frame([self.day("2026-01-05",100,109,99,104),self.day("2026-01-06",104,106,101,103)])
        x=exit_trade(bars,"2026-01-05","2026-01-06")
        self.assertEqual(x["reason"],"tp");self.assertAlmostEqual(x["grossPct"],7,delta=.02)
        self.assertGreater(x["netPct"],6);self.assertLess(x["netPct"],7)
    def test_stop_has_priority_if_both_touched(self):
        bars=self.frame([self.day("2026-01-05",100,110,95,104)])
        x=exit_trade(bars,"2026-01-05","2026-01-05")
        self.assertEqual(x["reason"],"stop");self.assertLess(x["netPct"],-4)
    def test_gap_penalty_and_timeout(self):
        bars=self.frame([self.day("2026-01-05",100,104,99,101),self.day("2026-01-06",94,96,91,92)])
        self.assertEqual(exit_trade(bars,"2026-01-05","2026-01-06")["reason"],"stop_gap")
        b=self.frame([self.day("2026-01-05",100,102,99,101)])
        self.assertEqual(exit_trade(b,"2026-01-05","2026-01-05")["reason"],"timeout")
    def test_historical_price_jump_excluded(self):
        x=self.frame([self.day("2026-01-05",100,101,99,100),self.day("2026-01-06",25,30,20,25)])
        self.assertIsNone(exit_trade(x,"2026-01-05","2026-01-06"))
if __name__=="__main__":unittest.main()
